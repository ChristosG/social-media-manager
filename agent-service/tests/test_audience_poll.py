"""The audience_poll handler snapshots follower counts for every connected account (follower count needs
only basic page/IG access, NOT the insights scope), so the Followers KPI has data."""
import uuid
import pytest
from app.worker import handlers, registry
from app.repo import connections as cr, post_metrics as pm
from app.social import insights_connector as ic
from app.db.pool import org_tx

pytestmark = pytest.mark.asyncio
ORG = "1d000000-0000-0000-0000-000000000001"


class _Ctx:
    def __init__(self, org_id):
        self.org_id = org_id


async def test_audience_poll_records_follower_snapshot(db_pool, monkeypatch):
    async def fake_list(org):
        return [{"id": "aaaaaaaa-0000-0000-0000-000000000001", "provider": "facebook",
                 "external_id": "page1", "scopes": "pages_read_engagement"}]
    async def fake_token(org, cid):
        return "tok"
    async def fake_followers(provider, ext, token):
        return 1204
    monkeypatch.setattr(cr, "list_connections", fake_list)
    monkeypatch.setattr(cr, "get_token", fake_token)
    monkeypatch.setattr(ic, "fetch_follower_count", fake_followers)

    handler = registry.get("audience_poll")
    assert handler is not None
    await handler(_Ctx(ORG), {})

    async with org_tx(ORG) as c:
        row = await c.fetchrow("SELECT provider, followers FROM audience_snapshots WHERE org_id=$1", __import__("uuid").UUID(ORG))
    assert row["provider"] == "facebook" and row["followers"] == 1204


async def test_audience_poll_records_even_without_insights_scope(db_pool, monkeypatch):
    """An IG account lacking instagram_manage_insights must STILL get a Followers snapshot — followers_count
    is available under instagram_basic. The old insights_capable gate wrongly left such accounts at 0."""
    org = str(uuid.uuid4())

    async def fake_list(o):
        return [{"id": "aaaaaaaa-0000-0000-0000-000000000002", "provider": "instagram",
                 "external_id": "ig2", "scopes": "instagram_basic"}]  # no instagram_manage_insights

    async def fake_token(o, cid):
        return "tok"

    async def fake_followers(provider, ext, token):
        return 42

    monkeypatch.setattr(cr, "list_connections", fake_list)
    monkeypatch.setattr(cr, "get_token", fake_token)
    monkeypatch.setattr(ic, "fetch_follower_count", fake_followers)
    await registry.get("audience_poll")(_Ctx(org), {})

    async with org_tx(org) as c:
        row = await c.fetchrow("SELECT provider, followers FROM audience_snapshots WHERE org_id=$1",
                               uuid.UUID(org))
    assert row["provider"] == "instagram" and row["followers"] == 42
