from datetime import datetime, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.anime.models import Anime

from .services import get_weekly_releases


class WeeklyReleaseServiceTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="release-user",
            password="password123",
            tracker_type="anilist",
        )

    @patch("apps.releases.services.tracker_get_weekly_releases")
    def test_get_weekly_releases_attaches_local_anime_ids(self, mock_tracker_get) -> None:
        mock_tracker_get.return_value = [
            {
                "tracker_id": "8801",
                "title": "Weekly Release Target",
                "episode": 7,
                "episodes": 12,
                "format": "tv",
                "cover_image_url": "https://example.com/release.jpg",
                "airing_at": datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc),
            }
        ]

        payload = get_weekly_releases(self.user, limit=1)

        self.assertEqual(len(payload["items"]), 1)
        item = payload["items"][0]
        anime = Anime.objects.get(tracker_type="anilist", tracker_id="8801")
        self.assertEqual(item["anime_id"], anime.id)
        self.assertEqual(anime.title_english, "Weekly Release Target")
