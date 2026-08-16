import uuid
from app.db.pool import org_tx


async def create_image(org_id: str, prompt: str, enhanced_prompt: str | None, data: bytes,
                       width: int, height: int, steps: int, cfg: float, seed: int | None,
                       sampler_name: str | None = None, platform: str | None = None,
                       fmt: str = "png", created_by: str | None = None) -> str:
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "INSERT INTO images(org_id,prompt,enhanced_prompt,data,width,height,steps,cfg,seed,"
            "sampler_name,platform,format,created_by) "
            "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) RETURNING id",
            uuid.UUID(org_id), prompt, enhanced_prompt, data, width, height, steps, float(cfg),
            seed, sampler_name, platform, fmt,
            uuid.UUID(created_by) if created_by else None)
    return str(r["id"])


async def get_image(org_id: str, image_id: str) -> dict | None:
    async with org_tx(org_id) as c:
        r = await c.fetchrow(
            "SELECT id, data, format, prompt FROM images WHERE id=$1", uuid.UUID(image_id))
    if not r:
        return None
    return {"id": str(r["id"]), "data": bytes(r["data"]), "format": r["format"], "prompt": r["prompt"]}
