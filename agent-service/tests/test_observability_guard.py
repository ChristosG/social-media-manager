"""F11 regression: the cross-org trace guard must fail CLOSED on a missing userId.

The detail endpoint trusted `t.get("userId") and t.get("userId") != org_id` — so a trace with no
userId skipped the check entirely and was returned to any admin who knew/guessed its id.
"""
from app.api.observability import _trace_visible_to_org


def test_matching_org_is_visible():
    assert _trace_visible_to_org({"userId": "org-a"}, "org-a") is True


def test_other_org_is_denied():
    assert _trace_visible_to_org({"userId": "org-b"}, "org-a") is False


def test_missing_or_blank_userid_is_denied():
    assert _trace_visible_to_org({}, "org-a") is False
    assert _trace_visible_to_org({"userId": ""}, "org-a") is False
    assert _trace_visible_to_org({"userId": None}, "org-a") is False
