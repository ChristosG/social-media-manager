"""The metrics scheduler fans out the insights jobs daily, per org: every tick it enumerates engage-capable
orgs and — throttled to ~once/day off the latest audience_snapshots.captured_at — enqueues a metrics_sweep
(re-poll young posts) and an audience_poll (snapshot followers). Without this nothing periodically refreshes
insights; they'd only update at publish time or via the manual Refresh button."""
import uuid

import pytest

from app.repo import jobs, post_metrics as pm
from app.social import metrics_scheduler as ms

pytestmark = pytest.mark.usefixtures("db_pool")

# Distinct org ids per test: the shared test DB persists audience_snapshots across test functions/runs
# (migrations are idempotent but don't truncate), so a snapshot one test writes must not leak into another's
# throttle check. ORG_DUE is a fresh uuid each run → guaranteed to have no prior snapshot → always "due".
ORG_DUE = str(uuid.uuid4())
ORG_FRESH = "1d000000-0000-0000-0000-00000000d0e1"  # gets a fresh snapshot each run → always throttled


def _record_enqueue(calls):
    async def _fake(org_id, kind, *, payload=None, dedup_key=None, **kw):
        calls.append((org_id, kind, dedup_key))
        return {"id": str(uuid.uuid4()), "kind": kind, "dedup_key": dedup_key}
    return _fake


async def test_tick_enqueues_both_jobs_when_no_recent_snapshot(monkeypatch):
    """No audience_snapshots row for the org → the org is due, so tick enqueues BOTH insights jobs for it."""
    async def fake_orgs(limit=200):
        return [ORG_DUE]
    calls: list = []
    monkeypatch.setattr(ms, "_engage_orgs", fake_orgs)
    monkeypatch.setattr(jobs, "enqueue", _record_enqueue(calls))

    n = await ms.tick()

    kinds = {c[1] for c in calls}
    assert kinds == {"metrics_sweep", "audience_poll", "import_posts"}
    assert (ORG_DUE, "metrics_sweep", f"sweep-{ORG_DUE}") in calls
    assert (ORG_DUE, "audience_poll", f"aud-{ORG_DUE}") in calls
    assert (ORG_DUE, "import_posts", f"import-{ORG_DUE}") in calls
    assert n == 3


async def test_tick_throttles_when_snapshot_is_fresh(monkeypatch):
    """A just-captured audience_snapshots row makes the org NOT due → tick enqueues nothing (daily throttle)."""
    async def fake_orgs(limit=200):
        return [ORG_FRESH]
    calls: list = []
    monkeypatch.setattr(ms, "_engage_orgs", fake_orgs)
    monkeypatch.setattr(jobs, "enqueue", _record_enqueue(calls))

    # Fresh snapshot (captured_at defaults to now()) → inside the 20h throttle window.
    await pm.record_follower_snapshot(ORG_FRESH, None, "facebook", 1000)

    n = await ms.tick()

    assert calls == []
    assert n == 0
