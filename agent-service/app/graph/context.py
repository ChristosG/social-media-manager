from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.agent.prompts import DEFAULTS
from app.security.context import current_timezone


def _today_line() -> str:
    """Ground the model in the user's LOCAL date when the webapp forwarded a tz; UTC otherwise.
    Any bad/unknown tz falls back to UTC — this must never raise."""
    tz = current_timezone()
    if tz:
        try:
            now = datetime.now(ZoneInfo(tz))
            return f"Today's date is {now:%Y-%m-%d} ({tz})."
        except Exception:
            pass
    return f"Today's date is {datetime.now(timezone.utc):%Y-%m-%d} (UTC)."


def build_system_prompt(memory: list[dict], profile: dict | None, recent_titles: list[str],
                        content_types: list[dict] | None = None, skill_prompts: list[dict] | None = None,
                        persona: str | None = None, agent_mode: bool = False,
                        programs: list[dict] | None = None) -> str:
    # The persona + tool-guidance block is an editable prompt (Studio → Prompts, key `system_persona`);
    # the rest of this function appends the org's data-driven context (voice, banned, mission, ledger…).
    #
    # agent_mode separates "how the assistant BEHAVES" from "how the POSTS read". The agent node (the
    # planner/"brain") runs with agent_mode=True: brand voice + style rules are framed as content the
    # drafting TOOLS apply, NOT as instructions for the agent itself — otherwise a strong rule like
    # "write in pirate language" makes the model role-play in chat and stop calling tools. The drafting
    # tools (draft_post / suggest_posts) build their prompts with agent_mode=False and carry the full voice.
    lines = [persona or DEFAULTS["system_persona"]]
    # Ground the model in the real date so it stops guessing stale years for campaign dates,
    # "this week", "happening soon", etc. — in the user's local tz when known.
    lines.append(_today_line())
    voice = next((m["value"] for m in memory if m["kind"] == "brand_voice"), None)
    if voice:
        desc = voice.get("descriptor") if isinstance(voice, dict) else str(voice)
        if agent_mode:
            lines.append(f"The posts you create use this brand voice: {desc}. The drafting tools apply it "
                         "automatically — in your OWN replies to the user, write plainly and professionally "
                         "in normal English. Never role-play the brand voice in conversation.")
        else:
            lines.append(f"BRAND VOICE: {desc}. Always write in this voice.")
    banned = [m["value"].get("topic", m.get("key")) if isinstance(m["value"], dict) else m["value"]
              for m in memory if m["kind"] == "banned_topic"]
    if banned:
        lines.append(f"BANNED TOPICS (never mention): {', '.join(str(b) for b in banned if b)}.")
    pillars = [m["value"].get("name", m.get("key")) if isinstance(m["value"], dict) else m["value"]
               for m in memory if m["kind"] == "content_pillar"]
    if pillars:
        lines.append(f"CONTENT PILLARS: {', '.join(str(p) for p in pillars if p)}.")

    def _free(m, *keys):
        v = m["value"]
        if isinstance(v, dict):
            return next((v[k] for k in keys if v.get(k)), m.get("key"))
        return v
    # Durable style rules / CTA preferences the user has taught (e.g. "always sign off with 🐾",
    # "end fundraising posts with our donation link"). Allowed in the schema and editable in Studio;
    # injected here so they actually shape every draft.
    rules = [_free(m, "rule", "text") for m in memory if m["kind"] == "style_rule"]
    rules = [str(r) for r in rules if r]
    if rules and not agent_mode:
        # In agent_mode we OMIT style rules from the brain's prompt entirely — they reach the caption
        # writer via draft_post's directives, and listing them here only tempts the model to perform them.
        lines.append("STYLE RULES (always follow): " + "; ".join(rules) + ".")
    ctas = [_free(m, "cta", "text") for m in memory if m["kind"] == "cta_pref"]
    ctas = [str(c) for c in ctas if c]
    if ctas:
        if agent_mode:
            lines.append("CALL-TO-ACTION PREFERENCES (the drafting tools add these to posts): " + "; ".join(ctas) + ".")
        else:
            lines.append("CALL-TO-ACTION PREFERENCES: " + "; ".join(ctas) + ".")
    # Durable org facts the user has taught (e.g. "we are a tech company") — context for every turn.
    facts = [_free(m, "fact", "text") for m in memory if m["kind"] == "fact"]
    facts = [str(f) for f in facts if f]
    if facts:
        lines.append("ORG FACTS (keep in mind): " + "; ".join(facts) + ".")
    if profile and profile.get("name"):
        lines.append(f"ORGANIZATION NAME: {profile['name']}. Refer to the org by this name or as 'we'/'our "
                     "team' — speak as part of it. NEVER write a placeholder like '[Organization Name]'.")
    if profile and profile.get("mission"):
        lines.append(f"ORG MISSION: {profile['mission']}.")
    if profile and profile.get("audience"):
        lines.append(f"AUDIENCE: {profile['audience']}.")
    if profile and profile.get("default_platform"):
        lines.append(f"PRIMARY PLATFORM: the org mainly posts on {profile['default_platform']} — when the "
                     "user asks for a post without naming a platform, default to this one.")
    # The org's actual PROGRAMS/services — the single most important grounding for on-point posts. Without
    # this the model writes generic feel-good copy ("a post for my programs" can't reflect programs it never
    # sees). Listed so suggest_posts/draft_post can anchor ideas + captions in real offerings.
    if programs:
        parts = []
        for p in programs[:8]:
            name = (p.get("name") or "").strip()
            desc = (p.get("description") or "").strip()
            if name:
                parts.append(f"{name} — {desc}" if desc else name)
        if parts:
            lines.append("ORG PROGRAMS / SERVICES (ground posts in these; reference the relevant one by "
                         "name): " + "; ".join(parts) + ".")
    if recent_titles:
        lines.append("RECENTLY WORKED-ON POSTS (avoid repeating): " + "; ".join(recent_titles[:10]) + ".")
    if content_types:
        parts = []
        for c in content_types:
            cfg = c.get("config") if isinstance(c.get("config"), dict) else {}  # tolerate a non-object config
            desc = cfg.get("description")
            parts.append(f"{c['name']} — {desc}" if desc else c["name"])
        lines.append("AVAILABLE CONTENT TYPES (draw from these when suggesting/drafting): " + "; ".join(parts) + ".")
    if skill_prompts:
        for s in skill_prompts:
            cfg = s.get("config") if isinstance(s.get("config"), dict) else {}
            instr = cfg.get("instruction") or cfg.get("text")
            if instr:
                lines.append(f"SKILL · {s['name']}: {instr}")
    return "\n".join(lines)
