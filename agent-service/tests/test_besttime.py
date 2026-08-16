from datetime import date
from app.agent.besttime import suggested_slots, PLATFORM_WINDOWS


def test_returns_slots_within_the_week_for_platform():
    slots = suggested_slots("instagram", date(2026, 7, 6), count=3)   # Mon 2026-07-06
    assert len(slots) == 3
    for iso in slots:
        assert iso.startswith("2026-07")
    assert slots == sorted(slots) and len(set(slots)) == 3


def test_unknown_platform_falls_back_to_default():
    out = suggested_slots("threads", date(2026, 7, 6), count=2)
    assert len(out) == 2


def test_windows_cover_known_platforms():
    assert {"instagram", "linkedin", "facebook", "x"} <= set(PLATFORM_WINDOWS)
