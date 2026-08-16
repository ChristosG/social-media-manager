import asyncio
import base64
import random

import httpx

from app.config import get_settings

# FLUX shares GPU1 with embeddings — serialize generations so requests don't pile up.
_sem = asyncio.Semaphore(1)


def _round16(n: int) -> int:
    """FLUX wants dimensions on a 16px grid; clamp to a sane range."""
    return max(256, min(1536, (int(n) // 16) * 16))


async def generate(prompt: str, width: int = 1024, height: int = 1024, steps: int = 4,
                   cfg: float = 1.0, seed: int | None = None,
                   sampler_name: str | None = None) -> tuple[bytes, int] | None:
    """Call the host FLUX server. Returns (png_bytes, seed_used) or None on failure."""
    if seed is None:
        seed = random.randint(1, 2_147_483_647)
    width, height = _round16(width), _round16(height)
    payload = {"prompt": prompt, "width": width, "height": height, "steps": steps,
               "cfg": cfg, "seed": seed, "return_base64": True}
    if sampler_name:
        payload["sampler_name"] = sampler_name
    base = get_settings().flux_base_url.rstrip("/")
    try:
        async with _sem:
            async with httpx.AsyncClient(timeout=180) as c:
                r = await c.post(f"{base}/generate", json=payload)
                r.raise_for_status()
                data = r.json()
        b64 = data.get("image_base64")
        if not b64:
            return None
        return base64.b64decode(b64), seed
    except Exception:
        return None
