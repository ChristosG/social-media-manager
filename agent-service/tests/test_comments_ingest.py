import uuid
import pytest
from app.comments import ingest
from app.repo import connections as cr, comments as comment_repo, org_settings as os_repo, memory as mem_repo

pytestmark = pytest.mark.asyncio

ENGAGE_FB = "pages_show_list,pages_read_engagement,pages_manage_engagement"


def _fake_comments(*ids):
    return [{"external_id": i, "post_external_id": "P1", "message": "love it", "author_name": "Sam",
             "permalink": "https://fb/c/" + i, "commented_at": "2026-06-10T10:00:00+00:00"} for i in ids]


async def _engage_conn(org):
    return await cr.create_connection(org, "facebook", "PAGE1", "Our Page", "tok-xyz", scopes=ENGAGE_FB)


async def test_draft_mode_drafts_every_new_comment(db_pool, monkeypatch):
    org = str(uuid.uuid4())
    await _engage_conn(org)
    monkeypatch.setattr(ingest.cc, "fetch_comments", lambda *a, **k: _async(_fake_comments("C1", "C2")))
    monkeypatch.setattr(ingest.comment_reply, "draft_reply", lambda *a, **k: _async("Thank you!"))
    posted = []
    monkeypatch.setattr(ingest.cc, "post_reply", lambda *a, **k: _async(posted.append(1) or {"id": "R"}))

    out = await ingest.ingest_org_comments(org, force=True)
    assert out["new"] == 2 and out["drafted"] == 2 and out["auto_replied"] == 0
    assert posted == []                                  # auto-reply OFF -> nothing posted
    rows = await comment_repo.list_for(org, status="open")
    assert len(rows) == 2 and all(r["reply_text"] == "Thank you!" for r in rows)


async def test_ingest_is_idempotent(db_pool, monkeypatch):
    org = str(uuid.uuid4())
    await _engage_conn(org)
    monkeypatch.setattr(ingest.cc, "fetch_comments", lambda *a, **k: _async(_fake_comments("C1")))
    monkeypatch.setattr(ingest.comment_reply, "draft_reply", lambda *a, **k: _async("hi"))
    first = await ingest.ingest_org_comments(org, force=True)
    second = await ingest.ingest_org_comments(org, force=True)
    assert first["new"] == 1 and second["new"] == 0     # same comment never re-drafted


async def test_auto_mode_posts_safe_replies(db_pool, monkeypatch):
    org = str(uuid.uuid4())
    await _engage_conn(org)
    await os_repo.set_auto_reply_safe(org, True)
    monkeypatch.setattr(ingest.cc, "fetch_comments", lambda *a, **k: _async(_fake_comments("C1")))
    monkeypatch.setattr(ingest.comment_reply, "draft_reply", lambda *a, **k: _async("You're welcome!"))
    monkeypatch.setattr(ingest.comment_reply, "classify_safety",
                        lambda *a, **k: _async({"safe": True, "confidence": 0.95, "reason": "thanks"}))
    monkeypatch.setattr(ingest.cc, "post_reply", lambda *a, **k: _async({"id": "REPLY1"}))

    out = await ingest.ingest_org_comments(org, force=True)
    assert out["auto_replied"] == 1 and out["drafted"] == 0
    [row] = await comment_repo.list_for(org, status="replied")
    assert row["reply_external_id"] == "REPLY1" and row["reply_mode"] == "auto"


async def test_auto_mode_drafts_when_unsafe(db_pool, monkeypatch):
    org = str(uuid.uuid4())
    await _engage_conn(org)
    await os_repo.set_auto_reply_safe(org, True)
    monkeypatch.setattr(ingest.cc, "fetch_comments", lambda *a, **k: _async(_fake_comments("C1")))
    monkeypatch.setattr(ingest.comment_reply, "draft_reply", lambda *a, **k: _async("We'll fix it"))
    monkeypatch.setattr(ingest.comment_reply, "classify_safety",
                        lambda *a, **k: _async({"safe": False, "confidence": 0.2, "reason": "complaint"}))
    posted = []
    monkeypatch.setattr(ingest.cc, "post_reply", lambda *a, **k: _async(posted.append(1) or {"id": "R"}))

    out = await ingest.ingest_org_comments(org, force=True)
    assert out["drafted"] == 1 and out["auto_replied"] == 0 and posted == []   # unsafe -> draft, not posted


async def test_auto_on_clears_existing_draft_backlog(db_pool, monkeypatch):
    """The bug the user hit: a comment drafted while auto-reply was OFF must auto-post once the toggle is
    turned ON and we poll again — even though it is no longer a 'new' comment."""
    org = str(uuid.uuid4())
    await _engage_conn(org)
    monkeypatch.setattr(ingest.cc, "fetch_comments", lambda *a, **k: _async(_fake_comments("C1")))
    monkeypatch.setattr(ingest.comment_reply, "draft_reply", lambda *a, **k: _async("Thank you!"))
    # 1) auto OFF -> drafts C1, leaves it open
    first = await ingest.ingest_org_comments(org, force=True)
    assert first["drafted"] == 1 and first["auto_replied"] == 0
    assert (await comment_repo.list_for(org, status="open"))[0]["external_id"] == "C1"
    # 2) turn auto ON, re-poll: C1 is NOT new, but the backlog pass auto-posts it
    await os_repo.set_auto_reply_safe(org, True)
    monkeypatch.setattr(ingest.comment_reply, "classify_safety",
                        lambda *a, **k: _async({"safe": True, "confidence": 0.95, "reason": "thanks"}))
    monkeypatch.setattr(ingest.cc, "post_reply", lambda *a, **k: _async({"id": "R1"}))
    second = await ingest.ingest_org_comments(org, force=True)
    assert second["new"] == 0 and second["auto_replied"] == 1
    [row] = await comment_repo.list_for(org, status="replied")
    assert row["external_id"] == "C1" and row["reply_mode"] == "auto"


async def test_unsafe_comment_is_classified_only_once(db_pool, monkeypatch):
    """The idle-vLLM burn: an OPEN comment the classifier rates UNSAFE must be classified at most ONCE.
    Before the fix, every poll re-ran the LLM safety classifier over the whole open backlog forever, so a
    static backlog of N drafts cost N LLM calls every poll, around the clock, with no user activity."""
    org = str(uuid.uuid4())
    await _engage_conn(org)
    await os_repo.set_auto_reply_safe(org, True)
    monkeypatch.setattr(ingest.cc, "fetch_comments", lambda *a, **k: _async(_fake_comments("C1")))
    monkeypatch.setattr(ingest.comment_reply, "draft_reply", lambda *a, **k: _async("We'll look into it"))
    calls = []
    monkeypatch.setattr(ingest.comment_reply, "classify_safety",
                        lambda *a, **k: (calls.append(1),
                                         _async({"safe": False, "confidence": 0.2, "reason": "complaint"}))[1])
    monkeypatch.setattr(ingest.cc, "post_reply", lambda *a, **k: _async({"id": "R"}))

    await ingest.ingest_org_comments(org, force=True)            # poll 1: classify C1 once -> unsafe -> open
    monkeypatch.setattr(ingest.cc, "fetch_comments", lambda *a, **k: _async([]))  # no new comments after
    await ingest.ingest_org_comments(org, force=True)            # poll 2: must NOT re-classify the backlog
    await ingest.ingest_org_comments(org, force=True)            # poll 3
    assert len(calls) == 1, f"classifier re-ran {len(calls)}x; must classify each comment once"
    [row] = await comment_repo.list_for(org, status="open")      # still a human-review draft (unchanged UX)
    assert row["external_id"] == "C1" and row["reply_text"] == "We'll look into it"


async def test_banned_topic_blocks_autopost_even_when_classifier_says_safe(db_pool, monkeypatch):
    """Defense-in-depth: even if the LLM safety gate is fooled (or just wrong), a reply that mentions a
    banned topic must never be auto-posted publicly — it falls back to a human-reviewed draft."""
    org = str(uuid.uuid4())
    await _engage_conn(org)
    await os_repo.set_auto_reply_safe(org, True)
    await mem_repo.create_entry(org, "banned_topic", {"topic": "politics"}, key="politics")
    monkeypatch.setattr(ingest.cc, "fetch_comments", lambda *a, **k: _async(_fake_comments("C1")))
    monkeypatch.setattr(ingest.comment_reply, "draft_reply",
                        lambda *a, **k: _async("Thanks — and yes, we do take a stand on politics!"))
    # Classifier is compromised/wrong and rubber-stamps it as safe.
    monkeypatch.setattr(ingest.comment_reply, "classify_safety",
                        lambda *a, **k: _async({"safe": True, "confidence": 0.99, "reason": "looks fine"}))
    posted = []
    monkeypatch.setattr(ingest.cc, "post_reply", lambda *a, **k: _async(posted.append(1) or {"id": "R"}))

    out = await ingest.ingest_org_comments(org, force=True)
    assert posted == []                                  # banned topic -> never auto-posted
    assert out["auto_replied"] == 0
    [row] = await comment_repo.list_for(org, status="open")   # left open for human review
    assert "politics" in row["reply_text"]


async def test_throttle_skips_until_forced(db_pool, monkeypatch):
    org = str(uuid.uuid4())
    await _engage_conn(org)
    monkeypatch.setattr(ingest.cc, "fetch_comments", lambda *a, **k: _async(_fake_comments("C1")))
    monkeypatch.setattr(ingest.comment_reply, "draft_reply", lambda *a, **k: _async("hi"))
    await ingest.ingest_org_comments(org, force=True)                 # sets comments_polled_at
    throttled = await ingest.ingest_org_comments(org, force=False)    # within window
    assert throttled["status"] == "throttled"


async def test_no_engage_connection_is_noop(db_pool, monkeypatch):
    org = str(uuid.uuid4())
    # publish-only scopes -> not engage-capable -> feature dormant
    await cr.create_connection(org, "facebook", "PAGE1", "Page", "tok", scopes="pages_manage_posts")
    out = await ingest.ingest_org_comments(org, force=True)
    assert out["connections"] == 0 and out["new"] == 0


def _async(value):
    async def _coro():
        return value
    return _coro()
