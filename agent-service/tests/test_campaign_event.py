from app.security import context


def test_push_campaign_populates_sink():
    sink: list = []
    token = context.campaign_sink_var.set(sink)
    try:
        context.push_campaign("cid-1", "boost donations")
        assert sink == [{"id": "cid-1", "brief": "boost donations"}]
    finally:
        context.campaign_sink_var.reset(token)


def test_push_campaign_noop_without_sink():
    context.campaign_sink_var.set(None)
    context.push_campaign("cid", "b")  # must not raise


def test_push_campaign_ignores_empty_id():
    sink: list = []
    token = context.campaign_sink_var.set(sink)
    try:
        context.push_campaign("", "b")
        assert sink == []
    finally:
        context.campaign_sink_var.reset(token)
