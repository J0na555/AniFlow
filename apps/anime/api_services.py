from __future__ import annotations

from django.db.models import Q

from apps.anime.models import UserAnime
from apps.anime.services import apply_progress_update
from apps.anime.services import normalize_tracker_status
from apps.recommendations.services import get_recommendations
from apps.releases.services import get_weekly_releases
from apps.streaming.router import resolve_streaming_route
from apps.tracker.services import sync_user_list
from apps.tracker.services import update_progress as tracker_update_progress


def _preferred_title(entry: UserAnime) -> str:
    anime = entry.anime
    return anime.title_english or anime.title_romaji or anime.title_native or ""


def _serialize_user_entry(entry: UserAnime) -> dict:
    anime = entry.anime
    return {
        "anime_id": anime.id,
        "tracker_id": anime.tracker_id,
        "title": _preferred_title(entry),
        "status": entry.status,
        "progress": entry.progress,
        "episodes": anime.episodes,
        "score": float(entry.score) if entry.score is not None else None,
        "cover_image_url": anime.cover_image_url,
        "updated_at": entry.updated_at.isoformat(),
    }


def ensure_user_library_loaded(user) -> None:
    if not UserAnime.objects.filter(user=user).exists():
        sync_user_list(user)


def get_dashboard_payload(user) -> dict:
    ensure_user_library_loaded(user)
    entries = UserAnime.objects.filter(user=user).select_related("anime")
    watching = entries.filter(status="watching").order_by("-updated_at")
    planning = entries.filter(status="planning").order_by(
        "anime__title_english", "anime__title_romaji"
    )
    completed = entries.filter(status="completed").order_by("-updated_at")

    return {
        "continue_watching": [_serialize_user_entry(entry) for entry in watching[:5]],
        "counts": {
            "watching": watching.count(),
            "planning": planning.count(),
            "completed": completed.count(),
        },
    }


def get_watchlist_payload(user, *, status: str | None = None, query: str = "") -> dict:
    ensure_user_library_loaded(user)
    entries = UserAnime.objects.filter(user=user).select_related("anime")

    if status:
        entries = entries.filter(status=status)

    if query:
        entries = entries.filter(
            Q(anime__title_english__icontains=query)
            | Q(anime__title_romaji__icontains=query)
            | Q(anime__title_native__icontains=query)
        )

    entries = entries.order_by("-updated_at")
    items = [_serialize_user_entry(entry) for entry in entries[:50]]
    return {
        "items": items,
        "count": entries.count(),
    }


def get_resume_payload(user, *, limit: int = 10) -> dict:
    ensure_user_library_loaded(user)
    entries = (
        UserAnime.objects.filter(user=user, status="watching")
        .select_related("anime")
        .order_by("-updated_at")[:limit]
    )
    items: list[dict] = []
    for entry in entries:
        next_episode = entry.progress + 1
        route = resolve_streaming_route(user, entry.anime, next_episode)
        item = _serialize_user_entry(entry)
        item["next_episode"] = next_episode
        item["route"] = {
            "url": route.url,
            "search_url": route.search_url,
            "needs_confirmation": route.needs_confirmation,
            "source": route.source.name if route.source else None,
        }
        items.append(item)
    return {"items": items}


def update_progress_payload(user, *, anime_id: int, progress: int) -> dict:
    user_anime = UserAnime.objects.select_related("anime").get(user=user, anime_id=anime_id)
    tracker_response = tracker_update_progress(
        user,
        user_anime.anime.tracker_id,
        progress,
    )
    tracker_status = normalize_tracker_status(tracker_response.get("status"))
    updated = apply_progress_update(
        user_anime,
        tracker_response.get("progress", progress),
        tracker_status,
    )
    return {
        "item": _serialize_user_entry(updated),
        "tracker_status": tracker_status,
    }


def get_recommendations_payload(user) -> dict:
    ensure_user_library_loaded(user)
    return get_recommendations(user, limit=10)


def get_releases_payload(user) -> dict:
    ensure_user_library_loaded(user)
    return get_weekly_releases(user, limit=10)
