import asyncio
import hashlib
import hmac
import json
import httpx
from app.config import get_settings

_GRAPH = "https://graph.facebook.com/v21.0"
_transport: httpx.MockTransport | None = None   # test hook; None → real network
_TRANSIENT = {1, 2, 4, 17, 32, 613}
_AUTH = {190}


class PublishError(Exception): ...
class PublishTransientError(PublishError): ...
class PublishPermanentError(PublishError): ...
class PublishAuthError(PublishError): ...


def _proof(token: str) -> str:
    return hmac.new(get_settings().meta_app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def _classify(payload: dict) -> PublishError:
    err = payload.get("error", {}) if isinstance(payload, dict) else {}
    code = err.get("code")
    msg = err.get("error_user_msg") or err.get("message") or "Meta API error"
    if code in _AUTH:
        return PublishAuthError(msg)
    if code in _TRANSIENT:
        return PublishTransientError(msg)
    return PublishPermanentError(msg)


async def _call(method: str, path: str, token: str, params: dict) -> dict:
    p = {**params, "access_token": token, "appsecret_proof": _proof(token)}
    async with httpx.AsyncClient(timeout=60, transport=_transport) as c:
        r = await (c.post(f"{_GRAPH}/{path}", data=p) if method == "POST"
                   else c.get(f"{_GRAPH}/{path}", params=p))
        body = r.json()
        if r.status_code >= 400 or (isinstance(body, dict) and body.get("error")):
            raise _classify(body)
        return body


async def _wait_container(container_id: str, token: str, tries: int = 5) -> None:
    for _ in range(tries):
        st = await _call("GET", container_id, token, {"fields": "status_code"})
        if st.get("status_code") == "FINISHED":
            return
        if st.get("status_code") == "ERROR":
            raise PublishPermanentError("Instagram could not process the media")
        await asyncio.sleep(2)
    raise PublishTransientError("Instagram media not ready yet")


async def _publish_instagram(ig_id: str, token: str, caption: str, urls: list[str]) -> dict:
    if not urls:
        raise PublishPermanentError("Instagram requires at least one image")
    if len(urls) == 1:
        cont = await _call("POST", f"{ig_id}/media", token, {"image_url": urls[0], "caption": caption})
    else:
        if len(urls) > 10:
            # Don't silently drop content on a public post — fail loudly instead.
            raise PublishPermanentError("Instagram carousel supports at most 10 images")
        children = []
        for u in urls:
            c = await _call("POST", f"{ig_id}/media", token, {"image_url": u, "is_carousel_item": "true"})
            children.append(c["id"])
        cont = await _call("POST", f"{ig_id}/media", token,
                           {"media_type": "CAROUSEL", "caption": caption, "children": ",".join(children)})
    await _wait_container(cont["id"], token)
    pub = await _call("POST", f"{ig_id}/media_publish", token, {"creation_id": cont["id"]})
    media = await _call("GET", pub["id"], token, {"fields": "permalink"})
    # `id` is always present post-publish; the worker keys idempotency on it (permalink may be empty).
    return {"id": pub["id"], "permalink": media.get("permalink", "")}


async def _publish_facebook(page_id: str, token: str, caption: str, urls: list[str]) -> dict:
    if not urls:                                   # text-only
        post = await _call("POST", f"{page_id}/feed", token, {"message": caption})
    elif len(urls) == 1:
        post = await _call("POST", f"{page_id}/photos", token,
                           {"url": urls[0], "message": caption, "published": "true"})
    else:                                          # multi: unpublished photos -> feed with attachments
        media = []
        for u in urls:
            ph = await _call("POST", f"{page_id}/photos", token, {"url": u, "published": "false"})
            media.append({"media_fbid": ph["id"]})
        params = {"message": caption}
        for i, m in enumerate(media):
            params[f"attached_media[{i}]"] = json.dumps(m)
        post = await _call("POST", f"{page_id}/feed", token, params)
    pid = post.get("post_id") or post.get("id", "")
    permalink = post.get("permalink_url") or f"https://www.facebook.com/{pid}"
    return {"id": pid, "permalink": permalink}


async def publish_to_target(provider: str, target_id: str, page_token: str,
                            caption: str, image_jpg_urls: list[str]) -> dict:
    if provider == "instagram":
        return await _publish_instagram(target_id, page_token, caption, image_jpg_urls)
    if provider == "facebook":
        return await _publish_facebook(target_id, page_token, caption, image_jpg_urls)
    raise PublishPermanentError(f"unsupported provider {provider}")
