"""Per-org prompt overrides: persistence, effective merge, reset, and validation."""
import uuid

import pytest

from app.security.context import set_identity
from app.repo import prompts as repo
from app.agent.prompts import DEFAULTS


@pytest.mark.usefixtures("db_pool")
async def test_override_roundtrip_and_reset():
    org = str(uuid.uuid4())
    set_identity("u", org)

    # No overrides → effective == defaults, nothing flagged.
    eff = await repo.list_effective(org)
    assert {p["key"] for p in eff} == set(DEFAULTS)
    assert all(p["template"] == p["default"] and not p["is_overridden"] for p in eff)

    # Set one → it's returned and flagged.
    await repo.set_override(org, "draft_instructions", "Write a tiny {label} post.")
    assert (await repo.get_overrides(org))["draft_instructions"] == "Write a tiny {label} post."
    eff = {p["key"]: p for p in await repo.list_effective(org)}
    assert eff["draft_instructions"]["is_overridden"]
    assert eff["draft_instructions"]["template"] == "Write a tiny {label} post."
    assert not eff["system_persona"]["is_overridden"]

    # Reset → back to default.
    assert await repo.reset_override(org, "draft_instructions") is True
    assert "draft_instructions" not in await repo.get_overrides(org)


@pytest.mark.usefixtures("db_pool")
async def test_unknown_key_rejected():
    org = str(uuid.uuid4())
    set_identity("u", org)
    with pytest.raises(ValueError):
        await repo.set_override(org, "not_a_real_prompt", "x")


@pytest.mark.usefixtures("db_pool")
async def test_overrides_are_org_scoped():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    set_identity("u", a)
    await repo.set_override(a, "suggest_instructions", "A-only template {count}")
    # Org B must not see A's override (RLS).
    set_identity("u", b)
    assert await repo.get_overrides(b) == {}
