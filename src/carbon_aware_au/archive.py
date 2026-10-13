"""Historical 5-minute intensity from AEMO's SCADA archive, for validation and what-if charts."""

from __future__ import annotations

from datetime import date

import pandas as pd
from nem import NemClient
from nem.archive import load_scada_day
from nem.client import REGIONS
from nem.mms import parse_mms

__all__ = ["intensity_series", "load_day_scada", "published_daily", "validate_day"]

load_day_scada = load_scada_day

def intensity_series(scada: pd.DataFrame, generators: pd.DataFrame) -> pd.DataFrame:
    """Per interval and region: generation (MW), emissions (t CO2e/h) and intensity (g/kWh)."""
    df = scada.merge(generators[["duid", "region", "ef_t_per_mwh"]], on="duid", how="inner")
    df = df[df["mw"] > 0].copy()
    df["t_per_h"] = df["mw"] * df["ef_t_per_mwh"]
    g = df.groupby(["interval_end", "region"], as_index=False).agg(mw=("mw", "sum"), t_per_h=("t_per_h", "sum"))
    g["g_per_kwh"] = g["t_per_h"] / g["mw"] * 1000
    return g[g["region"].isin(REGIONS)]


def published_daily(day: date, client: NemClient | None = None) -> pd.DataFrame:
    """AEMO's published CDEII daily summary (region, energy MWh, emissions t, intensity t/MWh)."""
    client = client or NemClient()
    text = client._get(f"{client.base_url}/Reports/Current/CDEII/CO2EII_SUMMARY_RESULTS.CSV").decode("utf-8", "replace")
    t = parse_mms(text)["CO2EII.PUBLISHING"]
    t = t[t["SETTLEMENTDATE"].dt.date == day]
    if t.empty:
        raise ValueError(f"AEMO's current CDEII summary has no figures for {day}; it holds recent days only")
    t = t.rename(columns={"REGIONID": "region", "TOTAL_SENT_OUT_ENERGY": "energy_mwh",
                          "TOTAL_EMISSIONS": "emissions_t", "CO2E_INTENSITY_INDEX": "published_t_per_mwh"})
    return t[["region", "energy_mwh", "emissions_t", "published_t_per_mwh"]]


def validate_day(day: date, client: NemClient | None = None) -> pd.DataFrame:
    """Compare our daily average intensity with AEMO's published CDEII figure, per region."""
    client = client or NemClient()
    series = intensity_series(load_day_scada(day), client.generators())
    series["energy_mwh"] = series["mw"] / 12  # 5-minute intervals
    series["emissions_t"] = series["t_per_h"] / 12
    ours = series.groupby("region", as_index=False).agg(our_energy_mwh=("energy_mwh", "sum"), our_emissions_t=("emissions_t", "sum"))
    ours["our_g_per_kwh"] = ours["our_emissions_t"] / ours["our_energy_mwh"] * 1000
    pub = published_daily(day, client)
    pub["published_g_per_kwh"] = pub["published_t_per_mwh"] * 1000
    out = ours.merge(pub, on="region")
    out["diff_g_per_kwh"] = out["our_g_per_kwh"] - out["published_g_per_kwh"]
    out["diff_pct"] = out["diff_g_per_kwh"] / out["published_g_per_kwh"].where(out["published_g_per_kwh"] > 0) * 100
    return out
