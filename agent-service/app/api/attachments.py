import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from app.security.context import require_identity
from app.agent.extract import extract_text
from app.repo import attachments as repo

router = APIRouter()

_MAX_BYTES = 10 * 1024 * 1024  # 10MB — keep in sync with the nginx client_max_body_size

# ONLY types safe to store + serve. Deliberately EXCLUDES script-executable types
# (text/html, application/xhtml+xml, image/svg+xml, application/xml) — if a browser ever
# renders those from our origin they run JS (stored XSS). We normalize to one of these.
_SAFE_MIME = {
    "text/plain", "text/markdown", "text/csv", "text/tab-separated-values",
    "application/json", "application/pdf",
    "image/png", "image/jpeg", "image/gif", "image/webp",
}
_EXT_MIME = {
    ".txt": "text/plain", ".md": "text/markdown", ".markdown": "text/markdown",
    ".csv": "text/csv", ".tsv": "text/tab-separated-values", ".json": "application/json",
    ".log": "text/plain", ".yaml": "text/plain", ".yml": "text/plain",
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
}


def _safe_mime(mime: str, filename: str) -> str | None:
    """Return a SAFE, normalized content-type to store, or None to reject the upload.
    Rejects script-executable types (html/svg/xml) even if the extension looks textual."""
    m = (mime or "").split(";")[0].strip().lower()
    if m in _SAFE_MIME:
        return m
    # Browsers sometimes send application/octet-stream for .md/.csv/.txt — fall back by extension.
    ext = filename.lower()[filename.rfind("."):] if filename and "." in filename else ""
    return _EXT_MIME.get(ext)


def _sanitize_filename(name: str) -> str:
    """Strip quotes/CRLF (header-injection) and bound length for the Content-Disposition header."""
    return re.sub(r'[\r\n"\\]', "", name or "").strip()[:200] or "download"


@router.post("/attachments")
async def upload(file: UploadFile = File(...), ident: tuple[str, str] = Depends(require_identity)):
    user_id, org_id = ident
    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 10MB)")
    filename = file.filename or "upload"
    mime_type = _safe_mime(file.content_type or "", filename)
    if mime_type is None:
        raise HTTPException(status_code=415, detail="unsupported file type")
    content_text = extract_text(filename, mime_type, data)
    # Store the NORMALIZED safe mime (never the raw, possibly-dangerous client value).
    row = await repo.create_attachment(
        org_id, user_id, filename, mime_type, len(data), content_text, data)
    # Mirror filename into original_filename so the UI (which renders original_filename) works.
    row["original_filename"] = row["filename"]
    return row


@router.get("/attachments/{attachment_id}/download")
async def download(attachment_id: str, ident: tuple[str, str] = Depends(require_identity)):
    _, org_id = ident
    att = await repo.get_attachment(org_id, attachment_id)
    if att is None:
        raise HTTPException(status_code=404, detail="not found")
    # Even though uploads are normalized, re-validate on the way out (defense in depth):
    # serve a known-safe content-type or fall back to octet-stream, never render inline.
    stored = (att["mime_type"] or "").lower()
    ctype = stored if stored in _SAFE_MIME else "application/octet-stream"
    fname = _sanitize_filename(att["filename"])
    return Response(
        content=att["data"],
        media_type=ctype,
        headers={
            # attachment (download), NEVER inline — served bytes can't execute in our origin.
            "Content-Disposition": f"attachment; filename=\"{fname}\"; filename*=UTF-8''{quote(fname)}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, no-store",
        },
    )
