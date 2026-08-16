import pytest
from app.db.pool import org_tx

pytestmark = pytest.mark.asyncio
ORG = "1c000000-0000-0000-0000-000000000001"


async def test_post_metrics_and_audience_tables_and_throttle_col(db_pool):
    async with org_tx(ORG) as c:
        for t in ("post_metrics", "audience_snapshots"):
            assert await c.fetchval("SELECT 1 FROM information_schema.tables WHERE table_name=$1", t) == 1
            assert await c.fetchval("SELECT relforcerowsecurity FROM pg_class WHERE relname=$1", t) is True
        assert await c.fetchval(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='org_settings' AND column_name='insights_refreshed_at'") == 1
