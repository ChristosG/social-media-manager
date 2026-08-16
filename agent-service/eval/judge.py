"""LLM-as-judge: score a piece of assistant output against a rubric, 1-5, with a reason.

We grade the *qualities the brief cares about* — brand-voice adherence, per-platform
adaptation, novelty (no repeated ideas) — that a plain assertion can't capture. The judge
is the same self-hosted Qwen, run at temperature 0 and asked for strict JSON. Self-judging
has known bias (a model tends to like its own style), so we keep the rubric concrete and
pair every LLM score with a deterministic check where one exists (see scenario_eval.py).
"""
import json
import re

from app.llm.client import build_chat_model


_JUDGE_SYSTEM = (
    "You are a strict evaluator of social-media copy for nonprofits. "
    "You return ONLY compact JSON: {\"score\": <int 1-5>, \"reason\": \"<one sentence>\"}. "
    "5 = fully meets the criterion, 1 = clearly fails. Be critical; do not inflate."
)


async def judge(criterion: str, content: str, *, context: str = "") -> dict:
    """Score `content` against `criterion`. Returns {'score': int, 'reason': str}."""
    model = build_chat_model(enable_thinking=False, temperature=0.0)
    prompt = (
        f"CRITERION: {criterion}\n"
        + (f"\nCONTEXT (for reference):\n{context}\n" if context else "")
        + f"\nOUTPUT TO JUDGE:\n{content}\n\nReturn the JSON verdict now."
    )
    resp = await model.ainvoke([("system", _JUDGE_SYSTEM), ("user", prompt)])
    return _parse(resp.content)


def _parse(text: str) -> dict:
    """Best-effort JSON extraction (the model occasionally wraps it in prose/fences)."""
    if isinstance(text, list):  # some chat models return content as parts
        text = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            d = json.loads(m.group(0))
            score = int(d.get("score", 0))
            return {"score": max(1, min(5, score)), "reason": str(d.get("reason", "")).strip()}
        except (ValueError, TypeError):
            pass
    return {"score": 0, "reason": f"unparseable judge output: {text[:120]!r}"}
