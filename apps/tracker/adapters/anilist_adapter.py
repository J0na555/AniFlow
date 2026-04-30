from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx

from .base_adapter import TrackerAdapter

ANILIST_API_URL = "https://graphql.anilist.co"

VIEWER_QUERY = """
query Viewer {
  Viewer {
    id
    name
  }
}
"""

USER_LIST_QUERY = """
query UserList($userId: Int) {
  MediaListCollection(userId: $userId, type: ANIME) {
    lists {
      entries {
        status
        progress
        score(format: POINT_10_DECIMAL)
        startedAt { year month day }
        completedAt { year month day }
        media {
          id
          title { romaji english native }
          season
          seasonYear
          episodes
          description
          coverImage { large }
          bannerImage
          studios(isMain: true) { nodes { name } }
        }
      }
    }
  }
}
"""

UPDATE_PROGRESS_MUTATION = """
mutation UpdateProgress($mediaId: Int!, $progress: Int!) {
  SaveMediaListEntry(mediaId: $mediaId, progress: $progress) {
    id
    status
    progress
    score(format: POINT_10_DECIMAL)
  }
}
"""


def _parse_date(raw: dict | None) -> date | None:
    if not raw:
        return None
    year = raw.get("year")
    month = raw.get("month")
    day = raw.get("day")
    if not (year and month and day):
        return None
    return date(year, month, day)


def _normalize_status(raw: str | None) -> str:
    if not raw:
        return ""
    value = raw.lower()
    if value == "current":
        return "watching"
    return value


class AniListAdapter(TrackerAdapter):
    tracker_type = "anilist"

    def _access_token(self, user) -> str:
        token = user.tracker_access_token
        if not token:
            raise ValueError("User is missing AniList access token.")
        return token

    def _request(self, user, query: str, variables: dict | None = None) -> dict:
        headers = {"Authorization": f"Bearer {self._access_token(user)}"}
        payload = {"query": query, "variables": variables or {}}
        response = httpx.post(
            ANILIST_API_URL,
            json=payload,
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            raise ValueError(data["errors"])
        return data["data"]

    def get_viewer(self, user) -> dict:
        data = self._request(user, VIEWER_QUERY)
        return data["Viewer"]

    def get_user_list(self, user) -> list[dict]:
        user_id = int(user.tracker_user_id) if user.tracker_user_id else None
        if not user_id:
            viewer = self.get_viewer(user)
            user_id = int(viewer["id"])

        data = self._request(user, USER_LIST_QUERY, {"userId": user_id})
        collection = data["MediaListCollection"]
        entries: list[dict] = []
        for list_group in collection.get("lists", []):
            for entry in list_group.get("entries", []):
                media = entry["media"] or {}
                titles = media.get("title") or {}
                studios = media.get("studios") or {}
                studio_nodes = studios.get("nodes") or []
                score = entry.get("score")
                entries.append(
                    {
                        "tracker_type": self.tracker_type,
                        "tracker_id": str(media.get("id")),
                        "title_romaji": titles.get("romaji") or "",
                        "title_english": titles.get("english") or "",
                        "title_native": titles.get("native") or "",
                        "season": (media.get("season") or "").lower(),
                        "season_year": media.get("seasonYear"),
                        "episodes": media.get("episodes"),
                        "studio": studio_nodes[0]["name"] if studio_nodes else "",
                        "cover_image_url": (media.get("coverImage") or {}).get("large") or "",
                        "banner_image_url": media.get("bannerImage") or "",
                        "description": media.get("description") or "",
                        "status": _normalize_status(entry.get("status")),
                        "progress": entry.get("progress") or 0,
                        "score": Decimal(str(score)) if score not in (None, 0) else None,
                        "start_date": _parse_date(entry.get("startedAt")),
                        "completed_date": _parse_date(entry.get("completedAt")),
                    }
                )
        return entries

    def update_progress(self, user, tracker_id: str, progress: int) -> dict:
        data = self._request(
            user,
            UPDATE_PROGRESS_MUTATION,
            {"mediaId": int(tracker_id), "progress": progress},
        )
        return data["SaveMediaListEntry"]
