from __future__ import annotations

from typing import Any

from .models import Anime


def upsert_from_tracker_payload(payload: dict[str, Any]) -> Anime:
    tracker_type = payload["tracker_type"]
    tracker_id = payload["tracker_id"]
    defaults = {
        "title_romaji": payload.get("title_romaji", ""),
        "title_english": payload.get("title_english", ""),
        "title_native": payload.get("title_native", ""),
        "season": payload.get("season", ""),
        "season_year": payload.get("season_year"),
        "episodes": payload.get("episodes"),
        "studio": payload.get("studio", ""),
        "cover_image_url": payload.get("cover_image_url", ""),
        "banner_image_url": payload.get("banner_image_url", ""),
        "description": payload.get("description", ""),
    }
    anime, _ = Anime.objects.update_or_create(
        tracker_type=tracker_type,
        tracker_id=tracker_id,
        defaults=defaults,
    )
    return anime
