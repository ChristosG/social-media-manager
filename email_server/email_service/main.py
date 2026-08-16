import time
import uuid
import logging
from collections import defaultdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate
from pathlib import Path

import re

import aiosmtplib
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import escape
from pydantic import BaseModel, EmailStr, Field

from config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("email_service")

app = FastAPI(title="Email Service", docs_url=None, redoc_url=None)

# Jinja2 template environment
templates_dir = Path(__file__).parent / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(templates_dir),
    autoescape=select_autoescape(["html"]),
)

# Rate limiting state
_recipient_hits: dict[str, list[float]] = defaultdict(list)
_global_hits: list[float] = []


# --- Middleware: API key auth ---
@app.middleware("http")
async def authenticate(request: Request, call_next):
    if request.url.path in ("/health", "/docs", "/openapi.json"):
        return await call_next(request)

    settings = get_settings()
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != settings.api_key:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

    return await call_next(request)


# --- Rate limiting ---
def _cleanup_hits(hits: list[float], window: float = 60.0) -> list[float]:
    now = time.monotonic()
    return [t for t in hits if now - t < window]


def check_rate_limit(recipient: str) -> None:
    settings = get_settings()
    now = time.monotonic()

    # Global rate limit
    global _global_hits
    _global_hits = _cleanup_hits(_global_hits)
    if len(_global_hits) >= settings.rate_limit_global:
        raise HTTPException(status_code=429, detail="Global rate limit exceeded")
    _global_hits.append(now)

    # Per-recipient rate limit
    _recipient_hits[recipient] = _cleanup_hits(_recipient_hits[recipient])
    if len(_recipient_hits[recipient]) >= settings.rate_limit_per_recipient:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded for {recipient}")
    _recipient_hits[recipient].append(now)


# --- Request/response models ---
class SendRequest(BaseModel):
    to: EmailStr
    template: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$", max_length=64)
    data: dict = Field(default_factory=dict)


class SendResponse(BaseModel):
    status: str = "sent"
    message: str = "Email queued for delivery"


# --- Endpoints ---
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/send", response_model=SendResponse)
async def send_email(payload: SendRequest):
    settings = get_settings()

    check_rate_limit(payload.to)

    # Verify template exists
    template_name = f"{payload.template}.html"
    template_path = templates_dir / template_name
    if not template_path.is_file():
        raise HTTPException(status_code=400, detail=f"Unknown template: {payload.template}")

    # Escape all user-provided data values
    safe_data = {k: escape(str(v)) if isinstance(v, str) else v for k, v in payload.data.items()}

    # Render template
    template = jinja_env.get_template(template_name)
    html_body = template.render(**safe_data, domain=settings.mail_domain, app_name=settings.app_name)

    # Build MIME message
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.sender
    msg["To"] = payload.to
    msg["Subject"] = _get_subject(payload.template, safe_data)
    msg["Message-ID"] = f"<{uuid.uuid4()}@{settings.mail_domain}>"
    msg["Date"] = formatdate(localtime=True)
    msg["List-Unsubscribe"] = f"<mailto:{settings.mail_from_address or f'noreply@{settings.mail_domain}'}?subject=unsubscribe>"

    # Plain text version (strip HTML tags) — improves spam score
    plain_text = re.sub(r"<[^>]+>", "", html_body)
    plain_text = re.sub(r"\n\s*\n", "\n\n", plain_text).strip()
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Send via SMTP
    try:
        smtp_kwargs = {
            "hostname": settings.smtp_host,
            "port": settings.smtp_port,
        }
        if settings.smtp_user:
            smtp_kwargs["username"] = settings.smtp_user
            smtp_kwargs["password"] = settings.smtp_password
        if settings.smtp_use_tls:
            smtp_kwargs["use_tls"] = True

        await aiosmtplib.send(msg, **smtp_kwargs)
    except Exception as e:
        logger.error(f"SMTP error: {e}")
        raise HTTPException(status_code=502, detail="Failed to send email")

    logger.info(f"Email sent: template={payload.template} to={payload.to}")
    return SendResponse()


def _get_subject(template: str, data: dict) -> str:
    """Return a subject line based on template name."""
    settings = get_settings()
    name = settings.app_name
    subjects = {
        "welcome": f"Welcome to {name}!",
        "login_alert": f"{name} — New login to your account",
        "verify_email": f"{name} — Verify your email address",
        "forgot_password": f"{name} — Reset your password",
        "password_changed": f"{name} — Your password has been changed",
    }
    return subjects.get(template, "Notification")


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)
