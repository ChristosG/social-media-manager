"""Campaign planning helpers: deterministic date spread + angle dedup + robust angle parsing. The LLM
proposes angle ideas; these helpers make the plan well-formed (distinct, non-repeating, evenly dated)."""
import json
import re
from datetime import date, timedelta


def _flatten_angles(items: list) -> list[str]:
    """Normalise a list of parsed items (strings or {title/angle} objects) into clean angle strings:
    unwrap dicts, strip wrapping quotes and a trailing comma the model leaves inside the quotes, drop junk."""
    out: list[str] = []
    for it in items:
        if isinstance(it, dict):
            it = str(it.get("title") or it.get("angle") or next(iter(it.values()), ""))
        if not isinstance(it, str):
            continue
        s = it.strip().strip('"').strip().rstrip(",").strip()
        if len(s) > 3:
            out.append(s)
    return out


def parse_angles(content: str) -> list[str]:
    """Robustly extract angle strings from an LLM response that is SUPPOSED to be a JSON array of strings but
    routinely isn't. Local models emit malformed JSON — commas INSIDE the quotes, all on one line, e.g.
    `["Meet the team," "Show the work,"]` — which used to defeat json.loads AND the bracket slice, leaving a
    naive line-split to collapse the whole array into ONE blob slot. Tiers, first win returns:
      1) strict json.loads        2) json.loads of the [...] slice (markdown fences / leading prose)
      3) quoted-string regex      4) newline split (unquoted bullets)
    The regex tier is the one that recovers the malformed single-line case correctly."""
    content = (content or "").strip()
    candidates = [content]
    if "[" in content and "]" in content:
        candidates.append(content[content.find("["): content.rfind("]") + 1])
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except Exception:
            continue
        if isinstance(data, list):
            flat = _flatten_angles(data)
            if len(flat) >= 2:
                return flat
    # 3) Quoted-string regex — pulls each "…" out even when the delimiters between them are wrong.
    flat = _flatten_angles(re.findall(r'"([^"]+)"', content))
    if len(flat) >= 2:
        return flat
    # 4) Newline split — last resort for bullet/numbered lists with no quotes.
    lines = [re.sub(r'^[\s\-*\d.>]+', "", ln) for ln in content.splitlines()]
    return _flatten_angles([ln for ln in lines if ln.strip()])


def spread_dates(start: date, count: int, cadence_days: int = 3) -> list[date]:
    return [start + timedelta(days=i * cadence_days) for i in range(count)]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


def _overlap(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(len(sa), len(sb))


def dedup_angles(angles: list[str], existing_titles: list[str]) -> list[str]:
    seen = {_norm(t) for t in existing_titles}
    out: list[str] = []
    for a in angles:
        n = _norm(a)
        if not n or n in seen:
            continue
        if any(_overlap(n, _norm(k)) >= 0.7 for k in out):
            continue
        out.append(a)
        seen.add(n)
    return out
