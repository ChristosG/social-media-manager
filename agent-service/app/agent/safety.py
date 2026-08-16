"""Deterministic content-safety checks that run as a ground-truth gate, independent of the LLM.

Banned topics are conveyed to the model as a soft prompt instruction ("Never mention: X"), but a 9B
occasionally ignores it. `contains_banned` is the cheap, testable backstop that the caller runs on
generated text BEFORE any irreversible side effect (publishing, auto-replying). It is intentionally
conservative about false positives — it matches a banned topic only at word/phrase boundaries, so
"art" never trips on "start" — because a wrongly-blocked benign reply just falls back to human review.
"""
import re
from functools import lru_cache


@lru_cache(maxsize=512)
def _topic_pattern(topic: str) -> re.Pattern | None:
    """A word-boundary regex for one banned topic. Cached because banned lists are small and stable."""
    t = topic.strip().lower()
    if not t:
        return None
    # \b around the whole (possibly multi-word) phrase; collapse internal whitespace so
    # "gun  control" in the topic still matches "gun control" in the text.
    escaped = r"\s+".join(re.escape(w) for w in t.split())
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


def contains_banned(text: str, banned_topics: list[str]) -> list[str]:
    """Return the distinct banned topics that appear (as whole words/phrases) in `text`.

    Empty list means the text is clear. Order follows first appearance in `banned_topics`."""
    if not text or not banned_topics:
        return []
    hits: list[str] = []
    for topic in banned_topics:
        pat = _topic_pattern(topic)
        if pat and pat.search(text) and topic not in hits:
            hits.append(topic)
    return hits
