"""Append utm_* params to outbound links in a caption (opt-in, off by default) so the org can attribute
social traffic in their own analytics. Standard scheme: utm_source=<provider>, utm_medium=social,
utm_campaign=social_studio. A link that already carries utm_source is left untouched (no double-tagging),
and the existing query string / fragment are preserved."""
import re

_URL_RE = re.compile(r"https?://[^\s)<>\]]+", re.IGNORECASE)
_PARAMS = "utm_source={src}&utm_medium=social&utm_campaign=social_studio"


def tag_links(caption: str, provider: str) -> str:
    """Return `caption` with utm params appended to each http(s) URL (skipping any already utm-tagged)."""
    if not caption:
        return caption
    src = (provider or "social").lower()
    params = _PARAMS.format(src=src)

    def _repl(m: re.Match) -> str:
        url = m.group(0)
        if "utm_source=" in url.lower():
            return url
        frag = ""
        if "#" in url:
            url, frag = url.split("#", 1)
            frag = "#" + frag
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}{params}{frag}"

    return _URL_RE.sub(_repl, caption)
