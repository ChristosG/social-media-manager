import io
import logging

logger = logging.getLogger(__name__)

# Cap extracted text so a big file can't blow up the LLM context (and our DB rows).
_MAX_CHARS = 20000

# Filename suffixes we treat as plain UTF-8 text even if the mime type is generic.
_TEXT_SUFFIXES = (".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".log", ".yaml", ".yml")


def extract_text(filename: str, mime_type: str, data: bytes) -> str:
    """Extract plain text from an uploaded file. The LLM is text-only — images yield ''
    (no vision). Always defensive: any failure returns '' rather than raising."""
    name = (filename or "").lower()
    mime = (mime_type or "").lower()
    try:
        if mime == "application/pdf" or name.endswith(".pdf"):
            text = _extract_pdf(data)
        elif mime.startswith("image/"):
            text = ""  # no vision — nothing to extract
        elif mime.startswith("text/") or name.endswith(_TEXT_SUFFIXES):
            text = data.decode("utf-8", "ignore")
        else:
            # Unknown type: best-effort decode (covers things like application/json without a suffix).
            text = data.decode("utf-8", "ignore")
    except Exception:
        logger.exception("text extraction failed (file=%s mime=%s)", filename, mime_type)
        return ""
    return text[:_MAX_CHARS]


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(parts)
    except Exception:
        logger.exception("pdf extraction failed")
        return ""
