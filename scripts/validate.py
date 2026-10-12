"""Compare our intensity estimate with AEMO's published CDEII daily figures.

  uv run python scripts/validate.py 2026-09-21 2026-09-22 ...
"""
import sys
from datetime import date

import pandas as pd

from carbon_aware_au.archive import validate_day

pd.set_option("display.width", 200)
days = [date.fromisoformat(a) for a in sys.argv[1:]] or [date(2026, 9, 28)]
frames = []
for d in days:
    f = validate_day(d)
    f.insert(0, "date", d)
    frames.append(f)
all_ = pd.concat(frames)
cols = ["date", "region", "our_g_per_kwh", "published_g_per_kwh", "diff_g_per_kwh", "diff_pct", "our_energy_mwh", "energy_mwh"]
print(all_[cols].round(1).to_string(index=False))
print("\nMean absolute error (g/kWh):", round(all_["diff_g_per_kwh"].abs().mean(), 1))
print("Mean absolute % error (regions with published > 0):", round(all_["diff_pct"].abs().mean(), 1))
print("Correlation across region-days:", round(all_["our_g_per_kwh"].corr(all_["published_g_per_kwh"]), 4))
