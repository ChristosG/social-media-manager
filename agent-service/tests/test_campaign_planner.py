from datetime import date
from app.agent.campaign import spread_dates, dedup_angles


def test_spread_dates_even_across_range():
    out = spread_dates(date(2026, 7, 6), count=3, cadence_days=3)
    assert out == [date(2026, 7, 6), date(2026, 7, 9), date(2026, 7, 12)]


def test_spread_dates_default_cadence():
    out = spread_dates(date(2026, 7, 6), count=4)
    assert len(out) == 4 and out == sorted(out) and len(set(out)) == 4


def test_dedup_angles_drops_near_duplicates_and_existing():
    angles = ["A family's clean water story", "a family's CLEAN water story",
              "The science of BioSand", "Volunteer spotlight"]
    existing = ["volunteer spotlight"]
    out = dedup_angles(angles, existing)
    assert "The science of BioSand" in out
    assert sum(1 for a in out if "family" in a.lower()) == 1
    assert all("volunteer spotlight" != a.lower() for a in out)


def test_dedup_handles_empty():
    assert dedup_angles([], ["x"]) == []
    assert dedup_angles(["only one"], []) == ["only one"]
