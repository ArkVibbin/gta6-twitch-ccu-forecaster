# gta6-twitch-ccu-forecaster

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/ArkVibbin/gta6-twitch-ccu-forecaster/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/ArkVibbin/gta6-twitch-ccu-forecaster/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts, hour by hour, how many people watch Grand Theft Auto VI live on Twitch across the 24 UTC hours of its release day, 2026-11-19, from everything recorded up to the end of its first hour: five quantiles an hour, scored by pinball loss on the log scale. It learns the day's shape from the past AAA launches shipped inside each case rather than assuming the first hour holds all day.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
python3 main.py --selfcheck   # leave-one-out loss over the case's own comparables
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=veb086x7&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
