from datetime import datetime, timezone
import trafilatura


def _parse_date(s: str | None):
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s[:19] if len(s) >= 19 and "T" in s else s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def extract_article(html: str, url: str) -> dict | None:
    """Main-content extraction from already-fetched HTML (never fetches — preserves the SSRF guard).
    Returns {title, author, published_at, text} or None when there's no usable article body."""
    if not html:
        return None
    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=False,
                               favor_recall=True, no_fallback=False)
    if not text or len(text.strip()) < 200:
        return None
    title = author = date = None
    try:
        md = trafilatura.extract_metadata(html, default_url=url)
        if md:
            title, author, date = md.title, md.author, md.date
    except Exception:
        pass
    return {"title": title, "author": author, "published_at": _parse_date(date), "text": text.strip()}
