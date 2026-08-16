# max_chars is the HARD ceiling; target_chars is the IDEAL length the drafter aims for. Without a target the
# model treats the (large) ceiling as a goal and writes walls of text — Instagram especially wants a tight,
# scroll-stopping caption, not 2200 chars.
PLATFORMS: dict[str, dict] = {
    "linkedin":  {"label": "LinkedIn",  "max_chars": 3000, "target_chars": 900, "tone": "professional, warm, story-led",
                  "hashtags": "2-3 relevant", "image": (1200, 627)},
    "instagram": {"label": "Instagram", "max_chars": 2200, "target_chars": 600, "tone": "vivid, personal, emoji-friendly",
                  "hashtags": "5-10", "image": (1080, 1080)},
    "x":         {"label": "X",         "max_chars": 280,  "target_chars": 240, "tone": "punchy, concise",
                  "hashtags": "1-2", "image": (1600, 900)},
    "facebook":  {"label": "Facebook",  "max_chars": 2000, "target_chars": 500, "tone": "friendly, community",
                  "hashtags": "0-2", "image": (1200, 630)},
}

def resolve_platform(name: str) -> tuple[str, dict] | None:
    key = (name or "").strip().lower()
    return (key, PLATFORMS[key]) if key in PLATFORMS else None
