from app.security.img_sign import sign_image, verify_image, image_url


def test_sign_verify_roundtrip():
    sig = sign_image("img-abc", "org-1")
    assert verify_image("img-abc", "org-1", sig)


def test_verify_rejects_tampering():
    sig = sign_image("img-abc", "org-1")
    assert not verify_image("img-abc", "org-2", sig)   # wrong org (no cross-tenant)
    assert not verify_image("img-xyz", "org-1", sig)   # wrong image id
    assert not verify_image("img-abc", "org-1", "deadbeef")
    assert not verify_image("img-abc", "org-1", "")
    assert not verify_image("", "", "")


def test_image_url_shape():
    u = image_url("img-abc", "org-1")
    assert u.startswith("/api/v1/img/img-abc?o=org-1&s=")
    assert len(u.rsplit("s=", 1)[1]) == 64  # sha256 hex


def test_public_image_url_is_absolute_with_fmt():
    from app.security.img_sign import public_image_url, image_url
    url = public_image_url("img-1", "org-1", fmt="jpg")
    assert url == "https://test.example" + image_url("img-1", "org-1") + "&fmt=jpg"
    assert url.startswith("https://test.example/api/v1/img/img-1?")


def test_public_image_url_no_fmt():
    from app.security.img_sign import public_image_url, image_url
    assert public_image_url("img-2", "org-2") == "https://test.example" + image_url("img-2", "org-2")


def test_public_image_url_raises_without_public_origin(monkeypatch):
    import pytest
    from app.security import img_sign
    monkeypatch.setattr(img_sign, "get_settings",
                        lambda: type("S", (), {"meta_oauth_redirect": "", "image_url_secret": "x"})())
    with pytest.raises(RuntimeError):
        img_sign.public_image_url("img-1", "org-1", fmt="jpg")


def test_signing_fails_closed_without_secret(monkeypatch):
    # The /img endpoint trusts the signed org to scope an RLS read, so a guessable/empty signing
    # secret would let an attacker forge URLs and read any org's images. Refuse to sign instead of
    # falling back to a repo-public default.
    import pytest
    from app.security import img_sign
    monkeypatch.setattr(img_sign, "get_settings",
                        lambda: type("S", (), {"image_url_secret": ""})())
    with pytest.raises(RuntimeError):
        img_sign.sign_image("img-1", "org-1")


def test_signing_fails_closed_with_short_secret(monkeypatch):
    import pytest
    from app.security import img_sign
    monkeypatch.setattr(img_sign, "get_settings",
                        lambda: type("S", (), {"image_url_secret": "short"})())
    with pytest.raises(RuntimeError):
        img_sign.sign_image("img-1", "org-1")
