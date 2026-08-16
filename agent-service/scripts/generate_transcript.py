"""Generate the required 7-step scenario transcript by driving the real agent graph
(real self-hosted Qwen, split-role test DB) and writing docs/transcript-7-step-scenario.md.

Run from the agent-service dir with the venv:
    DATABASE_URL=postgresql://npo_app:changeme@localhost:55432/npo \
    MIGRATION_DATABASE_URL=postgresql://npo_owner:changeme@localhost:55432/npo \
    LLM_BASE_URL=http://localhost:6888/v1 \
    .venv/bin/python scripts/generate_transcript.py
"""
import asyncio
import os
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://npo_app:changeme@localhost:55432/npo")
os.environ.setdefault("MIGRATION_DATABASE_URL", "postgresql://npo_owner:changeme@localhost:55432/npo")
os.environ.setdefault("LLM_BASE_URL", "http://localhost:6888/v1")
os.environ.setdefault("JWT_PUBLIC_KEY", "")

from langchain_core.messages import HumanMessage  # noqa: E402
from app.config import get_settings  # noqa: E402
get_settings.cache_clear()
from app.db.migrate import run_migrations  # noqa: E402
from app.db import pool as dbpool  # noqa: E402
from app.db.pool import org_tx  # noqa: E402
from app.security.context import set_identity  # noqa: E402
from app.graph.graph import build_graph  # noqa: E402
import app.agent.tools as tool_mod  # noqa: E402

tool_mod._model = None  # force the real Qwen, not a test fake

ORG_NAME = "Paws & Tails Rescue"
STEPS = [
    "Suggest some posts for us.",
    "Let's go with the first one, write it for LinkedIn.",
    "Too corporate — we're warm and grassroots. Redo it.",
    "Now give me an Instagram version.",
    "What programs does our org actually run?",
    "Which posts have we worked on, and what's the status of each?",
    "Suggest another post for next month.",
]


async def seed(org: str) -> None:
    async with org_tx(org) as conn:
        await conn.execute(
            "INSERT INTO orgs(id, name) VALUES($1, $2) ON CONFLICT DO NOTHING",
            uuid.UUID(org), ORG_NAME,
        )
        await conn.execute(
            """INSERT INTO org_profile(org_id, mission, one_liner, audience, regions)
               VALUES($1, $2, $3, $4, $5)
               ON CONFLICT (org_id) DO UPDATE SET mission = EXCLUDED.mission""",
            uuid.UUID(org),
            "We rescue, rehabilitate, and rehome abandoned dogs and cats across central Texas.",
            "A volunteer-run animal rescue in central Texas.",
            "Local pet adopters, volunteers, and small-business sponsors.",
            ["Texas"],
        )
        for name, desc in [
            ("Foster-to-Adopt", "Temporary foster homes that transition into permanent adoptions."),
            ("Mobile Vaccination Clinics", "Free monthly vaccination and microchip clinics in underserved neighborhoods."),
            ("Senior Pet Sanctuary", "Lifetime care for senior animals who are unlikely to be adopted."),
        ]:
            await conn.execute(
                "INSERT INTO programs(org_id, name, description) VALUES($1, $2, $3)",
                uuid.UUID(org), name, desc,
            )


async def main() -> None:
    await run_migrations()       # as npo_owner
    await dbpool.init_pool()     # as npo_app
    org = str(uuid.uuid4())
    set_identity("demo-user", org)
    await seed(org)

    g = build_graph()
    history: list = []
    seen_tool_ids: set[str] = set()
    out_lines: list[str] = [
        "# 7-Step Scenario Transcript",
        "",
        f"**Organization:** {ORG_NAME} — seeded with a mission profile + 3 programs (as an onboarded org would have).  ",
        "**Model:** Qwen 3.5-9B, self-hosted via vLLM (thinking-off, tool-calling).  ",
        "**Agent:** the production LangGraph ReAct graph, driven turn-by-turn.  ",
        "**DB:** per-org Postgres with FORCE row-level security; the runtime role is DML-only (npo_app).",
        "",
        "Each turn lists the tools the agent chose to call, then its reply. The brand-voice "
        "correction at step 3 persists to steps 4 and 7; the ledger is populated as posts are "
        "suggested/drafted; step 6 reads that ledger back.",
        "",
        "---",
        "",
    ]

    for i, step in enumerate(STEPS, 1):
        history = history + [HumanMessage(step)]
        out = await g.ainvoke(
            {"messages": history, "org_id": org, "system_prompt": ""},
            {"recursion_limit": 12},
        )
        history = out["messages"]
        # Collect tool calls newly issued this turn (by tool_call id).
        turn_tools: list[str] = []
        for m in history:
            for call in (getattr(m, "tool_calls", None) or []):
                cid = call.get("id") or f"{call.get('name')}-{len(seen_tool_ids)}"
                if cid not in seen_tool_ids:
                    seen_tool_ids.add(cid)
                    turn_tools.append(call.get("name", "?"))
        reply = (history[-1].content or "").strip()
        tools_str = ", ".join(f"`{t}`" for t in turn_tools) if turn_tools else "_(none — answered directly)_"
        out_lines += [
            f"### {i}. User",
            f"> {step}",
            "",
            f"**Tools called:** {tools_str}",
            "",
            "**Assistant:**",
            "",
            reply if reply else "_(empty)_",
            "",
            "---",
            "",
        ]
        print(f"[{i}/7] tools={turn_tools} reply_len={len(reply)}")

    # Footer: what stuck in memory + the ledger, as evidence.
    from app.repo import memory as mem_repo, ledger as ledger_repo
    voices = await mem_repo.list_entries(org, "brand_voice")
    posts = await ledger_repo.list_posts(org)
    voice_val = voices[0]["value"] if voices else None
    if isinstance(voice_val, dict):
        voice_str = voice_val.get("descriptor") or voice_val.get("value") or str(voice_val)
    else:
        voice_str = str(voice_val) if voice_val is not None else "(none)"
    out_lines += [
        "## Evidence (persisted state after the run)",
        "",
        f"- **Brand voice learned:** \"{voice_str}\" — a row in `memory_entries`, injected into every later turn",
        f"- **Ledger entries:** {len(posts)} post(s) tracked — "
        + ", ".join(f"\"{p['title']}\" ({p['status']})" for p in posts[:8]),
        "",
    ]

    # Appendix: the actual draft text the agent wrote — proves the voice transformation,
    # not just the tool routing (the inline replies sometimes summarize instead of pasting).
    async with org_tx(org) as conn:
        drafts = await conn.fetch(
            "SELECT title, COALESCE(platform, '—') AS platform, status, content "
            "FROM posts WHERE content IS NOT NULL AND length(trim(content)) > 0 "
            "ORDER BY updated_at"
        )
    if drafts:
        out_lines += ["---", "", "## Appendix — the drafts the agent actually wrote", ""]
        for d in drafts:
            out_lines += [
                f"### \"{d['title']}\" — {d['platform']} ({d['status']})",
                "",
                d["content"].strip(),
                "",
                "---",
                "",
            ]

    repo_root = Path(__file__).resolve().parents[2]
    dest = repo_root / "docs" / "transcript-7-step-scenario.md"
    dest.write_text("\n".join(out_lines))
    print(f"\nWrote {dest}")
    await dbpool.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
