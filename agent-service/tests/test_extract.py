from app.sources import extract

_HTML = """<!doctype html><html><head><title>Site</title></head><body>
<nav><ul><li>Ροή Ειδήσεων</li><li>ΟΙΚΟΝΟΜΙΑ</li><li>ΠΟΛΙΤΙΚΗ</li></ul></nav>
<header>DAX 24.773 CAC 8.218 Dow Jones 50.867</header>
<article><h1>New tax bill explained</h1>
<p>The finance ministry published a new tax bill on Monday that lowers VAT for small nonprofits.</p>
<p>Officials said the measure takes effect next quarter and applies to registered charities.</p>
</article>
<footer>Subscribe to our newsletter. Cookie settings.</footer></body></html>"""


def test_extracts_article_drops_chrome():
    doc = extract.extract_article(_HTML, "https://news.example/tax")
    assert doc is not None
    assert "tax bill" in doc["text"].lower()
    assert "lowers VAT for small nonprofits" in doc["text"]
    assert "Ροή Ειδήσεων" not in doc["text"]
    assert "Dow Jones" not in doc["text"]
    assert "Cookie settings" not in doc["text"]


def test_returns_none_on_empty():
    assert extract.extract_article("<html><body><nav>menu</nav></body></html>", "http://x") is None
