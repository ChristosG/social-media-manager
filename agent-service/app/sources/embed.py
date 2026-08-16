import math
import httpx
from app.config import get_settings

# Override in tests with httpx.MockTransport; None → real network.
_transport: httpx.MockTransport | None = None

_QUERY_INSTRUCT = ("Instruct: Given a question, retrieve passages that answer it\nQuery: {q}")


def _normalize(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


async def _post_embeddings(inputs: list[str]) -> list[list[float]]:
    s = get_settings()
    url = s.embed_base_url.rstrip("/") + "/embeddings"
    async with httpx.AsyncClient(timeout=60, transport=_transport) as c:
        r = await c.post(url, json={"model": s.embed_model, "input": inputs})
        r.raise_for_status()
        data = r.json()["data"]
    return [_normalize(d["embedding"]) for d in data]


async def embed_texts(texts: list[str], batch: int = 16) -> list[list[float]]:
    """Embed documents/chunks (raw). Batched + L2-normalized."""
    out: list[list[float]] = []
    for i in range(0, len(texts), batch):
        out.extend(await _post_embeddings(texts[i:i + batch]))
    return out


async def embed_query(query: str) -> list[float]:
    """Embed a search query with the Qwen3-Embedding instruction prefix (asymmetric retrieval)."""
    return (await _post_embeddings([_QUERY_INSTRUCT.format(q=query)]))[0]
