"""Average emissions intensity of generation in a NEM region.

intensity (g CO2e/kWh) = sum(MW x emissions factor) / sum(MW), over units generating in the region.
Factors are AEMO's CDEII per-unit factors (t CO2e/MWh), so t/MWh equals kg/kWh and x1000 gives g/kWh.
This is an *average* intensity of local generation, not marginal, and ignores imports.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from nem import NemClient, emissions_intensity, generation_mix, renewable_share
from nem.client import REGIONS


@dataclass(frozen=True)
class Intensity:
    region: str
    g_per_kwh: float
    renewable_share: float
    interval_end: pd.Timestamp


def normalise_region(region: str) -> str:
    r = region.upper().strip()
    if r in {"NSW", "QLD", "VIC", "SA", "TAS"}:
        r += "1"
    if r not in REGIONS:
        raise ValueError(f"Unknown region {region!r}. Use one of {', '.join(REGIONS)}.")
    return r


def intensity_from_units(units: pd.DataFrame, region: str) -> Intensity:
    mix = generation_mix(units, region)
    return Intensity(
        region=region,
        g_per_kwh=emissions_intensity(mix) * 1000,
        renewable_share=renewable_share(mix),
        interval_end=units["interval_end"].iloc[0],
    )


def current_intensity(region: str, client: NemClient | None = None) -> Intensity:
    r = normalise_region(region)
    return intensity_from_units((client or NemClient()).generation_by_unit(), r)
