import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.repo import profile as profile_repo


def _h(org): return {"X-User-Id": str(uuid.uuid4()), "X-Tenant-Id": org}


@pytest.mark.usefixtures("db_pool")
async def test_profile_upsert_and_get():
    org = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/profile", headers=_h(org))).json()["profile"] is None
        await c.put("/profile", json={"mission": "End ocean plastic", "regions": ["TX", "FL"]}, headers=_h(org))
        p = (await c.get("/profile", headers=_h(org))).json()["profile"]
        assert p["mission"] == "End ocean plastic" and p["regions"] == ["TX", "FL"]


@pytest.mark.usefixtures("db_pool")
async def test_upsert_profile_none_regions_defaults_to_empty_on_insert():
    """Fix 1: INSERT with regions=None must default to '{}' (NOT NULL), not error."""
    org = str(uuid.uuid4())
    # First upsert — fresh org, regions=None → INSERT path; must not raise and must give []
    result = await profile_repo.upsert_profile(org, "Mission", None, None, None)
    assert result["regions"] == [], f"expected [] on first insert with None regions, got {result['regions']!r}"


@pytest.mark.usefixtures("db_pool")
async def test_upsert_profile_none_regions_preserves_existing_on_update():
    """Fix 1 + COALESCE on UPDATE: passing None regions must preserve the existing value."""
    org = str(uuid.uuid4())
    # Insert with a real regions list
    await profile_repo.upsert_profile(org, "Mission", None, None, ["Texas"])
    # Second upsert — regions=None → UPDATE path; COALESCE must keep ["Texas"]
    result = await profile_repo.upsert_profile(org, None, None, None, None)
    assert result["regions"] == ["Texas"], (
        f"expected ['Texas'] after None-regions update, got {result['regions']!r}"
    )
