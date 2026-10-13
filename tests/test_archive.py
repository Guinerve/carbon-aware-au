from datetime import date

import pytest

from carbon_aware_au.archive import published_daily

SUMMARY = """C,NEMP.WORLD,CO2EII,AEMO,PUBLIC,2026/10/01,04:00:00
I,CO2EII,PUBLISHING,1,CONTRACTYEAR,WEEKNO,SETTLEMENTDATE,REGIONID,TOTAL_SENT_OUT_ENERGY,TOTAL_EMISSIONS,CO2E_INTENSITY_INDEX
D,CO2EII,PUBLISHING,1,2026,39,2026/09/27 00:00:00,SA1,33853.9,771.9,0.0228
D,CO2EII,PUBLISHING,1,2026,39,2026/09/27 00:00:00,VIC1,124694.9,73345.0,0.5882
"""


class FakeClient:
    base_url = "https://nemweb.example"

    def _get(self, url):
        return SUMMARY.encode()


def test_published_daily_reads_the_requested_day():
    t = published_daily(date(2026, 9, 27), FakeClient())
    assert set(t["region"]) == {"SA1", "VIC1"}
    assert t.loc[t["region"] == "VIC1", "published_t_per_mwh"].item() == pytest.approx(0.5882)


def test_published_daily_fails_loudly_for_a_day_not_in_the_summary():
    # AEMO's "current" CDEII summary only holds recent days. An older day must not give an
    # empty table, which made scripts/validate.py print NaN errors without saying why.
    with pytest.raises(ValueError, match="2026-08-01"):
        published_daily(date(2026, 8, 1), FakeClient())
