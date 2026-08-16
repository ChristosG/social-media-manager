import uuid
import pytest
from app.db.pool import org_tx

pytestmark = pytest.mark.asyncio


async def test_sources_documents_chunks_exist_and_vector_works(db_pool):
    org = str(uuid.uuid4())
    async with org_tx(org) as c:
        sid = await c.fetchval(
            "INSERT INTO sources(org_id, kind, name, config) VALUES($1,'web','T','{}'::jsonb) RETURNING id",
            uuid.UUID(org))
        did = await c.fetchval(
            "INSERT INTO documents(org_id, source_id, url, content_hash) VALUES($1,$2,'http://x','h') RETURNING id",
            uuid.UUID(org), sid)
        vec = "[" + ",".join(["0.01"] * 2560) + "]"
        await c.execute(
            "INSERT INTO chunks(org_id, document_id, ord, text, embedding) VALUES($1,$2,0,'hello',$3::vector)",
            uuid.UUID(org), did, vec)
        dist = await c.fetchval("SELECT embedding <=> $1::vector FROM chunks LIMIT 1", vec)
    assert dist is not None and abs(dist) < 1e-6
