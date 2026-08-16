import uuid

import pytest

from app.api import ledger as ledger_api
from app.repo import ledger as repo
from app.security.context import set_identity

pytestmark = pytest.mark.usefixtures("db_pool")


async def _ident(org):
    user = str(uuid.uuid4())
    set_identity(user_id=user, org_id=org)
    return (user, org)


async def test_set_images_replaces_and_404s():
    org = str(uuid.uuid4()); ident = await _ident(org)
    p = await repo.create_post(org, "title", "brief", status="drafted")
    ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    res = await ledger_api.set_images(p["id"], ledger_api.ImagesIn(image_ids=ids), ident=ident)
    assert res == {"ok": True}
    assert (await repo.get_post(org, p["id"]))["image_ids"] == ids

    with pytest.raises(Exception):  # HTTPException 404 for an unknown post
        await ledger_api.set_images(str(uuid.uuid4()), ledger_api.ImagesIn(image_ids=[]), ident=ident)


async def test_generate_appends_image(monkeypatch):
    org = str(uuid.uuid4()); ident = await _ident(org)
    p = await repo.create_post(org, "title", "brief", status="drafted")
    new_id = str(uuid.uuid4())

    async def fake_gen(o, **k):
        return {"id": new_id, "url": f"/img/{new_id}"}

    monkeypatch.setattr(ledger_api.image_gen, "generate_one", fake_gen)
    out = await ledger_api.generate_post_image(p["id"], ledger_api.GenIn(prompt="a well"), ident=ident)
    assert out == {"id": new_id, "url": f"/img/{new_id}"}
    assert (await repo.get_post(org, p["id"]))["image_ids"] == [new_id]
