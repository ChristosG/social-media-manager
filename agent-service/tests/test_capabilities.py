import uuid
import pytest
from app.repo import capabilities as repo

pytestmark = pytest.mark.asyncio


async def test_effective_includes_globals_and_org_rows(db_pool):
    org = str(uuid.uuid4())
    await repo.create_capability(org, "platform", "tiktok",
                                 {"label": "TikTok", "max_chars": 2200, "tone": "fun", "hashtags": "3-5"})
    eff = await repo.list_effective(org, "platform")
    names = {c["name"] for c in eff}
    assert "tiktok" in names and "linkedin" in names  # org row + global


async def test_org_override_wins_and_can_disable_global(db_pool):
    org = str(uuid.uuid4())
    await repo.create_capability(org, "platform", "linkedin",
                                 {"label": "LinkedIn", "max_chars": 1500, "tone": "OURS", "hashtags": "1"})
    eff = {c["name"]: c for c in await repo.list_effective(org, "platform")}
    assert eff["linkedin"]["config"]["tone"] == "OURS"  # org row overrides the global
    await repo.create_capability(org, "platform", "facebook", {"label": "Facebook"})
    fb = next(c for c in await repo.list_effective(org, "platform") if c["name"] == "facebook")
    await repo.update_capability(org, fb["id"], enabled=False)
    names = {c["name"] for c in await repo.list_effective(org, "platform")}
    assert "facebook" not in names


async def test_resolve_platform_registry_then_fallback(db_pool):
    org = str(uuid.uuid4())
    await repo.create_capability(org, "platform", "threads", {"label": "Threads", "max_chars": 500, "tone": "casual"})
    assert (await repo.resolve_platform(org, "threads"))[1]["label"] == "Threads"   # from registry
    assert (await repo.resolve_platform(org, "LinkedIn"))[0] == "linkedin"          # global, case-insensitive
    assert await repo.resolve_platform(org, "myspace") is None                      # unknown


async def test_cannot_edit_global_row(db_pool):
    """A global (org_id NULL) row is not matched by the org's UPDATE policy -> 0 rows -> False."""
    org = str(uuid.uuid4())
    a_global = next(c for c in await repo.list_all(org, "platform") if c["is_global"] and c["name"] == "x")
    assert await repo.update_capability(org, a_global["id"], enabled=False) is False


async def test_disabled_global_not_resurrected_by_fallback(db_pool):
    """Disabling a seeded global platform hides it from resolve_platform — no hardcoded resurrection."""
    org = str(uuid.uuid4())
    await repo.create_capability(org, "platform", "facebook", {"label": "Facebook"})
    fb = next(c for c in await repo.list_effective(org, "platform") if c["name"] == "facebook")
    await repo.update_capability(org, fb["id"], enabled=False)
    assert await repo.resolve_platform(org, "facebook") is None
