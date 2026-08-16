"""Automated output-quality eval for the required 7-step scenario.

Runs the canonical conversation against the REAL self-hosted Qwen, then scores the result
two ways:

  • deterministic checks — did the brand-voice correction persist? did suggestions reach the
    ledger? did the "next month" suggestion introduce a genuinely new idea (not a repeat)?
  • LLM-as-judge (eval/judge.py) — graded 1-5 for the qualities assertions can't capture:
    brand-voice adherence, per-platform adaptation, and novelty.

Run it:
    cd agent-service
    DATABASE_URL=postgresql://npo_app:changeme@localhost:55432/npo \
    MIGRATION_DATABASE_URL=postgresql://npo_owner:changeme@localhost:55432/npo \
    LLM_BASE_URL=http://localhost:6888/v1 \
    .venv/bin/python -m eval.scenario_eval

Writes a JSON report to eval/results/ and exits non-zero if the score is below threshold,
so it can gate CI.
"""
import asyncio
import json
import os
import pathlib
import uuid
from datetime import datetime, timezone

# Defaults mirror tests/conftest.py so it "just runs" on the dev box. Override via env.
os.environ.setdefault("DATABASE_URL", "postgresql://npo_app:changeme@localhost:55432/npo")
os.environ.setdefault("MIGRATION_DATABASE_URL", "postgresql://npo_owner:changeme@localhost:55432/npo")
os.environ.setdefault("LLM_BASE_URL", "http://localhost:6888/v1")
# Reach the embedder on the host (compose default name qwen-emb-vllm won't resolve off-cluster).
os.environ.setdefault("EMBED_BASE_URL", "http://localhost:8090/v1")
os.environ.setdefault("META_TOKEN_KEY", "eval-only-meta-token-key-rotate-me-0123456789")
os.environ.setdefault("IMAGE_URL_SECRET", "eval-only-image-url-secret-0123456789")

from langchain_core.messages import HumanMessage  # noqa: E402

from app.db.migrate import run_migrations  # noqa: E402
from app.db import pool as dbpool  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.graph.graph import build_graph  # noqa: E402
from app.agent import router as agent_router  # noqa: E402
from app.security.context import set_identity, draft_sink_var  # noqa: E402
from app.repo import ledger as ledger_repo, memory as mem_repo, profile as profile_repo  # noqa: E402
from eval.judge import judge  # noqa: E402

PASS_THRESHOLD = 3.5   # mean judge score (1-5) required to "pass"

SCENARIO = [
    "Suggest some posts for us.",
    "Let's go with the first one, write it for LinkedIn.",
    "Too corporate — we're warm and grassroots. Redo it.",
    "Now give me an Instagram version.",
    "What programs does our org actually run?",
    "Which posts have we worked on, and what's the status of each?",
    "Suggest another post for next month.",
]


async def _seed_org(org: str):
    """A minimal, realistic org so the Q&A step (5) has something grounded to answer."""
    await profile_repo.upsert_profile(
        org,
        mission="We rescue and rehome stray dogs, and run free spay/neuter clinics.",
        one_liner="A grassroots animal-welfare nonprofit.",
        audience="Local pet lovers and volunteers",
        regions=["Athens"],
    )
    await profile_repo.create_program(org, "Foster Network", "Matches stray dogs with foster homes.")
    await profile_repo.create_program(org, "Free Spay & Neuter Clinic", "Monthly free clinic for strays.")


async def run() -> dict:
    get_settings.cache_clear()
    import app.agent.tools as tool_mod
    tool_mod._model = None  # force the real Qwen, not a test stub

    await run_migrations(os.environ["MIGRATION_DATABASE_URL"])
    await dbpool.init_pool()
    try:
        org = str(uuid.uuid4())
        set_identity("eval-user", org)
        await _seed_org(org)

        g = build_graph()
        history: list = []
        outputs: list[str] = []   # the assistant's chat reply each turn
        captions: list[str] = []  # the actual drafted caption each turn (empty when no draft_post)

        async def turn(text: str) -> str:
            nonlocal history
            # A fresh draft sink per turn captures the EXACT caption draft_post produced — the final
            # chat message is only a wrapper ("I've drafted… want an image?"), so judging that would
            # be unfair. This mirrors how app/api/ws.py harvests the live draft.
            sink: list = []
            draft_sink_var.set(sink)
            history = history + [HumanMessage(text)]
            out = await g.ainvoke({"messages": history, "org_id": org, "system_prompt": ""},
                                  {"recursion_limit": 14})
            history = out["messages"]
            captions.append((sink[-1] if sink else "").strip())
            return out["messages"][-1].content or ""

        # Offline view of the Auto router's decisions across the scenario — this is what makes the
        # routing "eval-driven": we can see/tune which turns it escalates to thinking-on, with zero
        # added latency at runtime (the router is a pure heuristic, not an LLM call).
        routing = [{"turn": i + 1, "step": s, **agent_router.classify(s).__dict__}
                   for i, s in enumerate(SCENARIO)]

        ideas_before = set()
        for i, step in enumerate(SCENARIO):
            outputs.append(await turn(step))
            if i == 0:  # snapshot the first batch of ideas to test novelty later
                ideas_before = {p["title"].strip().lower() for p in await ledger_repo.list_posts(org)}

        # For the draft steps, judge the real caption; fall back to the chat reply if none was captured.
        linkedin = captions[1] or outputs[1]
        instagram = captions[3] or outputs[3]

        # ---- deterministic checks -------------------------------------------------
        voices = await mem_repo.list_entries(org, "brand_voice")
        ledger = await ledger_repo.list_posts(org)
        ideas_after = {p["title"].strip().lower() for p in ledger}
        checks = {
            "voice_correction_persisted": bool(voices) and "grassroots" in str(voices).lower(),
            "suggestions_in_ledger": len(ledger) >= 1,
            "next_month_idea_is_new": len(ideas_after - ideas_before) >= 1,
        }

        # ---- LLM-as-judge ---------------------------------------------------------
        scored = {
            "voice_adherence": await judge(
                "The post is warm and grassroots — NOT corporate or stiff. Personal, community tone.",
                instagram, context="Brand voice the org asked for: warm, grassroots, not corporate."),
            "platform_adaptation": await judge(
                "These are two DISTINCT drafts properly adapted to their platforms "
                "(LinkedIn = professional/longer; Instagram = casual, emoji/hashtags, shorter).",
                f"--- LinkedIn ---\n{linkedin}\n\n--- Instagram ---\n{instagram}"),
            "novelty_next_month": await judge(
                "This new suggestion is a genuinely DIFFERENT idea, not a rephrase of the earlier ones.",
                outputs[6], context=f"Earlier suggestions:\n{outputs[0]}"),
            "qa_grounded": await judge(
                "The answer correctly describes the org's real programs (Foster Network; "
                "Free Spay & Neuter Clinic) without inventing unrelated ones.",
                outputs[4], context="Real programs: Foster Network, Free Spay & Neuter Clinic."),
        }

        judge_scores = [v["score"] for v in scored.values() if v["score"] > 0]
        mean = round(sum(judge_scores) / len(judge_scores), 2) if judge_scores else 0.0
        passed = all(checks.values()) and mean >= PASS_THRESHOLD

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "org_id": org,
            "model": get_settings().llm_model,
            "deterministic_checks": checks,
            "judge_scores": scored,
            "judge_mean": mean,
            "pass_threshold": PASS_THRESHOLD,
            "passed": passed,
            "routing": routing,
            "transcript": [
                {"user": s, "assistant": o, **({"caption": c} if c else {})}
                for s, o, c in zip(SCENARIO, outputs, captions)
            ],
        }
    finally:
        await dbpool.close_pool()


def _print_report(r: dict):
    print("\n" + "=" * 64)
    print(f"  SCENARIO EVAL — {r['model']}   ({r['timestamp']})")
    print("=" * 64)
    print("\n  Deterministic checks:")
    for k, v in r["deterministic_checks"].items():
        print(f"    [{'PASS' if v else 'FAIL'}]  {k}")
    print("\n  LLM-as-judge (1-5):")
    for k, v in r["judge_scores"].items():
        print(f"    {v['score']}/5  {k:<22} — {v['reason']}")
    print(f"\n  Judge mean: {r['judge_mean']}  (threshold {r['pass_threshold']})")
    if r.get("routing"):
        print("\n  Auto-routing decisions (heuristic, offline):")
        for d in r["routing"]:
            print(f"    turn {d['turn']}: {'THINK' if d['reasoning'] else 'fast '} — {d['reason']}  ({d['step']!r})")
    print(f"\n  OVERALL: {'✅ PASS' if r['passed'] else '❌ FAIL'}")
    print("=" * 64 + "\n")


async def _main():
    r = await run()
    _print_report(r)
    out_dir = pathlib.Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    fn = out_dir / f"run-{r['timestamp'].replace(':', '-')}.json"
    fn.write_text(json.dumps(r, indent=2))
    print(f"  report → {fn}\n")
    raise SystemExit(0 if r["passed"] else 1)


if __name__ == "__main__":
    asyncio.run(_main())
