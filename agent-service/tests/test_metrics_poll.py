import uuid

import pytest

from app.repo import connections as cr, ledger as led, scheduled_posts as sp, post_metrics as pm
from app.security.context import set_identity
from app.social import insights_connector as ic
from app.social import publish as pub
from app.social import publish_worker as w
from app.worker import registry

pytestmark = pytest.mark.asyncio


async def _ig(org):
    return await cr.create_connection(org, "instagram", "IG_EXT_1", "@x", token="tok",
                                      scopes="instagram_basic,instagram_content_publish")


async def _published_post(org, user, monkeypatch, *, ext="MEDIA1"):
    """Seed a ledger post + a scheduled_posts row driven through the real publish worker to 'published'.
    Returns (post_id, connection_id, provider, external_post_id) — the per-target tuple we re-poll."""
    conn = await _ig(org)
    post = await led.create_post(org, "Leo angle", "Leo angle", status="approved")
    row = await sp.create(org, targets=[{"provider": "instagram", "connection_id": conn["id"]}],
                          caption="hi", image_ids=[str(uuid.uuid4())], content_hash=str(uuid.uuid4()),
                          scheduled_at_now=True, created_by=user, post_id=post["id"])

    async def fake_publish(provider, target_id, page_token, caption, image_jpg_urls):
        return {"id": ext, "permalink": "https://instagram.com/p/ok"}
    monkeypatch.setattr(pub, "publish_to_target", fake_publish)
    await w.run_one(org, row["id"])
    done = await sp.get(org, row["id"])
    assert done["status"] == "published"
    return post["id"], conn["id"], "instagram", ext


# ── Step 1: repo ──────────────────────────────────────────────────────────────


async def test_young_published_posts_returns_published_target(db_pool, monkeypatch):
    org = str(uuid.uuid4()); user = str(uuid.uuid4())
    set_identity(user_id=user, org_id=org)
    post_id, cid, provider, ext = await _published_post(org, user, monkeypatch)

    items = await pm.young_published_posts(org, days=14)
    mine = [i for i in items if i["post_id"] == post_id]
    assert len(mine) == 1
    it = mine[0]
    assert it["connection_id"] == cid
    assert it["provider"] == provider
    assert it["external_post_id"] == ext


async def test_young_published_posts_skips_old(db_pool, monkeypatch):
    org = str(uuid.uuid4()); user = str(uuid.uuid4())
    set_identity(user_id=user, org_id=org)
    post_id, _cid, _p, _ext = await _published_post(org, user, monkeypatch)
    # Age the published row past the window.
    from app.db.pool import org_tx
    async with org_tx(org) as c:
        await c.execute("UPDATE scheduled_posts SET updated_at = now() - interval '30 days' "
                        "WHERE post_id=$1", uuid.UUID(post_id))
    items = await pm.young_published_posts(org, days=14)
    assert not [i for i in items if i["post_id"] == post_id]


async def test_record_snapshot_writes_row(db_pool):
    org = str(uuid.uuid4()); user = str(uuid.uuid4())
    set_identity(user_id=user, org_id=org)
    post = await led.create_post(org, "snap", "snap", status="approved")
    await pm.record_snapshot(org, post["id"], None, "instagram", "EXT9",
                             {"reach": 100, "engagement": 5})
    from app.db.pool import org_tx
    async with org_tx(org) as c:
        r = await c.fetchrow("SELECT metrics, provider, external_post_id FROM post_metrics "
                             "WHERE post_id=$1", uuid.UUID(post["id"]))
    assert r is not None
    assert r["provider"] == "instagram" and r["external_post_id"] == "EXT9"
    import json
    metrics = r["metrics"] if isinstance(r["metrics"], dict) else json.loads(r["metrics"])
    assert metrics == {"reach": 100, "engagement": 5}


# ── Step 2: metrics_poll handler ───────────────────────────────────────────────


class _Ctx:
    def __init__(self, org_id):
        self.org_id = org_id


async def test_metrics_poll_handler_records_snapshot(db_pool, monkeypatch):
    import app.worker.handlers  # noqa: F401 — registers the handlers on import
    org = str(uuid.uuid4()); user = str(uuid.uuid4())
    set_identity(user_id=user, org_id=org)
    conn = await _ig(org)
    post = await led.create_post(org, "poll me", "poll me", status="approved")

    async def fake_metrics(provider, ext, token):
        return {"reach": 100, "engagement": 5}
    monkeypatch.setattr(ic, "fetch_post_metrics", fake_metrics)
    monkeypatch.setattr(cr, "get_token", lambda org_id, cid: _async("tok"))

    handler = registry.get("metrics_poll")
    assert handler is not None
    await handler(_Ctx(org), {"post_id": post["id"], "connection_id": conn["id"],
                              "provider": "instagram", "external_post_id": "EXT_POLL"})

    from app.db.pool import org_tx
    import json
    async with org_tx(org) as c:
        r = await c.fetchrow("SELECT metrics FROM post_metrics WHERE post_id=$1 AND external_post_id=$2",
                             uuid.UUID(post["id"]), "EXT_POLL")
    assert r is not None
    metrics = r["metrics"] if isinstance(r["metrics"], dict) else json.loads(r["metrics"])
    assert metrics == {"reach": 100, "engagement": 5}


async def test_metrics_poll_handler_noops_without_token(db_pool, monkeypatch):
    import app.worker.handlers  # noqa: F401
    org = str(uuid.uuid4()); user = str(uuid.uuid4())
    set_identity(user_id=user, org_id=org)
    post = await led.create_post(org, "no token", "no token", status="approved")
    monkeypatch.setattr(cr, "get_token", lambda org_id, cid: _async(None))
    called = {"n": 0}

    async def fake_metrics(*a, **k):
        called["n"] += 1
        return {}
    monkeypatch.setattr(ic, "fetch_post_metrics", fake_metrics)

    handler = registry.get("metrics_poll")
    await handler(_Ctx(org), {"post_id": post["id"], "connection_id": str(uuid.uuid4()),
                              "provider": "instagram", "external_post_id": "X"})
    assert called["n"] == 0  # no token → never calls the Graph API, never records


# ── metrics_sweep handler ──────────────────────────────────────────────────────


async def test_metrics_sweep_enqueues_polls_for_young_posts(db_pool, monkeypatch):
    import app.worker.handlers  # noqa: F401
    from app.repo import jobs
    org = str(uuid.uuid4()); user = str(uuid.uuid4())
    set_identity(user_id=user, org_id=org)
    post_id, cid, provider, ext = await _published_post(org, user, monkeypatch)

    handler = registry.get("metrics_sweep")
    assert handler is not None
    await handler(_Ctx(org), {})

    from app.db.pool import org_tx
    async with org_tx(org) as c:
        n = await c.fetchval("SELECT count(*) FROM jobs WHERE kind='metrics_poll' "
                             "AND payload->>'post_id' = $1", post_id)
    assert n >= 1


# ── Step 4: publish-time enqueue ───────────────────────────────────────────────


async def test_publish_enqueues_followup_polls(db_pool, monkeypatch):
    from app.repo import jobs
    org = str(uuid.uuid4()); user = str(uuid.uuid4())
    set_identity(user_id=user, org_id=org)
    post_id, cid, _provider, ext = await _published_post(org, user, monkeypatch, ext="MEDIA_FOLLOW")

    from app.db.pool import org_tx
    async with org_tx(org) as c:
        rows = await c.fetch("SELECT run_after FROM jobs WHERE kind='metrics_poll' "
                             "AND payload->>'post_id' = $1 AND payload->>'external_post_id' = $2 "
                             "ORDER BY run_after", post_id, ext)
    assert len(rows) == 3  # +24h / +72h / +7d


async def test_publish_without_post_id_enqueues_nothing(db_pool, monkeypatch):
    org = str(uuid.uuid4()); user = str(uuid.uuid4())
    set_identity(user_id=user, org_id=org)
    conn = await _ig(org)
    row = await sp.create(org, targets=[{"provider": "instagram", "connection_id": conn["id"]}],
                          caption="hi", image_ids=[str(uuid.uuid4())], content_hash=str(uuid.uuid4()),
                          scheduled_at_now=True, created_by=user, post_id=None)

    async def fake_publish(*a, **k):
        return {"id": "ADHOC", "permalink": "p"}
    monkeypatch.setattr(pub, "publish_to_target", fake_publish)
    await w.run_one(org, row["id"])

    from app.db.pool import org_tx
    async with org_tx(org) as c:
        n = await c.fetchval("SELECT count(*) FROM jobs WHERE kind='metrics_poll' "
                             "AND payload->>'external_post_id' = $1", "ADHOC")
    assert n == 0  # ad-hoc publish (no ledger post) schedules no polls


async def _async(v):
    return v
