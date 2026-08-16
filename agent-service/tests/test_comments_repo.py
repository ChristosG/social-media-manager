import uuid
import pytest
from app.repo import comments as cr, org_settings as os_repo, scheduled_posts as sp

pytestmark = pytest.mark.asyncio


def _c(ext, **kw):
    return {"external_id": ext, "message": kw.get("message", "nice!"),
            "post_external_id": kw.get("post", "POST1"), "author_name": kw.get("author", "Sam"),
            "permalink": kw.get("permalink", "https://fb.com/c/" + ext),
            "commented_at": kw.get("commented_at", "2026-06-07T10:00:00+00:00")}


async def test_upsert_is_idempotent_and_returns_only_new(db_pool):
    org, conn = str(uuid.uuid4()), str(uuid.uuid4())
    new1 = await cr.upsert_many(org, conn, "facebook", [_c("A"), _c("B")])
    assert {c["external_id"] for c in new1} == {"A", "B"}
    # Re-ingesting A with a new C: only C is returned as new (A is a no-op) — drafts happen once per comment.
    new2 = await cr.upsert_many(org, conn, "facebook", [_c("A"), _c("C")])
    assert {c["external_id"] for c in new2} == {"C"}
    assert len(await cr.list_for(org)) == 3


async def test_newest_commented_at_is_the_since_cursor(db_pool):
    org, conn = str(uuid.uuid4()), str(uuid.uuid4())
    await cr.upsert_many(org, conn, "facebook", [
        _c("A", commented_at="2026-06-01T00:00:00+00:00"),
        _c("B", commented_at="2026-06-05T00:00:00+00:00")])
    newest = await cr.newest_commented_at(org, conn)
    assert newest.isoformat() == "2026-06-05T00:00:00+00:00"


async def test_reply_is_exactly_once(db_pool):
    org, conn = str(uuid.uuid4()), str(uuid.uuid4())
    [c] = await cr.upsert_many(org, conn, "facebook", [_c("A")])
    assert await cr.mark_replied(org, c["id"], "thanks!", "REPLY1", "draft") is True
    # A second attempt (double-click / racing worker) must not double-post.
    assert await cr.mark_replied(org, c["id"], "thanks again", "REPLY2", "auto") is False
    got = await cr.get(org, c["id"])
    assert got["status"] == "replied" and got["reply_external_id"] == "REPLY1"


async def test_ignore_only_open(db_pool):
    org, conn = str(uuid.uuid4()), str(uuid.uuid4())
    [c] = await cr.upsert_many(org, conn, "facebook", [_c("A")])
    assert await cr.ignore(org, c["id"]) is True
    assert await cr.ignore(org, c["id"]) is False
    assert (await cr.get(org, c["id"]))["status"] == "ignored"


async def test_status_filter(db_pool):
    org, conn = str(uuid.uuid4()), str(uuid.uuid4())
    rows = await cr.upsert_many(org, conn, "facebook", [_c("A"), _c("B")])
    await cr.ignore(org, rows[0]["id"])
    assert len(await cr.list_for(org, status="open")) == 1
    assert len(await cr.list_for(org, status="ignored")) == 1


async def test_list_for_attaches_parent_post_context(db_pool):
    """A comment on a post we published carries that post's caption (+ image ids) for the inbox chip;
    a comment with no linked post gets post=None."""
    org, conn = str(uuid.uuid4()), str(uuid.uuid4())
    row = await sp.create(org, targets=[{"provider": "facebook", "connection_id": conn}],
                          caption="Our big day at the shelter!", image_ids=[],
                          content_hash="h1", scheduled_at_now=True, created_by=str(uuid.uuid4()), post_id=None)
    linked = _c("A"); linked["scheduled_post_id"] = row["id"]
    await cr.upsert_many(org, conn, "facebook", [linked, _c("B")])
    by_ext = {c["external_id"]: c for c in await cr.list_for(org)}
    assert by_ext["A"]["post"] and by_ext["A"]["post"]["caption"].startswith("Our big day")
    assert by_ext["B"]["post"] is None


async def test_org_settings_defaults_and_toggle(db_pool):
    org = str(uuid.uuid4())
    assert (await os_repo.get(org))["auto_reply_safe"] is False   # default with no row
    await os_repo.set_auto_reply_safe(org, True)
    assert (await os_repo.get(org))["auto_reply_safe"] is True
    await os_repo.touch_comments_polled(org)
    assert await os_repo.comments_polled_at(org) is not None
    assert (await os_repo.get(org))["auto_reply_safe"] is True    # toggle preserved across touch
