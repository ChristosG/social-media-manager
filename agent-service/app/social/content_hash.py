import hashlib


def content_hash(caption: str, image_ids: list[str]) -> str:
    """Stable, order-independent hash of a post's content for duplicate detection."""
    joined = (caption or "").strip() + "|" + ",".join(sorted(str(i) for i in image_ids))
    return hashlib.sha256(joined.encode()).hexdigest()
