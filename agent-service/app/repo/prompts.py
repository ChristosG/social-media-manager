"""Per-org prompt overrides (the editable prompts in Studio → Prompts)."""
import uuid

from app.db.pool import org_tx
from app.agent.prompts import PROMPTS, DEFAULTS, KEYS


async def get_overrides(org_id: str) -> dict[str, str]:
    """{key: template} for the org's overridden prompts only (missing key => use the default)."""
    async with org_tx(org_id) as c:
        rows = await c.fetch("SELECT key, template FROM prompt_overrides")
    return {r["key"]: r["template"] for r in rows if r["key"] in KEYS}


async def list_effective(org_id: str) -> list[dict]:
    """The full registry for the editor: default + current (effective) template + overridden flag."""
    overrides = await get_overrides(org_id)
    return [{
        "key": p["key"], "label": p["label"], "description": p["description"],
        "placeholders": p["placeholders"], "default": p["default"],
        "template": overrides.get(p["key"], p["default"]),
        "is_overridden": p["key"] in overrides,
    } for p in PROMPTS]


async def set_override(org_id: str, key: str, template: str) -> None:
    if key not in KEYS:
        raise ValueError(f"unknown prompt key: {key}")
    async with org_tx(org_id) as c:
        await c.execute(
            "INSERT INTO prompt_overrides(org_id, key, template) VALUES($1, $2, $3) "
            "ON CONFLICT (org_id, key) DO UPDATE SET template = $3, updated_at = now()",
            uuid.UUID(org_id), key, template)


async def reset_override(org_id: str, key: str) -> bool:
    async with org_tx(org_id) as c:
        res = await c.execute("DELETE FROM prompt_overrides WHERE key = $1", key)
    return res.endswith("1")
