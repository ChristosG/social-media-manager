from app.security.context import timezone_var
from app.graph.context import build_system_prompt


def test_today_line_uses_user_timezone():
    tok = timezone_var.set("America/Los_Angeles")
    try:
        sp = build_system_prompt([], None, [])
        assert "America/Los_Angeles" in sp
        assert "Today's date is" in sp
    finally:
        timezone_var.reset(tok)


def test_today_line_falls_back_to_utc_on_bad_tz():
    tok = timezone_var.set("Not/ARealZone")
    try:
        sp = build_system_prompt([], None, [])
        assert "(UTC)" in sp
    finally:
        timezone_var.reset(tok)


def test_today_line_utc_when_no_timezone():
    sp = build_system_prompt([], None, [])
    assert "(UTC)" in sp
