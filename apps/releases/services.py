from __future__ import annotations

from django.utils import timezone

from apps.tracker.services import get_weekly_releases as tracker_get_weekly_releases


def _serialize_release(item: dict) -> dict:
    airing_at = item.get("airing_at")
    airing_label = ""
    if airing_at is not None:
        local_airing = timezone.localtime(airing_at)
        airing_label = local_airing.strftime("%a %H:%M")
        airing_at = local_airing.isoformat()
    return {
        "tracker_id": item.get("tracker_id"),
        "title": item.get("title") or "",
        "episode": item.get("episode"),
        "episodes": item.get("episodes"),
        "format": item.get("format") or "",
        "cover_image_url": item.get("cover_image_url") or "",
        "airing_at": airing_at,
        "airing_label": airing_label,
    }


def get_weekly_releases(user, *, limit: int = 8) -> dict:
    try:
        items = tracker_get_weekly_releases(user, limit=limit)
    except Exception:
        return {
            "items": [],
            "message": "Could not load weekly releases from AniList right now.",
        }

    if not items:
        return {
            "items": [],
            "message": "No upcoming releases were found for this week.",
        }

    serialized_items = [_serialize_release(item) for item in items]
    return {"items": serialized_items, "message": ""}
