from app.sources import discover


def test_classify_respects_override():
    assert discover.classify("http://x", "single", "", "") == "single"
    assert discover.classify("http://x/feed.xml", "auto", "", "application/xml") == "rss"
    assert discover.classify("http://x/rss", "auto", "", "") == "rss"


def test_classify_section_vs_single_by_link_density():
    many = "".join(f'<a href="/news/article-{i}-story">x</a>' for i in range(15))
    assert discover.classify("http://x/oikonomia", "auto", f"<html>{many}</html>", "text/html") == "section"
    assert discover.classify("http://x/a-single-article", "auto", "<html><a href='/'>home</a></html>",
                             "text/html") == "single"


def test_classify_article_url_is_single_even_with_many_links():
    # an article page links to many related articles, but the URL is itself an article (numeric id)
    many = "".join(f'<a href="/oikonomia/{4000000+i}/story-{i}-here">x</a>' for i in range(15))
    assert discover.classify("https://www.capital.gr/oikonomia/3996701/komision-espa", "auto",
                             f"<html>{many}</html>", "text/html") == "single"
    # a date-path article too
    assert discover.classify("https://news.example/2026/06/06/big-tax-story", "auto", "", "") == "single"


def test_parse_feed_links_returns_entry_urls():
    rss = """<?xml version='1.0'?><rss><channel>
      <item><link>https://news.example/a</link></item>
      <item><link>https://news.example/b</link></item>
    </channel></rss>"""
    assert discover.parse_feed_links(rss)[:2] == ["https://news.example/a", "https://news.example/b"]


def test_extract_article_links_excludes_aggregation_pages():
    html = ('<a href="/tag/foo-bar">t</a>'
            '<a href="/author/jane-doe">a</a>'
            '<a href="/category/news-stuff">c</a>'
            '<a href="/oikonomia/3996807/real-story-here">r</a>')
    links = discover.extract_article_links(html, "https://news.example/oikonomia")
    assert any("/oikonomia/3996807/" in u for u in links)
    assert all("/tag/" not in u and "/author/" not in u and "/category/" not in u for u in links)


def test_prefer_articles_picks_numeric_id_urls():
    urls = ["https://x.gr/tax/tax-akinita", "https://x.gr/oikonomia/3996807/story-slug"]
    assert discover._prefer_articles(urls) == ["https://x.gr/oikonomia/3996807/story-slug"]
    only_slugs = ["https://x.gr/a/foo-bar", "https://x.gr/b/baz-qux"]
    assert discover._prefer_articles(only_slugs) == only_slugs


def test_same_section_keeps_only_under_section_else_all():
    urls = ["https://www.capital.gr/oikonomia/3996807/real-story",
            "https://www.capital.gr/forex/3165226/isotimia-eur-usd",
            "https://www.capital.gr/tax/tax-akinita"]
    kept = discover._same_section(urls, "https://www.capital.gr/oikonomia")
    assert kept == ["https://www.capital.gr/oikonomia/3996807/real-story"]   # forex/tax dropped
    # homepage (no section segment) → [] so caller falls back to all
    assert discover._same_section(urls, "https://www.capital.gr/") == []


def test_extract_article_links_filters_same_host_articles():
    html = ('<a href="https://news.example/politics/big-story-2026">x</a>'
            '<a href="https://other.com/x">y</a>'
            '<a href="/about">z</a>'
            '<a href="https://news.example/oikonomia/tax-bill-explained">w</a>')
    links = discover.extract_article_links(html, "https://news.example/oikonomia")
    assert "https://news.example/politics/big-story-2026" in links
    assert "https://news.example/oikonomia/tax-bill-explained" in links
    assert all("other.com" not in u for u in links)
    assert all(not u.endswith("/about") for u in links)
