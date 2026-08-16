from app.sources import chunk


def test_packs_paragraphs_under_target():
    paras = ["A" * 500, "B" * 500, "C" * 500]
    out = chunk.chunk_text("\n\n".join(paras), target_chars=1200, overlap=0)
    assert len(out) == 2
    assert out[0].startswith("A") and "B" in out[0] and out[1].startswith("C")


def test_long_paragraph_is_split():
    out = chunk.chunk_text("X" * 3000, target_chars=1200, overlap=0)
    assert all(len(c) <= 1200 for c in out) and "".join(out) == "X" * 3000


def test_empty_returns_empty():
    assert chunk.chunk_text("   ", target_chars=1200) == []
