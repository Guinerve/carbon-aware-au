"""What would waiting have saved? Replays a week of 5-minute intensity for one region.

For each day and each request time, compare:
  run now      - the job starts at the request time
  wait         - carbon-aware-au wait --below <threshold> --max-wait <h>: starts at the first
                 5-minute reading at or below the threshold, or at the deadline
Jobs last --hours and draw constant power, so only relative CO2 matters.

  uv run python scripts/simulate_week.py NSW1 2026-09-21 7
"""
import sys
from datetime import date, timedelta

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from nem import NemClient

from carbon_aware_au.archive import intensity_series, load_day_scada

region = sys.argv[1] if len(sys.argv) > 1 else "NSW1"
start = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2026, 9, 21)
ndays = int(sys.argv[3]) if len(sys.argv) > 3 else 7
JOB_H, MAX_WAIT_H, PCTL = 1.0, 6.0, 0.30
REQUEST_HOURS = [8, 12, 17]

gens = NemClient().generators()
# one extra day after (jobs can run past midnight) and ndays BEFORE, so the threshold comes from the past
frames = [intensity_series(load_day_scada(start + timedelta(days=i)), gens) for i in range(-ndays, ndays + 1)]
s = pd.concat(frames)
s = s[s["region"] == region].set_index("interval_end").sort_index()["g_per_kwh"]
prior = s[: pd.Timestamp(start)]
threshold = float(prior.quantile(PCTL))  # chosen from the week BEFORE the one simulated: no lookahead

def job_mean(t0):  # mean intensity over the job
    w = s[t0 + pd.Timedelta(minutes=5) : t0 + pd.Timedelta(hours=JOB_H)]  # intervals ending 5..60 min after the start
    return float(w.mean())

rows = []
for i in range(ndays):
    for h in REQUEST_HOURS:
        t0 = pd.Timestamp(start + timedelta(days=i)) + pd.Timedelta(hours=h)
        horizon = s[t0 : t0 + pd.Timedelta(hours=MAX_WAIT_H)]
        clean = horizon[horizon <= threshold]
        t1 = clean.index[0] if len(clean) else t0 + pd.Timedelta(hours=MAX_WAIT_H)
        starts = pd.date_range(t0, t0 + pd.Timedelta(hours=MAX_WAIT_H), freq="5min")
        best = min(job_mean(t) for t in starts)  # hindsight oracle: the cleanest start inside the window
        rows.append({"request": t0, "start_wait": t1, "now": job_mean(t0), "wait": job_mean(t1), "oracle": best, "waited_h": (t1 - t0).total_seconds() / 3600})
df = pd.DataFrame(rows)


def change(x):  # "3.1% less" or "9.5% more"
    return f"{abs(x):.1%} {'less' if x >= 0 else 'more'}"


saving = 1 - df["wait"].sum() / df["now"].sum()
oracle = 1 - df["oracle"].sum() / df["now"].sum()
print(f"region {region}, {len(df)} jobs, threshold {threshold:.0f} g/kWh (P{int(PCTL*100)} of the previous week)")
print(f"mean intensity: run now {df['now'].mean():.0f} g/kWh, wait {df['wait'].mean():.0f} g/kWh  ->  {change(saving)} CO2")
print(f"hindsight oracle (cleanest start in window): {change(oracle)} CO2 than run now")
print(f"mean wait {df['waited_h'].mean():.1f} h, longest {df['waited_h'].max():.1f} h, jobs that hit the deadline: {(df['waited_h'] >= MAX_WAIT_H).sum()}")

fig, ax = plt.subplots(figsize=(10, 4))
sw = s[pd.Timestamp(start) : pd.Timestamp(start) + pd.Timedelta(days=ndays)]
ax.plot(sw.index, sw.values, color="#555", lw=1, label=f"{region} average intensity")
ax.axhline(threshold, color="#1a7f4b", ls="--", lw=1, label=f"threshold {threshold:.0f} g/kWh")
ax.scatter(df["request"], [s.asof(t) for t in df["request"]], color="#cf222e", s=22, zorder=3, label="run at once")
ax.scatter(df["start_wait"], [s.asof(t) for t in df["start_wait"]], color="#1f6feb", s=22, zorder=3, label="carbon-aware-au start")
ax.set_ylabel("g CO₂e / kWh"); ax.set_title(f"{region}: waiting (max {MAX_WAIT_H:.0f} h) compared with running at once: {change(saving)} CO₂ over {len(df)} jobs of 1 h")
ax.legend(loc="upper right", fontsize=8, ncol=2); ax.grid(alpha=.25)
fig.tight_layout(); fig.savefig(f"assets/week-{region.lower()}.png", dpi=140)
