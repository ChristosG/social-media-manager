"""Eval-driven heuristic model routing.

The 9B runs thinking-OFF by default — fast and reliable at structured tool calls. Some turns,
though, genuinely benefit from a deliberate pass: voice corrections, multi-constraint asks,
comparisons, "redo this differently". Rather than make the user reach for a toggle (or pay an
extra LLM round-trip to classify), we read a few cheap, deterministic signals from the turn and
decide. The thresholds here are validated OFFLINE by the eval harness (eval/scenario_eval.py),
which is what makes this "eval-driven" without adding any runtime latency.

`classify()` is a pure function (no I/O) so it's trivially testable and can't fail a request.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Correction / revision cues — the same family draft_post uses to detect a tweak. A correction is
# the canonical "think harder" turn (the model must reconcile a nuanced preference with prior work).
_CORRECTION = re.compile(
    r"\b(too |more |less |instead|redo|rework|again|not quite|isn'?t|doesn'?t|"
    r"warmer|colder|softer|edgier|punchier|simpler|corporate|stiff|generic|bland|off-?brand|"
    r"vague|ambiguous|represent|the voice of|face of (my|our|the)|who we are|feels? (vague|off|wrong)|"
    r"be (my|our) (voice|assistant))\b", re.I)

# Analytical / planning / comparative asks — open-ended reasoning rather than a single action.
_ANALYTICAL = re.compile(
    r"\b(why|how come|compare|versus|vs\.?|trade-?offs?|pros and cons|strategy|strategi[sz]e|"
    r"plan|brainstorm|ideas? for the (month|quarter|year)|which (is|works) better|explain|analy[sz]e)\b", re.I)

# Multiple distinct asks chained in one turn ("write X and also Y, then Z").
_MULTI = re.compile(r"\b(and also|as well as|then (also )?|;|, and )\b", re.I)

_LONG_WORDS = 45   # a long, dense turn usually carries multiple constraints


@dataclass(frozen=True)
class RouteDecision:
    reasoning: bool
    reason: str   # short, human-readable — surfaced in the UI hint and the trace metadata


def classify(message: str, history: list[str] | None = None) -> RouteDecision:
    """Decide whether THIS turn should run with thinking on. Conservative: default OFF (fast),
    flip ON only on a clear complexity signal, so simple turns stay snappy."""
    text = (message or "").strip()
    if not text:
        return RouteDecision(False, "empty")

    if _CORRECTION.search(text):
        return RouteDecision(True, "correction/refinement")
    if _ANALYTICAL.search(text):
        return RouteDecision(True, "analytical/planning")
    if _MULTI.search(text):
        return RouteDecision(True, "multiple constraints")
    if len(text.split()) >= _LONG_WORDS:
        return RouteDecision(True, "long, dense request")

    # A very short reply that follows the assistant ("no, the other one", "make it pop") is usually a
    # correction with the nuance living in the PRIOR turn — give it the deliberate pass.
    if history and len(text.split()) <= 4 and _CORRECTION.search(text):
        return RouteDecision(True, "short correction in context")

    return RouteDecision(False, "straightforward")
