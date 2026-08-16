# Email Service API

Base URL: `http://localhost:8025`

## Authentication

All requests (except `/health`) require an API key via the `X-API-Key` header.

```
X-API-Key: your-api-key
```

Returns `401` if the key is missing or invalid.

## Rate Limits

- **Per recipient:** 10 emails/minute
- **Global:** 100 emails/minute

Returns `429` when exceeded.

---

## Endpoints

### `GET /health`

Health check. No authentication required.

**Response:**
```json
{ "status": "ok" }
```

---

### `POST /send`

Send a templated email.

**Headers:**
| Header         | Required | Description   |
|----------------|----------|---------------|
| `Content-Type` | Yes      | `application/json` |
| `X-API-Key`    | Yes      | Your API key  |

**Body:**
| Field      | Type   | Required | Description                                      |
|------------|--------|----------|--------------------------------------------------|
| `to`       | string | Yes      | Recipient email address                          |
| `template` | string | Yes      | Template name (alphanumeric, hyphens, underscores) |
| `data`     | object | No       | Key-value pairs passed to the template           |

**Response `200`:**
```json
{ "status": "sent", "message": "Email queued for delivery" }
```

**Error responses:**

| Status | Meaning                        |
|--------|--------------------------------|
| `400`  | Unknown template               |
| `401`  | Invalid or missing API key     |
| `429`  | Rate limit exceeded            |
| `502`  | SMTP delivery failure          |

---

## Templates

### `welcome`

Welcome email for new users.

**Data:**
| Field  | Type   | Description        |
|--------|--------|--------------------|
| `name` | string | User's display name |

```bash
curl -X POST http://localhost:8025/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "to": "user@example.com",
    "template": "welcome",
    "data": { "name": "Chris" }
  }'
```

---

### `login_alert`

Notification when a new login is detected.

**Data:**
| Field       | Type   | Description              |
|-------------|--------|--------------------------|
| `timestamp` | string | When the login occurred  |
| `ip`        | string | IP address of the login  |

```bash
curl -X POST http://localhost:8025/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "to": "user@example.com",
    "template": "login_alert",
    "data": { "timestamp": "2026-03-03 14:22 UTC", "ip": "203.0.113.42" }
  }'
```

---

### `verify_email`

Email verification for new signups. Includes a CTA button.

**Data:**
| Field        | Type   | Description                       |
|--------------|--------|-----------------------------------|
| `name`       | string | User's display name               |
| `verify_url` | string | Full URL to verify the email address |

```bash
curl -X POST http://localhost:8025/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "to": "user@example.com",
    "template": "verify_email",
    "data": {
      "name": "Chris",
      "verify_url": "https://yourdomain.com/verify?token=abc123"
    }
  }'
```

---

### `forgot_password`

Password reset email. Includes a CTA button.

**Data:**
| Field       | Type   | Description                     |
|-------------|--------|---------------------------------|
| `name`      | string | User's display name             |
| `reset_url` | string | Full URL to the reset password page |

```bash
curl -X POST http://localhost:8025/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "to": "user@example.com",
    "template": "forgot_password",
    "data": {
      "name": "Chris",
      "reset_url": "https://yourdomain.com/reset-password?token=xyz789"
    }
  }'
```

---

### `password_changed`

Confirmation after a password change. Informational only, no button.

**Data:**
| Field  | Type   | Description        |
|--------|--------|--------------------|
| `name` | string | User's display name |

```bash
curl -X POST http://localhost:8025/send \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "to": "user@example.com",
    "template": "password_changed",
    "data": { "name": "Chris" }
  }'
```

---

## Python Example

```python
import httpx

EMAIL_SERVICE = "http://localhost:8025"
API_KEY = "your-api-key"

async def send_email(to: str, template: str, data: dict):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{EMAIL_SERVICE}/send",
            headers={"X-API-Key": API_KEY},
            json={"to": to, "template": template, "data": data},
        )
        resp.raise_for_status()
        return resp.json()

# Verify email
await send_email("user@example.com", "verify_email", {
    "name": "Chris",
    "verify_url": "https://yourdomain.com/verify?token=abc123",
})

# Forgot password
await send_email("user@example.com", "forgot_password", {
    "name": "Chris",
    "reset_url": "https://yourdomain.com/reset-password?token=xyz789",
})

# Password changed
await send_email("user@example.com", "password_changed", {"name": "Chris"})
```

---

## Notes

- All string values in `data` are HTML-escaped automatically to prevent XSS.
- Emails are sent as multipart (HTML + plain text fallback).
- The subject line is determined by the template name and cannot be overridden per-request.
