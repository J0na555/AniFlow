from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.productivity.services import get_watching_limit_state

from .models import Anime, UserAnime

VALID_USER_STATUSES = frozenset(
    {"watching", "planning", "completed", "paused", "dropped", "repeating"}
)


class WatchingLimitReached(Exception):
    """Raised when starting another title would exceed the user's watching limit."""


def upsert_from_tracker_payload(payload: dict[str, Any]) -> Anime:
    tracker_type = payload.get("tracker_type") or "anilist"
    tracker_id = str(payload["tracker_id"])
    preferred_title = payload.get("title", "")
    defaults = {
        "title_romaji": payload.get("title_romaji", ""),
        "title_english": payload.get("title_english", "") or preferred_title,
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


def update_user_anime_status(user, *, anime_id: int, status: str) -> UserAnime:
    """Apply a list status change with watching-limit enforcement."""
    normalized = normalize_tracker_status(status)
    if normalized not in VALID_USER_STATUSES:
        raise ValueError(f"Invalid status: {status!r}")

    user_anime = UserAnime.objects.select_related("anime").get(user=user, anime_id=anime_id)
    prev = user_anime.status

    if normalized == "watching" and prev != "watching":
        limit_state = get_watching_limit_state(user)
        if limit_state.reached:
            raise WatchingLimitReached(
                "Watching limit reached. Override the limit before starting another title."
            )

    user_anime.status = normalized
    today = timezone.localdate()
    changed: set[str] = {"status", "updated_at"}

    if normalized == "watching" and prev == "planning" and not user_anime.start_date:
        user_anime.start_date = today
        changed.add("start_date")

    if normalized == "completed":
        if user_anime.anime.episodes is not None:
            user_anime.progress = user_anime.anime.episodes
        changed.add("progress")
        if not user_anime.completed_date:
            user_anime.completed_date = today
            changed.add("completed_date")
    elif prev == "completed" and normalized != "completed":
        if user_anime.completed_date is not None:
            user_anime.completed_date = None
            changed.add("completed_date")

    user_anime.save(update_fields=sorted(changed))
    return user_anime
