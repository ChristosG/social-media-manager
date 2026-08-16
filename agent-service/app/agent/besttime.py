"""Best-time-to-post: a deterministic heuristic of strong posting windows per platform.

Defaults come from widely-cited engagement research (weekday mid-morning / lunch / early-evening).
Returns concrete ISO datetimes within a target week so the calendar can highlight suggested slots.
Pure + testable; a future version can nudge these toward an org's own best-performing historical slots."""
from datetime import date, datetime, time, timedelta

# (weekday 0=Mon .. 6=Sun, hour) windows, best first.
PLATFORM_WINDOWS = {
    "instagram": [(1, 11), (3, 13), (2, 19), (4, 11)],
    "facebook":  [(2, 13), (3, 15), (1, 9), (4, 13)],
    "linkedin":  [(1, 9), (2, 11), (3, 8), (1, 17)],
    "x":         [(0, 9), (2, 12), (4, 17), (1, 8)],
}
_DEFAULT = [(1, 11), (3, 13), (2, 9), (4, 17)]


def suggested_slots(platform: str, week_start: date, count: int = 3,
                    org_windows: list[tuple[int, int]] | None = None) -> list[str]:
    """Concrete suggested datetimes for the week. When `org_windows` is given (the org's own best-performing
    (weekday, hour) slots from measured engagement), those lead; the static priors fill any remainder so we
    always return `count` slots and never drop below the heuristic when an org has little history."""
    windows: list[tuple[int, int]] = list(org_windows or [])
    for w in PLATFORM_WINDOWS.get((platform or "").lower(), _DEFAULT):
        if w not in windows:
            windows.append(w)
    out: list[str] = []
    for wd, hr in windows:
        delta = (wd - week_start.weekday()) % 7
        d = week_start + timedelta(days=delta)
        out.append(datetime.combine(d, time(hour=hr)).isoformat())
        if len(out) >= count:
            break
    return sorted(out)
