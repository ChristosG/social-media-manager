import re
from urllib.parse import urljoin, urlparse
import feedparser
from app.agent.research import fetch_html, _safe_target

_LINK = re.compile(r'href=["\']([^"\']+)["\']', re.I)
# "article-ish": a path with ≥2 segments and a slug (letter … hyphen … letter) in the last segment.
_SLUG = re.compile(r"/[^/]+/[^/]*[a-z][^/]*-[^/]*[a-z]", re.I)
# Aggregation / index pages (tag, author, category, …) — NOT articles; never ingest these.
_AGG = re.compile(r"^/(tag|tags|author|authors|category|categories|topic|topics|section|sections)/", re.I)
# Strong article signal: a numeric id segment (/3996807/) or a date path (/2026/06/). News sites that
# use these → keep ONLY these (drops topic landing pages); sites without them fall back to all slugs.
_ARTICLE_ID = re.compile(r"/\d{4,}(/|$)|/20\d\d/\d{2}/")


def _prefer_articles(urls: list[str]) -> list[str]:
    """Prefer URLs with a strong article signal (numeric id / date); fall back to all when none qualify."""
    strong = [u for u in urls if _ARTICLE_ID.search(urlparse(u).path)]
    return strong or urls


def _same_section(urls: list[str], base_url: str) -> list[str]:
    """When the source is a SECTION (e.g. /oikonomia), keep only articles under that same section —
    this is 'the latest articles under here', and it drops cross-section ticker/live-data pages
    (e.g. /forex/...) that happen to carry numeric ids. Returns [] when there's no section segment
    (e.g. a homepage), so callers fall back to all links."""
    seg = urlparse(base_url).path.strip("/").split("/")[0] if urlparse(base_url).path.strip("/") else ""
    if not seg:
        return []
    return [u for u in urls if urlparse(u).path.strip("/").split("/")[:1] == [seg]]


def classify(url: str, type_hint: str, html: str, content_type: str) -> str:
    if type_hint in ("single", "section", "rss"):
        return type_hint
    ct = (content_type or "").lower()
    if "xml" in ct or "rss" in ct or re.search(r"(rss|feed|\.xml)(/|$)", url, re.I):
        return "rss"
    # A URL that is ITSELF an article (numeric-id / date path) is a single article — even though article
    # pages link to many related articles, which would otherwise make them look like a section index.
    if _ARTICLE_ID.search(urlparse(url).path):
        return "single"
    links = extract_article_links(html or "", url)
    return "section" if len(links) >= 5 else "single"


def parse_feed_links(xml: str) -> list[str]:
    feed = feedparser.parse(xml)
    return [e.link for e in feed.entries if getattr(e, "link", None)]


def extract_article_links(html: str, base_url: str) -> list[str]:
    host = urlparse(base_url).netloc
    out, seen = [], set()
    for href in _LINK.findall(html):
        if href.startswith(("#", "mailto:", "javascript:")):
            continue
        absu = urljoin(base_url, href)
        p = urlparse(absu)
        if p.scheme not in ("http", "https") or p.netloc != host:
            continue
        if _AGG.search(p.path):          # drop tag/author/category aggregation pages
            continue
        if not _SLUG.search(p.path):
            continue
        if absu not in seen:
            seen.add(absu); out.append(absu)
    return out


async def discover(url: str, type_hint: str = "auto", latest_n: int = 15) -> tuple[str, str | None, list[str]]:
    """Returns (detected_kind, feed_url, article_urls[:latest_n]). Uses the SSRF-guarded fetch_html for
    all network I/O. For 'auto' it fetches the page once to classify, then expands sections via RSS
    (preferred) or on-page article links."""
    if _safe_target(url) is None:
        return ("single", None, [])
    page = await fetch_html(url)                            # RAW full page for link/feed discovery
    kind = classify(url, type_hint, page, "")
    if kind == "single":
        return ("single", None, [url])
    if kind == "rss":
        links = parse_feed_links(page)[:latest_n]
        return ("rss", url, links)
    feed_url = _find_feed(page, url)
    if feed_url and _safe_target(feed_url) is not None:
        feed_xml = await fetch_html(feed_url)
        links = parse_feed_links(feed_xml)[:latest_n]
        if links:
            return ("section", feed_url, links)
    arts = extract_article_links(page, url)
    arts = _same_section(arts, url) or arts          # 'latest articles under THIS section'
    return ("section", None, _prefer_articles(arts)[:latest_n])


def _find_feed(html: str, base_url: str) -> str | None:
    m = re.search(r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*href=["\']([^"\']+)["\']',
                  html, re.I)
    return urljoin(base_url, m.group(1)) if m else None
