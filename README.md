# carbon-aware-au

> Run your jobs when the Australian grid is cleanest.

**Status:** v0.1 core built; estimate validated; the "wait for threshold" policy does NOT yet beat running now (see below) · Portfolio project #7 · see `../README.md`

## The idea

A CLI and GitHub Action that delays a CI job or cron task until NEM emissions intensity in your region drops below a threshold.

## Stack

Python (uv), the shared `nem` client from `nem-mcp`, a composite GitHub Action, pytest.

Python project managed with `uv`; target a one-command run (`uv run ...`).

## Build plan (v1)

- [x] Estimate regional emissions intensity from dispatch data × AEMO emissions factors (CDEII)
- [x] CLI: `carbon-aware-au wait --region NSW1 --below 400 --max-wait 6h -- <command>`
- [x] Composite GitHub Action wrapper (`action.yml`; untested on GitHub)
- [ ] (simulation done, result unflattering, so no hero chart yet; see below) README chart: CO₂ for "run now" vs "run at the cleanest window" over a week

## Run it

```bash
uv sync
uv run carbon-aware-au now
uv run carbon-aware-au wait --region SA1 --below 100 --max-wait 3h -- ./deploy.sh
uv run pytest -q     # 19 tests
```

`--below` is in g CO₂e/kWh (400 g/kWh = 0.4 t/MWh). If the deadline passes it runs the command anyway; use `--on-timeout fail` to stop instead.

Depends on `nem-mcp` (the shared `nem` client) as a git dependency on `github.com/Guinerve/nem-mcp`. While that repo is private, installs need GitHub credentials.

## How I know it's right

**Intensity estimate vs AEMO's published CDEII daily summary**, 7 days (2026-09-21 to 27) × 5 regions = 35 region-days (`docs/validation-2026-09-21_27.txt`, rerun with `scripts/validate.py`):

| | |
|---|---|
| Mean absolute error | **9.6 g/kWh** |
| Mean absolute % error | **2.8 %** |
| Correlation | **0.9993** |
| Worst single region-day | VIC1 2026-09-27: +44 g/kWh (+7.5 %) |
| Typical bias | slightly high (we use gross SCADA output; CDEII uses sent-out energy) |

Note: CDEII's published summary is **daily per region** (the week number is just a label).

**Does waiting actually save CO₂? Not with the v1 policy.** Replaying that same week with 1-hour jobs requested at 08:00, 12:00 and 17:00, max wait 6 h, **threshold = the 30th percentile of the previous week** (so no lookahead), job intensity averaged over the 5-minute intervals the job actually runs in (`docs/simulation-all-regions.txt`):

| Region | Run now → wait (v1 policy) | Hindsight oracle (best start in the window) |
|---|---:|---:|
| NSW1 | −9.5 % (worse) | 3.1 % |
| QLD1 | −4.7 % (worse) | 2.9 % |
| VIC1 | −0.7 % (worse) | 9.1 % |
| SA1 | −3.9 % (worse) | 30.4 % |
| TAS1 | 7.6 % | 26.5 % |

(An earlier version of this script picked the threshold from the simulated week itself and counted the triggering interval in the job; a code review caught both, and the corrected numbers are above.) Why it loses: "first reading below threshold" waits through the evening peak and then often hits the deadline at a bad time (12–19 of 21 jobs per region), while midday requests are already clean. The upside exists (oracle), but capturing it needs a forecast or a historical time-of-day profile, not a fixed threshold. This is the main design finding to act on next.

## Limits

Gross SCADA output, no rooftop solar, no imports: a region's intensity ignores power imported from neighbours (matters for SA, TAS, VIC). Historical days use today's generator registry.

Average (not marginal) intensity; a simplification that should be stated plainly.

## Next (tomorrow)

- Replace the fixed-threshold policy: choose the start time from a historical time-of-day profile per region (and weekday/weekend), or from AEMO pre-dispatch. Re-run the simulation; the oracle numbers above are the ceiling.
- Add a `plan` command ("cleanest start in the next N hours").
- Test the Action on GitHub; add the chart once there is a positive result to show.

## Stretch

Day-ahead window prediction from AEMO pre-dispatch.

## Definition of done

- [ ] Hero GIF or screenshot at the top of this README
- [x] Live demo link or one-command run (`uv run carbon-aware-au now`)
- [ ] "How I know it's right" section filled in with real results
- [ ] Tests passing in CI, badge added
- [ ] "Limits" section written
- [ ] Licence chosen, repo description and topics set
- [ ] Pinned on GitHub profile and added to guinerve.github.io
- [ ] Added to `career-radar/data/cv/portfolio.json`
