import asyncio
import io

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from PIL import Image

from app.repo import images as repo
from app.security.context import require_identity
from app.security.img_sign import verify_image, image_url

router = APIRouter()

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB — keep in sync with nginx client_max_body_size
_MAX_DIM = 4096                       # clamp giant uploads before they hit the publishers


# Pillow decode/convert/encode is synchronous C that holds the GIL — running it inline in an async
# handler would freeze the WHOLE event loop (every concurrent chat stream + request) for the duration.
# These helpers are pure CPU and are dispatched via asyncio.to_thread so the loop stays free.

def _normalize_to_png(data: bytes) -> tuple[bytes, int, int]:
    """Decode → validate → flatten → bound dimensions → re-encode to PNG. Raises on a non-image."""
    img = Image.open(io.BytesIO(data))
    img.load()                                  # force decode — raises on truncated/forged files
    img = img.convert("RGBA") if (img.mode in ("RGBA", "LA", "P")) else img.convert("RGB")
    if img.width > _MAX_DIM or img.height > _MAX_DIM:
        img.thumbnail((_MAX_DIM, _MAX_DIM))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), img.width, img.height


def _to_jpeg(data: bytes) -> bytes:
    """Re-encode stored PNG bytes to JPEG (alpha composited onto white) for Instagram."""
    pil_img = Image.open(io.BytesIO(data))
    if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
        background = Image.new("RGB", pil_img.size, (255, 255, 255))
        rgba = pil_img.convert("RGBA")          # convert once; reuse for paste + alpha mask
        background.paste(rgba, mask=rgba.split()[3])
        pil_img = background
    else:
        pil_img = pil_img.convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=90, optimize=True)
    return buf.getvalue()


@router.post("/images/upload")
async def upload_image(file: UploadFile = File(...), ident: tuple[str, str] = Depends(require_identity)):
    """Accept a user-supplied image for a post and store it as an org image (same table the
    generator writes to), returning a signed display URL. The bytes are decoded and RE-ENCODED to PNG
    via Pillow — this validates the file is a real raster image, strips EXIF/metadata, and neutralizes
    any embedded payload (we never serve back the raw client bytes). Returns ``{id, url}`` so the
    publish dialog can append it to the image strip alongside generated images."""
    user_id, org_id = ident
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="image too large (max 10MB)")
    try:
        png, width, height = await asyncio.to_thread(_normalize_to_png, data)
    except Exception:
        raise HTTPException(status_code=415, detail="not a valid image")
    image_id = await repo.create_image(
        org_id, "uploaded image", None, png, width, height, 0, 0.0, None,
        platform=None, fmt="png", created_by=user_id)
    return {"id": image_id, "url": image_url(image_id, org_id)}


@router.get("/img/{image_id}")
async def serve_image(image_id: str, o: str = "", s: str = "", dl: int = 0, fmt: str = ""):
    """Serve a generated image by signed URL — no session auth (nginx routes this straight to the
    service, bypassing the gateway); the HMAC signature over (image_id, org) IS the authorization,
    and the signed `o` (org) scopes the per-org RLS read.

    Pass ``fmt=jpg`` to receive a JPEG (quality 90, alpha composited onto white) — required by
    Instagram's publish API. Omit or leave blank for the original PNG (max quality).
    The ``fmt`` parameter is intentionally NOT included in the HMAC so callers can add it without
    re-signing; the auth token still covers (image_id, org) only.
    """
    if not verify_image(image_id, o, s):
        raise HTTPException(status_code=403, detail="bad signature")
    img = await repo.get_image(o, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="not found")
    disposition = "attachment" if dl else "inline"

    if fmt == "jpg":
        jpeg = await asyncio.to_thread(_to_jpeg, img["data"])
        return Response(
            content=jpeg,
            media_type="image/jpeg",
            headers={
                "Content-Disposition": f'{disposition}; filename="social-studio-{image_id[:8]}.jpg"',
                "Cache-Control": "public, max-age=31536000, immutable",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return Response(
        content=img["data"],
        media_type="image/png",
        headers={
            "Content-Disposition": f'{disposition}; filename="social-studio-{image_id[:8]}.png"',
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )
