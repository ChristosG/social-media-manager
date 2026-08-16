import uuid, pytest
from app.social import publish_worker as w
from app.social import publish as pub
from app.repo import connections as cr, scheduled_posts as sp, notifications as nr, ledger as led

pytestmark = pytest.mark.asyncio


async def _ig(org):
    return await cr.create_connection(org, "instagram", "IG_EXT_1", "@x", token="tok",
                                      scopes="instagram_basic,instagram_content_publish")


async def test_run_one_publishes_and_notifies(db_pool, monkeypatch):
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); conn = await _ig(org)
    row = await sp.create(org, targets=[{"provider": "instagram", "connection_id": conn["id"]}],
                          caption="hi", image_ids=[str(uuid.uuid4())], content_hash="h",
                          scheduled_at_now=True, created_by=user, post_id=None)
    async def fake_publish(provider, target_id, page_token, caption, image_jpg_urls):
        assert target_id == "IG_EXT_1"           # uses external_id, not connection id
        return {"id": "MEDIA1", "permalink": "https://instagram.com/p/ok"}
    monkeypatch.setattr(pub, "publish_to_target", fake_publish)
    await w.run_one(org, row["id"])
    done = await sp.get(org, row["id"])
    assert done["status"] == "published"
    assert done["result"][conn["id"]]["id"] == "MEDIA1"
    assert await nr.unread_count(org, None) >= 1


async def test_run_one_marks_ledger_post_posted(db_pool, monkeypatch):
    """A successful publish must flip the linked ledger post to 'posted' (so the workspace + funnel reflect
    it), not leave it stuck at 'drafted'."""
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); conn = await _ig(org)
    post = await led.create_post(org, "t", "b", status="drafted")
    row = await sp.create(org, targets=[{"provider": "instagram", "connection_id": conn["id"]}],
                          caption="hi", image_ids=[str(uuid.uuid4())], content_hash="hpost",
                          scheduled_at_now=True, created_by=user, post_id=post["id"])
    async def fake_publish(*a, **k):
        return {"id": "MEDIAX", "permalink": "https://instagram.com/p/x"}
    monkeypatch.setattr(pub, "publish_to_target", fake_publish)
    await w.run_one(org, row["id"])
    posts = {p["id"]: p for p in await led.list_posts(org)}
    assert posts[post["id"]]["status"] == "posted"


async def test_run_one_is_idempotent(db_pool, monkeypatch):
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); conn = await _ig(org)
    row = await sp.create(org, targets=[{"provider": "instagram", "connection_id": conn["id"]}],
                          caption="hi", image_ids=[str(uuid.uuid4())], content_hash="h2",
                          scheduled_at_now=True, created_by=user, post_id=None)
    calls = {"n": 0}
    async def fake_publish(*a, **k):
        calls["n"] += 1
        return {"id": "M", "permalink": "https://x/p"}
    monkeypatch.setattr(pub, "publish_to_target", fake_publish)
    await w.run_one(org, row["id"])
    await w.run_one(org, row["id"])            # second run: already published, claim returns None
    assert calls["n"] == 1                      # NEVER published twice


async def test_transient_requeues_then_succeeds(db_pool, monkeypatch):
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); conn = await _ig(org)
    row = await sp.create(org, targets=[{"provider": "instagram", "connection_id": conn["id"]}],
                          caption="hi", image_ids=[str(uuid.uuid4())], content_hash="h3",
                          scheduled_at_now=True, created_by=user, post_id=None)
    state = {"fail": True}
    async def fake_publish(*a, **k):
        if state["fail"]:
            raise pub.PublishTransientError("rate limited")
        return {"id": "M2", "permalink": "p"}
    monkeypatch.setattr(pub, "publish_to_target", fake_publish)
    await w.run_one(org, row["id"])
    mid = await sp.get(org, row["id"])
    assert mid["status"] == "pending"          # requeued, NOT failed
    state["fail"] = False
    await w.run_one(org, row["id"])            # retry succeeds (row is pending again, claim works)
    assert (await sp.get(org, row["id"]))["status"] == "published"


async def test_permanent_fails_and_notifies(db_pool, monkeypatch):
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); conn = await _ig(org)
    row = await sp.create(org, targets=[{"provider": "instagram", "connection_id": conn["id"]}],
                          caption="hi", image_ids=[str(uuid.uuid4())], content_hash="h4",
                          scheduled_at_now=True, created_by=user, post_id=None)
    async def fake_publish(*a, **k):
        raise pub.PublishPermanentError("bad image")
    monkeypatch.setattr(pub, "publish_to_target", fake_publish)
    await w.run_one(org, row["id"])
    assert (await sp.get(org, row["id"]))["status"] == "failed"


async def test_exhausted_transient_fails_with_notification(db_pool, monkeypatch):
    # A target that stays transient until attempts are exhausted must end 'failed' AND notify the user
    # (not silently fail). Regression for the worker review finding.
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); conn = await _ig(org)
    row = await sp.create(org, targets=[{"provider": "instagram", "connection_id": conn["id"]}],
                          caption="hi", image_ids=[str(uuid.uuid4())], content_hash="h5",
                          scheduled_at_now=True, created_by=user, post_id=None)
    async def always_transient(*a, **k):
        raise pub.PublishTransientError("rate limited")
    monkeypatch.setattr(pub, "publish_to_target", always_transient)
    for _ in range(w._MAX_ATTEMPTS):          # drive attempts to the cap; each run claims the pending row
        await w.run_one(org, row["id"])
    done = await sp.get(org, row["id"])
    assert done["status"] == "failed"
    fails = [n for n in await nr.list_for(org, None) if n["type"] == "publish_failed"]
    assert len(fails) >= 1                     # user IS told it failed


async def test_run_one_fails_loudly_on_missing_public_origin(db_pool, monkeypatch):
    from app.security import img_sign
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); conn = await _ig(org)
    row = await sp.create(org, targets=[{"provider": "instagram", "connection_id": conn["id"]}],
                          caption="hi", image_ids=[str(uuid.uuid4())], content_hash="h-misconf",
                          scheduled_at_now=True, created_by=user, post_id=None)
    monkeypatch.setattr(img_sign, "get_settings",
                        lambda: type("S", (), {"meta_oauth_redirect": "", "image_url_secret": "x"})())
    await w.run_one(org, row["id"])
    done = await sp.get(org, row["id"])
    assert done["status"] == "failed"
    fails = [n for n in await nr.list_for(org, None) if n["type"] == "publish_failed"]
    assert len(fails) >= 1


async def test_run_one_passes_absolute_image_urls(db_pool, monkeypatch):
    # Regression: worker must hand Meta fully-qualified https:// URLs, not bare paths.
    # META_OAUTH_REDIRECT=https://test.example/... is set in conftest; the public base is https://test.example.
    org = str(uuid.uuid4()); user = str(uuid.uuid4()); conn = await _ig(org)
    img_id = str(uuid.uuid4())
    row = await sp.create(org, targets=[{"provider": "instagram", "connection_id": conn["id"]}],
                          caption="hi", image_ids=[img_id], content_hash="h6",
                          scheduled_at_now=True, created_by=user, post_id=None)
    captured_urls: list[list[str]] = []
    async def fake_publish(provider, target_id, page_token, caption, image_jpg_urls):
        captured_urls.append(list(image_jpg_urls))
        return {"id": "MEDIA2", "permalink": "https://instagram.com/p/abs"}
    monkeypatch.setattr(pub, "publish_to_target", fake_publish)
    await w.run_one(org, row["id"])
    assert len(captured_urls) == 1
    assert len(captured_urls[0]) == 1
    # Every URL handed to Meta must be absolute and on the public host, not a bare path.
    assert captured_urls[0][0].startswith("https://test.example/api/v1/img/")
