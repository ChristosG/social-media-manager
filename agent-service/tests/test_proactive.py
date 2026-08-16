import uuid, json, pytest
from datetime import datetime, timezone, date, timedelta
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.repo import ledger as led, scheduled_posts as sp

pytestmark = pytest.mark.usefixtures("db_pool")


def _h(org): return {"X-User-Id": str(uuid.uuid4()), "X-Tenant-Id": org}


class _Fake:
    async def ainvoke(self, *a, **k):
        return type("M", (), {"content": json.dumps([
            {"title": "Fresh idea one", "angle": "angle one"},
            {"title": "Volunteer spotlight", "angle": "angle two"},
        ])})()


async def test_this_week_returns_suggestions_excluding_existing(monkeypatch):
    org = str(uuid.uuid4())
    await led.create_post(org, "Volunteer spotlight", "b", status="suggested")  # existing -> must be excluded
    from app.api import proactive as pro
    monkeypatch.setattr(pro, "_model_for_proactive", lambda: _Fake())  # see note below
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/proactive/this-week", headers=_h(org))
        assert r.status_code == 200
        body = r.json()
        titles = [s["title"] for s in body["suggestions"]]
        assert "Fresh idea one" in titles
        assert "Volunteer spotlight" not in titles    # deduped against the ledger
        assert isinstance(body["gaps"], list) and len(body["gaps"]) >= 1   # week mostly empty


async def test_this_week_never_500s_without_model(monkeypatch):
    org = str(uuid.uuid4())
    from app.api import proactive as pro
    def boom(): raise RuntimeError("model down")
    monkeypatch.setattr(pro, "_model_for_proactive", boom)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/proactive/this-week", headers=_h(org))
        assert r.status_code == 200
        assert r.json()["suggestions"] == []   # graceful: no model -> no ideas, but gaps still returned
