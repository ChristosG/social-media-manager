"""Derive a campaign post's end-to-end lifecycle stage from its ledger row + latest scheduled_post.

Stages: drafting → drafted → approved → scheduled → posted (or failed). Pure (no I/O) so it's trivially
testable and can be reused by the campaign-enrichment endpoint and anywhere else that shows post progress."""

STAGES = ("drafting", "drafted", "approved", "scheduled", "posted", "failed")


def _first(result: dict | None, key: str) -> str | None:
    """First per-target value for `key` (e.g. a permalink or error) in a {target: {...}} result map."""
    for v in (result or {}).values():
        if isinstance(v, dict) and v.get(key):
            return str(v[key])
    return None


def lifecycle_for(post: dict | None, sp: dict | None) -> dict:
    """Map (ledger post, latest scheduled_post) → {stage, scheduled_at, published_at, permalink, error}."""
    out = {"stage": "drafting", "scheduled_at": None, "published_at": None, "permalink": None, "error": None}
    if post is None or post.get("status") == "drafting":
        return out
    out["stage"] = "approved" if post.get("status") == "approved" else "drafted"
    if not sp:
        return out
    status = sp.get("status")
    if status == "published":
        out.update(stage="posted", scheduled_at=sp.get("scheduled_at"),
                   published_at=sp.get("updated_at") or sp.get("scheduled_at"),
                   permalink=_first(sp.get("result"), "permalink"))
    elif status == "failed":
        out.update(stage="failed", scheduled_at=sp.get("scheduled_at"),
                   error=_first(sp.get("result"), "error") or "publish failed")
    elif status in ("pending", "publishing"):
        out.update(stage="scheduled", scheduled_at=sp.get("scheduled_at"))
    # canceled (or anything else) → stays 'drafted'
    return out
