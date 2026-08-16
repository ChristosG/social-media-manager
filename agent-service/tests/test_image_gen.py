import uuid

import pytest

from app.agent import image_gen, tools


async def test_generate_one_stores_and_returns_signed(monkeypatch):
    org = str(uuid.uuid4())
    new_id = str(uuid.uuid4())

    async def fake_flux(*a, **k):
        return (b"\x89PNG-bytes", 7)

    async def fake_create(*a, **k):
        return new_id

    async def fake_voice(_org):
        return (None, [])

    monkeypatch.setattr(image_gen.flux, "generate", fake_flux)
    monkeypatch.setattr(image_gen.images_repo, "create_image", fake_create)
    monkeypatch.setattr(image_gen, "image_url", lambda i, o: f"/img/{i}")
    monkeypatch.setattr(tools, "_voice_and_banned", fake_voice)

    out = await image_gen.generate_one(org, prompt="a clean water well", caption="Meet the women…", platform="")
    assert out == {"id": new_id, "url": f"/img/{new_id}"}


async def test_generate_one_raises_when_flux_down(monkeypatch):
    async def fake_flux(*a, **k):
        return None

    async def fake_voice(_org):
        return (None, [])

    monkeypatch.setattr(image_gen.flux, "generate", fake_flux)
    monkeypatch.setattr(tools, "_voice_and_banned", fake_voice)
    with pytest.raises(RuntimeError):
        await image_gen.generate_one(str(uuid.uuid4()), prompt="x", platform="")
