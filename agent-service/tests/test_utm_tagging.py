"""Opt-in UTM tagging: the util appends utm params to outbound links (skipping already-tagged ones), the
setting persists and defaults off, and the toggle endpoint round-trips."""
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.social.utm import tag_links
from app.repo import org_settings as os_repo

pytestmark = pytest.mark.asyncio


def test_tag_links_appends_params():
    out = tag_links("Donate at https://myra.org/give today!", "facebook")
    assert "https://myra.org/give?utm_source=facebook&utm_medium=social&utm_campaign=social_studio" in out
    assert "today!" in out


def test_tag_links_respects_existing_query_and_fragment():
    out = tag_links("See https://x.org/p?ref=1#sec", "instagram")
    assert "https://x.org/p?ref=1&utm_source=instagram&utm_medium=social&utm_campaign=social_studio#sec" in out


def test_tag_links_skips_already_tagged():
    url = "https://x.org/p?utm_source=facebook"
    assert tag_links(f"go {url}", "facebook") == f"go {url}"


def test_tag_links_noop_without_url():
    assert tag_links("no links here", "facebook") == "no links here"


async def test_utm_setting_defaults_off_and_persists(db_pool):
    org = str(uuid.uuid4())
    assert await os_repo.utm_tagging(org) is False
    await os_repo.set_utm_tagging(org, True)
    assert await os_repo.utm_tagging(org) is True
    assert (await os_repo.get(org))["utm_tagging"] is True


async def test_utm_settings_endpoint_roundtrip(db_pool):
    org = str(uuid.uuid4())
    H = {"X-User-Id": str(uuid.uuid4()), "X-Tenant-Id": org}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as cl:
        assert (await cl.get("/social/settings", headers=H)).json()["utm_tagging"] is False
        put = await cl.put("/social/settings", json={"utm_tagging": True}, headers=H)
        assert put.status_code == 200 and put.json()["utm_tagging"] is True
        assert (await cl.get("/social/settings", headers=H)).json()["utm_tagging"] is True
