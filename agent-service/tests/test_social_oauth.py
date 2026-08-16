import uuid
import httpx
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.social import oauth
from app.api import social as social_api
from app.repo import connections as cr

pytestmark = pytest.mark.asyncio


def test_state_sign_verify_roundtrip_and_tamper():
    st = oauth.sign_state("org-1", "user-1")
    p = oauth.verify_state(st, "user-1")
    assert p and p["o"] == "org-1" and p["u"] == "user-1"
    assert oauth.verify_state(st + "x", "user-1") is None        # tampered sig
    assert oauth.verify_state(st, "user-2") is None              # wrong user


def test_authorize_url_classic_scope_vs_business_config(monkeypatch):
    base = {"meta_app_id": "appid", "meta_oauth_redirect": "https://x/cb"}
    # classic Facebook Login: raw scopes, no config_id
    monkeypatch.setattr(oauth, "get_settings",
                        lambda: type("S", (), {**base, "meta_login_config_id": ""})())
    classic = oauth.authorize_url("facebook", "st")
    assert "scope=" in classic and "config_id=" not in classic
    # Facebook Login for Business: config_id drives permissions, scope omitted
    monkeypatch.setattr(oauth, "get_settings",
                        lambda: type("S", (), {**base, "meta_login_config_id": "cfg123"})())
    business = oauth.authorize_url("facebook", "st")
    assert "config_id=cfg123" in business and "scope=" not in business


async def test_connect_requires_identity_and_returns_authorize_url(monkeypatch):
    monkeypatch.setattr(oauth, "get_settings", lambda: type("S", (), {
        "meta_app_id": "appid", "meta_app_secret": "sec", "meta_oauth_redirect": "https://x/cb",
        "image_url_secret": "k"})())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        assert (await ac.get("/social/connect/facebook")).status_code == 401   # needs identity
        r = await ac.get("/social/connect/facebook", headers={"x-user-id": "u", "x-tenant-id": str(uuid.uuid4())})
        assert r.status_code == 200 and "facebook.com" in r.json()["authorize_url"] and "state=" in r.json()["authorize_url"]
        assert "social_oauth_nonce" in r.headers.get("set-cookie", "")   # session-binding cookie issued


async def test_callback_stores_connections_from_pages(db_pool, monkeypatch):
    org = str(uuid.uuid4())
    state = oauth.sign_state(org, "u")
    nonce = oauth.state_nonce(state)
    async def fake_exchange(code): return "LONG-LIVED-TOKEN"
    async def fake_granted_scopes(token): return "instagram_basic,instagram_content_publish,pages_show_list,pages_manage_posts"
    async def fake_pages(token):
        return [{"id": "page-1", "name": "Paws Page", "access_token": "PAGE-TOK",
                 "instagram_business_account": {"id": "ig-1", "username": "paws"}}]
    monkeypatch.setattr(social_api.ingest, "schedule_ingest", lambda o, s: None)
    monkeypatch.setattr(social_api.oauth, "exchange_code", fake_exchange)
    monkeypatch.setattr(social_api.oauth, "granted_scopes", fake_granted_scopes)
    monkeypatch.setattr(social_api.oauth, "list_pages", fake_pages)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        # the session cookie (set at connect time) must accompany the callback
        r = await ac.get(f"/social/callback?code=abc&state={state}", cookies={"social_oauth_nonce": nonce})
        # redirects back into the SPA with the outcome in the query string (n=2: page + linked IG)
        assert r.status_code == 303 and r.headers["location"] == "/studio?social=connected&linked=2"
    conns = await cr.list_connections(org)
    provs = {c["provider"] for c in conns}
    assert "facebook" in provs and "instagram" in provs          # both stored from one page


def test_can_publish_checks_scopes():
    from app.repo import connections as cr
    assert cr.can_publish({"provider": "instagram",
                           "scopes": "instagram_basic,instagram_content_publish"}) is True
    assert cr.can_publish({"provider": "instagram", "scopes": "instagram_basic"}) is False
    assert cr.can_publish({"provider": "facebook",
                           "scopes": "pages_show_list,pages_manage_posts"}) is True
    assert cr.can_publish({"provider": "facebook", "scopes": "pages_show_list"}) is False
    assert cr.can_publish({"provider": "instagram", "scopes": None}) is False


async def test_callback_rejected_without_session_cookie(db_pool):
    # OAuth-CSRF guard: a valid signed state with NO matching session cookie must NOT link any account
    org = str(uuid.uuid4())
    state = oauth.sign_state(org, "u")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.get(f"/social/callback?code=abc&state={state}")      # no cookie
        assert r.status_code == 303 and "social=error&reason=invalid" in r.headers["location"]
    assert await cr.list_connections(org) == []                            # nothing was stored


def test_sign_state_carries_popup_flag():
    st = oauth.sign_state("org-1", "user-1", popup=True)
    p = oauth.verify_state(st, "user-1")
    assert p and p.get("p") == 1
    st2 = oauth.sign_state("org-1", "user-1")
    assert (oauth.verify_state(st2, "user-1") or {}).get("p") is None


async def test_connect_popup_param_sets_flag_in_state(monkeypatch):
    monkeypatch.setattr(oauth, "get_settings", lambda: type("S", (), {
        "meta_app_id": "appid", "meta_app_secret": "sec", "meta_oauth_redirect": "https://x/cb",
        "meta_login_config_id": "", "image_url_secret": "k"})())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.get("/social/connect/facebook?popup=1",
                         headers={"x-user-id": "u", "x-tenant-id": str(uuid.uuid4())})
        assert r.status_code == 200
        from urllib.parse import urlparse, parse_qs
        state = parse_qs(urlparse(r.json()["authorize_url"]).query)["state"][0]
        assert (oauth.verify_state(state, None) or {}).get("p") == 1


async def test_callback_popup_returns_postmessage_html(db_pool, monkeypatch):
    org = str(uuid.uuid4())
    state = oauth.sign_state(org, "u", popup=True)
    nonce = oauth.state_nonce(state)
    monkeypatch.setattr(social_api.ingest, "schedule_ingest", lambda o, s: None)
    async def fake_exchange(code): return "TOK"
    async def fake_scopes(token): return "instagram_basic,pages_show_list"
    async def fake_pages(token):
        return [{"id": "page-1", "name": "P", "access_token": "PT",
                 "instagram_business_account": {"id": "ig-1", "username": "p"}}]
    monkeypatch.setattr(social_api.oauth, "exchange_code", fake_exchange)
    monkeypatch.setattr(social_api.oauth, "granted_scopes", fake_scopes)
    monkeypatch.setattr(social_api.oauth, "list_pages", fake_pages)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.get(f"/social/callback?code=abc&state={state}",
                         cookies={"social_oauth_nonce": nonce})
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "window.close()" in r.text and "postMessage" in r.text and "connected:2" in r.text
    conns = await cr.list_connections(org)
    assert {c["provider"] for c in conns} == {"facebook", "instagram"}


async def test_callback_popup_error_returns_html(db_pool):
    state = oauth.sign_state("org-1", "u", popup=True)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        r = await ac.get(f"/social/callback?error=denied&state={state}")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "error:denied" in r.text and "window.close()" in r.text
