from app.agent.lifecycle import lifecycle_for


def test_no_post_is_drafting():
    assert lifecycle_for(None, None)["stage"] == "drafting"


def test_post_still_drafting():
    assert lifecycle_for({"status": "drafting"}, None)["stage"] == "drafting"


def test_drafted_no_schedule():
    lc = lifecycle_for({"status": "drafted"}, None)
    assert lc["stage"] == "drafted" and lc["permalink"] is None


def test_scheduled():
    lc = lifecycle_for({"status": "scheduled"}, {"status": "pending", "scheduled_at": "2026-06-15T12:00:00+00:00"})
    assert lc["stage"] == "scheduled" and lc["scheduled_at"] == "2026-06-15T12:00:00+00:00"


def test_posted_with_permalink():
    sp = {"status": "published", "scheduled_at": "2026-06-15T12:00:00+00:00",
          "updated_at": "2026-06-15T12:00:05+00:00",
          "result": {"instagram": {"permalink": "https://instagram.com/p/abc"}}}
    lc = lifecycle_for({"status": "scheduled"}, sp)
    assert lc["stage"] == "posted"
    assert lc["permalink"] == "https://instagram.com/p/abc"
    assert lc["published_at"] == "2026-06-15T12:00:05+00:00"


def test_failed_with_error():
    sp = {"status": "failed", "scheduled_at": "2026-06-15T12:00:00+00:00",
          "result": {"instagram": {"error": "token expired"}}}
    lc = lifecycle_for({"status": "scheduled"}, sp)
    assert lc["stage"] == "failed" and lc["error"] == "token expired"


def test_canceled_falls_back_to_drafted():
    lc = lifecycle_for({"status": "drafted"}, {"status": "canceled"})
    assert lc["stage"] == "drafted"


def test_approved_no_schedule():
    lc = lifecycle_for({"status": "approved"}, None)
    assert lc["stage"] == "approved"


def test_approved_then_scheduled_advances():
    lc = lifecycle_for({"status": "approved"},
                       {"status": "pending", "scheduled_at": "2026-06-15T12:00:00+00:00"})
    assert lc["stage"] == "scheduled"
