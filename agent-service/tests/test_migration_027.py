import pytest
from app.db.pool import org_tx
import uuid

pytestmark = pytest.mark.asyncio
ORG = "11111111-1111-1111-1111-111111111111"


async def test_refine_columns_and_revisions_table_exist(db_pool):
    async with org_tx(ORG) as c:
        col = await c.fetchval(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='posts' AND column_name='refine_suggestions'")
        assert col == 1
        tbl = await c.fetchval(
            "SELECT 1 FROM information_schema.tables WHERE table_name='post_revisions'")
        assert tbl == 1
        forced = await c.fetchval(
            "SELECT relforcerowsecurity FROM pg_class WHERE relname='post_revisions'")
        assert forced is True
