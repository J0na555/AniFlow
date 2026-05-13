from __future__ import annotations

from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
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

SEARCH_QUERY = """
query SearchAnime($search: String!, $perPage: Int) {
  Page(page: 1, perPage: $perPage) {
    media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
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
"""

SAVE_LIST_ENTRY_MUTATION = """
mutation SaveListEntry(
  $mediaId: Int!
  $status: MediaListStatus
  $progress: Int
  $score: Float
) {
  SaveMediaListEntry(
    mediaId: $mediaId
    status: $status
    progress: $progress
    score: $score
  ) {
    id
    status
    progress
    score(format: POINT_10_DECIMAL)
  }
}
"""

RECOMMENDATIONS_QUERY = """
query Recommendations($perPage: Int) {
  Page(page: 1, perPage: $perPage) {
    recommendations(sort: RATING_DESC, onList: true) {
      rating
      mediaRecommendation {
        id
        title { romaji english native }
        episodes
        season
        seasonYear
        coverImage { large }
      }
    }
  }
}
"""

WEEKLY_RELEASES_QUERY = """
query WeeklyReleases($from: Int, $to: Int, $perPage: Int) {
  Page(page: 1, perPage: $perPage) {
    airingSchedules(
      airingAt_greater: $from
      airingAt_lesser: $to
      sort: TIME
    ) {
      episode
      airingAt
      media {
        id
        title { romaji english native }
        episodes
        format
        coverImage { large }
      }
    }
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


_ANILIST_STATUS_OVERRIDES = {"watching": "CURRENT"}
_VALID_ANIFLOW_STATUSES = {
    "watching",
    "planning",
    "completed",
    "paused",
    "dropped",
    "repeating",
}


def _to_anilist_status(status: str) -> str:
    value = (status or "").lower()
    if value not in _VALID_ANIFLOW_STATUSES:
        raise ValueError(f"Unsupported AniList status: {status!r}")
    return _ANILIST_STATUS_OVERRIDES.get(value, value.upper())


def _preferred_title(raw: dict | None) -> str:
    titles = raw or {}
    return titles.get("english") or titles.get("romaji") or titles.get("native") or ""


class AniListAdapter(TrackerAdapter):
    tracker_type = "anilist"

    def _access_token(self, user) -> str:
        token = user.tracker_access_token
        if not token:
            raise ValueError("User is missing AniList access token.")
        return token

    def _request(self, user, query: str, variables: dict | None = None) -> dict:
        headers: dict[str, str] = {}
        if user is not None:
            headers["Authorization"] = f"Bearer {self._access_token(user)}"
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

    def search_anime(self, query: str, *, limit: int = 20) -> list[dict]:
        data = self._request(
            None,
            SEARCH_QUERY,
            {"search": query, "perPage": limit},
        )
        page = data.get("Page") or {}
        results: list[dict] = []
        for media in page.get("media", []) or []:
            media_id = media.get("id")
            if not media_id:
                continue
            titles = media.get("title") or {}
            studios = media.get("studios") or {}
            studio_nodes = studios.get("nodes") or []
            results.append(
                {
                    "tracker_type": self.tracker_type,
                    "tracker_id": str(media_id),
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
                }
            )
        return results

    def save_list_entry(
        self,
        user,
        tracker_id: str,
        *,
        status: str,
        progress: int | None = None,
        score: float | None = None,
    ) -> dict:
        variables: dict = {
            "mediaId": int(tracker_id),
            "status": _to_anilist_status(status),
        }
        if progress is not None:
            variables["progress"] = int(progress)
        if score is not None:
            variables["score"] = float(score)
        data = self._request(user, SAVE_LIST_ENTRY_MUTATION, variables)
        return data["SaveMediaListEntry"]

    def get_recommendations(self, user, limit: int = 10) -> list[dict]:
        data = self._request(user, RECOMMENDATIONS_QUERY, {"perPage": limit})
        page = data.get("Page") or {}
        recommendations: list[dict] = []
        seen_tracker_ids: set[str] = set()
        for candidate in page.get("recommendations", []):
            media = candidate.get("mediaRecommendation") or {}
            media_id = media.get("id")
            if not media_id:
                continue
            tracker_id = str(media_id)
            if tracker_id in seen_tracker_ids:
                continue
            seen_tracker_ids.add(tracker_id)
            recommendations.append(
                {
                    "tracker_id": tracker_id,
                    "title": _preferred_title(media.get("title")),
                    "episodes": media.get("episodes"),
                    "season": (media.get("season") or "").lower(),
                    "season_year": media.get("seasonYear"),
                    "cover_image_url": (media.get("coverImage") or {}).get("large") or "",
                    "score": candidate.get("rating"),
                }
            )
        return recommendations

    def get_weekly_releases(self, user, limit: int = 10) -> list[dict]:
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(days=7)
        data = self._request(
            user,
            WEEKLY_RELEASES_QUERY,
            {
                "from": int(now.timestamp()),
                "to": int(window_end.timestamp()),
                "perPage": limit,
            },
        )
        page = data.get("Page") or {}
        releases: list[dict] = []
        for schedule in page.get("airingSchedules", []):
            media = schedule.get("media") or {}
            media_id = media.get("id")
            if not media_id:
                continue
            airing_at = schedule.get("airingAt")
            if not airing_at:
                continue
            releases.append(
                {
                    "tracker_id": str(media_id),
                    "title": _preferred_title(media.get("title")),
                    "episode": schedule.get("episode"),
                    "episodes": media.get("episodes"),
                    "format": (media.get("format") or "").lower(),
                    "cover_image_url": (media.get("coverImage") or {}).get("large") or "",
                    "airing_at": datetime.fromtimestamp(airing_at, tz=timezone.utc),
                }
            )
        return releases
