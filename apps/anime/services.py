from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from apps.productivity.services import get_watching_limit_state

from .models import Anime, UserAnime

logger = logging.getLogger(__name__)

TRACKER_TYPE_ANILIST = "anilist"

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


def _save_user_entry(
    user,
    anime: Anime,
    *,
    status: str,
    progress: int | None = None,
    score: float | None = None,
) -> UserAnime:
    """Push the entry to the user's tracker (best-effort) and upsert UserAnime.

    A tracker failure (e.g. AniList 5xx) is logged but does not roll back the
    local write; the next sync will reconcile the state.
    """
    # Lazy import to avoid the apps.tracker.services <-> apps.anime.services cycle.
    from apps.tracker import services as tracker_services

    try:
        tracker_services.save_list_entry(
            user,
            anime.tracker_id,
            status=status,
            progress=progress,
            score=score,
        )
    except Exception:
        logger.warning(
            "Failed to push list entry to tracker for user=%s anime=%s",
            getattr(user, "pk", None),
            anime.tracker_id,
            exc_info=True,
        )

    defaults: dict[str, Any] = {"status": status}
    if progress is not None:
        defaults["progress"] = progress
    if score is not None:
        defaults["score"] = score

    user_anime, _ = UserAnime.objects.update_or_create(
        user=user,
        anime=anime,
        defaults=defaults,
    )
    return user_anime


def add_to_library(
    user,
    *,
    tracker_id: str,
    status: str,
    progress: int = 0,
    score: float | None = None,
    payload: dict[str, Any] | None = None,
) -> UserAnime:
    """Add a tracker title to the user's library and sync it to the tracker.

    `payload` should be the tracker media payload already fetched by the caller
    (the search view caches it on the request). If omitted, we fall back to an
    existing local ``Anime`` row keyed by ``tracker_id`` and raise if neither
    is available.
    """
    normalized = normalize_tracker_status(status)
    if normalized not in VALID_USER_STATUSES:
        raise ValueError(f"Invalid status: {status!r}")

    tracker_type = getattr(user, "tracker_type", "") or TRACKER_TYPE_ANILIST

    if payload is not None:
        anime = upsert_from_tracker_payload(payload)
    else:
        try:
            anime = Anime.objects.get(
                tracker_type=tracker_type,
                tracker_id=str(tracker_id),
            )
        except Anime.DoesNotExist as exc:
            raise ValueError(
                f"No cached tracker payload for tracker_id={tracker_id!r}; "
                "fetch the media payload before calling add_to_library."
            ) from exc

    if normalized == "watching":
        existing = UserAnime.objects.filter(user=user, anime=anime).first()
        already_watching = existing is not None and existing.status == "watching"
        if not already_watching:
            limit_state = get_watching_limit_state(user)
            if limit_state.reached:
                raise WatchingLimitReached(
                    "Watching limit reached. Override the limit before "
                    "starting another title."
                )

    return _save_user_entry(
        user,
        anime,
        status=normalized,
        progress=progress,
        score=score,
    )
