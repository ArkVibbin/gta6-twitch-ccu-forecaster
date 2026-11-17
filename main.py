"""gta6-twitch-ccu-forecast-01: a comparable-shape forecaster.

Reads one case (Twitch "Grand Theft Auto VI" viewers recorded up to the end of
release day's first hour) and writes the five quantiles of hours 2..24.

Model: every comparable launch in the case is turned into a log-ratio curve
r_h = ln(mean_hour_h / mean_hour_1) for its own release day. A forecast for
this case is the weighted quantile of those ratios at each hour, re-anchored on
the case's hour-1 print:

    q_tau(h) = p1 * exp(alpha * median_h + (emp_q_tau(h) - median_h))

Donors are weighted by tier (a clean launch over an early-access-contaminated
one), by whether the launch rolled at midnight local (as GTA VI does), and by
how similar their pre-release surge is to this case's own (a Gaussian kernel on
the log jump from the prior 48 hours into hour 1).

Run: python3 main.py            # every /input/*.in -> /output/<id>.out
     python3 main.py --selfcheck  # leave-one-out loss over the case's own comparables
"""

import json
import math
import os
import sys
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
SIGMA = 0.15

ALPHA = 0.75     # how much of the comparable median ratio is believed
SPREAD = 1.0     # scale on the comparable spread around that median
BANDWIDTH = 0.7  # log-surge distance at which a donor's weight halves in effect
CLIP = 2.5       # a donor ratio further than this from 1x is a data artefact, not a shape
TIER_W = {"comparable": 1.0, "early-access-contaminated": 0.55}
ROLL_W = {True: 1.6, False: 0.5}
MIN_HOURS = 12


def round2(x: float) -> float | int:
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def tier_of(comparable: dict) -> str | None:
    unlock = comparable.get("unlock") or ""
    if "target-history" in unlock:
        return None
    if "early-access" in unlock:
        return "early-access-contaminated"
    if "Tier: weak" in unlock:
        return None
    return "comparable"


def rolled_midnight(comparable: dict) -> bool:
    unlock = (comparable.get("unlock") or "").lower()
    return "midnight local" in unlock or "rolling" in unlock


def median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if not n:
        return 1.0
    mid = n // 2
    return ordered[mid] if n % 2 else 0.5 * (ordered[mid - 1] + ordered[mid])


def donor_curve(comparable: dict) -> dict | None:
    """The comparable's release-day log-ratio curve, or None if it is too thin."""
    tier = tier_of(comparable)
    day = (comparable.get("day_start") or "")[:10]
    if tier is None or not day:
        return None
    hourly: dict[int, list[float]] = {}
    before: list[float] = []
    for point in comparable.get("hourly") or []:
        stamp = point.get("from") or ""
        if not stamp:
            continue
        viewers = point.get("viewers")
        if not isinstance(viewers, (int, float)):
            continue
        if stamp[:10] == day:
            hourly.setdefault(int(stamp[11:13]) + 1, []).append(float(viewers))
        elif stamp < day:
            before.append(float(viewers))
    means = {h: sum(v) / len(v) for h, v in hourly.items()}
    if means.get(1, 0.0) < 1.0:
        return None
    ratios = {
        h: math.log(max(means[h], 1.0) / means[1])
        for h in range(2, 25)
        if h in means and means[h] > 0.0
    }
    if len(ratios) < MIN_HOURS:
        return None
    prior = max(1.0, median(before[-48:]) if before else 1.0)
    return {
        "ratios": ratios,
        "tier": tier,
        "rolling": rolled_midnight(comparable),
        "surge": math.log(means[1] / prior),
    }


def weighted_quantile(pairs: list[tuple[float, float]]) -> list[float]:
    ordered = sorted(pairs)
    total = sum(w for _, w in ordered)
    out = []
    for level in LEVELS:
        acc = 0.0
        chosen = ordered[-1][0]
        for value, weight in ordered:
            acc += weight
            if acc / total >= level:
                chosen = value
                break
        out.append(chosen)
    return out


def forecast_ratios(donors: list[dict], surge: float) -> dict[int, list[float]]:
    out: dict[int, list[float]] = {}
    for h in range(2, 25):
        pairs = []
        for donor in donors:
            r = donor["ratios"].get(h)
            if r is None:
                continue
            w = TIER_W[donor["tier"]] * ROLL_W[donor["rolling"]]
            w *= math.exp(-0.5 * ((donor["surge"] - surge) / BANDWIDTH) ** 2)
            if w > 1e-4:
                pairs.append((max(-CLIP, min(CLIP, r)), w))
        if len(pairs) < 3:
            out[h] = [0.0, 0.0, 0.0, 0.0, 0.0]
            continue
        qs = weighted_quantile(pairs)
        mid = qs[2]
        out[h] = [ALPHA * mid + SPREAD * (q - mid) for q in qs]
    return out


def shift(donors: list[dict], surge: float, p1: float) -> dict[int, list[float]]:
    """Log-ratio rows -> absolute viewer quantiles for this case."""
    rows = forecast_ratios(donors, surge)
    out = {}
    for h in range(2, 25):
        q = [p1 * math.exp(x) for x in rows[h]]
        q = [min(max(v, 0.01), 1e9) for v in q]
        for i in range(1, 5):
            q[i] = max(q[i], q[i - 1])
        out[h] = [round2(v) for v in q]
    return out


def surge_of(case: dict, p1: float) -> float:
    checkpoint = case.get("checkpoint") or ""
    prior = [
        float(p["viewers"])
        for p in case.get("history") or []
        if (p.get("from") or "") < checkpoint and isinstance(p.get("viewers"), (int, float))
    ]
    return math.log(p1 / max(1.0, median(prior[-48:]) if prior else 1.0))


def forecast_case(case: dict, name: str) -> dict:
    if case.get("levels") != LEVELS:
        raise ValueError(f"{name} asks for levels {case.get('levels')}, not {LEVELS}")
    first = next((k for k in case.get("known") or [] if k.get("hour") == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))
    donors = [d for d in (donor_curve(c) for c in case.get("comparables") or []) if d]
    if not donors:
        rows = {h: [p1 * math.exp(z * SIGMA * math.sqrt(h - 1)) for z in Z] for h in range(1, 25)}
        return {"hours": [{"hour": r["hour"], "q": [round2(v) for v in rows[r["hour"]]]} for r in case["forecast"]]}
    rows = shift(donors, surge_of(case, p1), p1)
    return {"hours": [{"hour": r["hour"], "q": rows[r["hour"]]} for r in case["forecast"]]}


def pinball(rows: dict[int, list[float]], means: dict[int, float]) -> float | None:
    items = []
    for h, q in rows.items():
        if h not in means:
            continue
        ly = math.log(max(means[h], 1.0))
        for tau, value in zip(LEVELS, q):
            d = ly - math.log(max(value, 1e-9))
            items.append(2.0 * max(tau * d, (tau - 1.0) * d))
    return sum(items) / len(items) if items else None


def selfcheck(cases: list[dict]) -> None:
    ours, base = [], []
    for case in cases:
        donors = [d for d in (donor_curve(c) for c in case.get("comparables") or []) if d]
        for i, held in enumerate(donors):
            if len(held["ratios"]) < MIN_HOURS:
                continue
            rest = donors[:i] + donors[i + 1:]
            rows = forecast_ratios(rest, held["surge"])
            p1 = math.exp(0.0)  # ratios only: score against the held-out curve's own hour 1
            means = {h: p1 * math.exp(r) for h, r in held["ratios"].items()}
            got = pinball({h: [math.exp(x) for x in q] for h, q in rows.items()}, means)
            if got is not None:
                ours.append(got)
            base_rows = {h: [math.exp(z * SIGMA * math.sqrt(h - 1)) for z in Z] for h in means}
            ref = pinball(base_rows, means)
            if ref is not None:
                base.append(ref)
    print(f"donor curves scored: {len(ours)}")
    print(f"comparable-shape loss: {sum(ours) / len(ours):.4f}")
    print(f"persistence loss:      {sum(base) / len(base):.4f}")


def main() -> None:
    paths = sorted(INPUT_DIR.glob("*.in"))
    if "--selfcheck" in sys.argv:
        selfcheck([json.loads(p.read_text(encoding="utf-8")) for p in paths])
        return
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in paths:
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
