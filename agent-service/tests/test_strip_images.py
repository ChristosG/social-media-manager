from app.api.ws import _strip_images_for_llm


def test_strips_data_url_image_to_placeholder():
    big = "data:image/png;base64," + "A" * 100_000
    text = f"Here is your image!\n\n![a golden puppy]({big})\n"
    out = _strip_images_for_llm(text)
    assert "data:image" not in out
    assert "base64" not in out
    assert "[generated image: a golden puppy]" in out
    assert "Here is your image!" in out          # surrounding prose preserved
    assert len(out) < 200                          # collapsed from 100k+ chars


def test_strips_multiple_images():
    text = "![one](data:image/png;base64,AAAA) and ![two](https://x/y.png) done"
    out = _strip_images_for_llm(text)
    assert "data:" not in out and "https://x/y.png" not in out
    assert out.count("[generated image:") == 2


def test_noop_without_images():
    text = "Just a normal reply with no image at all."
    assert _strip_images_for_llm(text) == text


def test_handles_empty_alt_and_none():
    assert _strip_images_for_llm("![](data:image/png;base64,ZZ)") == "[generated image: image]"
    assert _strip_images_for_llm("") == ""


def test_strips_gallery_block():
    block = "```ss-gallery\ndata:image/png;base64,AAAA\ndata:image/png;base64,BBBB\n```"
    out = _strip_images_for_llm(f"Here are variations!\n\n{block}\n")
    assert "data:" not in out and "ss-gallery" not in out
    assert "[generated image variations]" in out
    assert "Here are variations!" in out
    assert len(out) < 120
