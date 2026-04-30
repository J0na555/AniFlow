from __future__ import annotations

from typing import Any

from django.utils import timezone

from .models import Anime, UserAnime


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


def normalize_tracker_status(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower()
    if normalized == "current":
        return "watching"
    return normalized


def apply_progress_update(
    user_anime: UserAnime,
    progress: int,
    tracker_status: str | None = None,
) -> UserAnime:
    status = normalize_tracker_status(tracker_status) or user_anime.status
    if progress > 0 and user_anime.status == "planning":
        status = "watching"
        if not user_anime.start_date:
            user_anime.start_date = timezone.localdate()

    if user_anime.anime.episodes and progress >= user_anime.anime.episodes:
        status = "completed"
        if not user_anime.completed_date:
            user_anime.completed_date = timezone.localdate()

    user_anime.progress = progress
    user_anime.status = status
    user_anime.save(
        update_fields=[
            "progress",
            "status",
            "start_date",
            "completed_date",
            "updated_at",
        ]
    )
    return user_anime
