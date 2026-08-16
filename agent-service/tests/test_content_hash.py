from app.social.content_hash import content_hash


def test_content_hash_stable_and_order_independent():
    a = content_hash("Hello 🐾", ["11111111-1111-1111-1111-111111111111",
                                  "22222222-2222-2222-2222-222222222222"])
    b = content_hash("Hello 🐾", ["22222222-2222-2222-2222-222222222222",
                                  "11111111-1111-1111-1111-111111111111"])
    c = content_hash("Hello", [])
    assert a == b           # image order does not matter
    assert a != c           # different content differs
    assert len(a) == 64     # sha256 hex
