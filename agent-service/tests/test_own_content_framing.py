from app.sources import retrieve


def test_news_hits_framed_untrusted_with_citation():
    hits = [{"url": "https://news.gr/a", "title": "Tax", "text": "VAT news", "kind": "web", "score": 0.7}]
    block = retrieve.format_sources_block(hits)
    assert "UNTRUSTED" in block and "CITE" in block and "https://news.gr/a" in block


def test_own_posts_framed_as_voice_reference():
    hits = [{"url": "https://instagram.com/p/abc", "title": None, "text": "Meet Luna, adopted today!",
             "kind": "instagram", "score": 0.7}]
    block = retrieve.format_sources_block(hits)
    assert "OWN past social posts" in block and "voice" in block.lower()
    assert "UNTRUSTED" not in block            # own posts are not framed as untrusted news
    assert "Meet Luna" in block


def test_mixed_shows_both_sections():
    hits = [
        {"url": "https://instagram.com/p/1", "title": None, "text": "Our gala recap", "kind": "instagram", "score": 0.7},
        {"url": "https://news.gr/x", "title": "Econ", "text": "growth 2%", "kind": "web", "score": 0.6},
    ]
    block = retrieve.format_sources_block(hits)
    assert "OWN past social posts" in block and "UNTRUSTED" in block
