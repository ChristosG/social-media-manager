import math
import httpx
import pytest
from app.sources import embed

pytestmark = pytest.mark.asyncio


def _fake_transport(dim=2560):
    def handler(request: httpx.Request):
        import json as _j
        body = _j.loads(request.content)
        inputs = body["input"]
        inputs = inputs if isinstance(inputs, list) else [inputs]
        data = [{"embedding": [0.0] * (dim - 1) + [float(i + 1)]} for i, _ in enumerate(inputs)]
        return httpx.Response(200, json={"data": data})
    return httpx.MockTransport(handler)


async def test_embed_texts_normalizes(monkeypatch):
    monkeypatch.setattr(embed, "_transport", _fake_transport())
    out = await embed.embed_texts(["a", "b"])
    assert len(out) == 2 and len(out[0]) == 2560
    assert math.isclose(math.sqrt(sum(v * v for v in out[0])), 1.0, rel_tol=1e-6)


async def test_embed_query_uses_instruction(monkeypatch):
    seen = {}
    def handler(request):
        import json as _j
        seen["input"] = _j.loads(request.content)["input"]
        return httpx.Response(200, json={"data": [{"embedding": [1.0] + [0.0] * 2559}]})
    monkeypatch.setattr(embed, "_transport", httpx.MockTransport(handler))
    await embed.embed_query("what is the tax bill")
    payload = seen["input"] if isinstance(seen["input"], str) else seen["input"][0]
    assert "Instruct:" in payload and "what is the tax bill" in payload
