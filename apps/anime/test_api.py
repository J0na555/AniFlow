from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.anime.models import Anime, UserAnime


class AnimeApiTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="api-user",
            password="password123",
        )
        self.client.force_login(self.user)
        self.anime = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="1001",
            title_english="API Target",
            episodes=12,
            cover_image_url="https://cdn.example.com/cover.jpg",
        )
        self.entry = UserAnime.objects.create(
            user=self.user,
            anime=self.anime,
            status="watching",
            progress=3,
        )

    @patch("apps.anime.api_services.get_recommendations")
    @patch("apps.anime.api_services.get_weekly_releases")
    def test_dashboard_matches_frontend_shape(self, mock_releases, mock_recommendations) -> None:
        mock_releases.return_value = {
            "items": [
                {
                    "tracker_id": "501",
                    "title": "Weekly Show",
                    "episode": 7,
                    "airing_at": "2026-05-04T19:00:00+00:00",
                    "cover_image_url": "https://cdn.example.com/release.jpg",
                }
            ]
        }
        mock_recommendations.return_value = {
            "items": [
                {
                    "tracker_id": "901",
                    "title": "Reco Show",
                    "episodes": 24,
                    "cover_image_url": "https://cdn.example.com/reco.jpg",
                }
            ]
        }

        response = self.client.get(reverse("api_dashboard"))
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertIn("stats", payload)
        self.assertIn("continueWatching", payload)
        self.assertIn("watching", payload)
        self.assertIn("weeklyReleases", payload)
        self.assertIn("recommendations", payload)
        self.assertIn("completed", payload)
        self.assertEqual(payload["continueWatching"][0]["id"], self.anime.id)

    def test_anime_search_includes_pagination(self) -> None:
        response = self.client.get(
            reverse("api_anime_search"),
            {"q": "API", "page": 1, "page_size": 10},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("results", payload)
        self.assertIn("pagination", payload)
        self.assertEqual(payload["pagination"]["page"], 1)

    @patch("apps.anime.api_services.tracker_update_progress")
    def test_progress_patch_updates_entry(self, mock_tracker_update_progress) -> None:
        mock_tracker_update_progress.return_value = {"progress": 5, "status": "current"}

        response = self.client.patch(
            reverse("api_library_progress", args=[self.anime.id]),
            data=json.dumps({"progress": 5}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.progress, 5)
        self.assertEqual(self.entry.status, "watching")

    def test_status_endpoint_sets_completed(self) -> None:
        response = self.client.post(
            reverse("api_library_status", args=[self.anime.id]),
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, "completed")
        self.assertEqual(self.entry.progress, self.anime.episodes)

    @patch("apps.anime.api_services.sync_user_list")
    def test_sync_anilist_endpoint_returns_count(self, mock_sync_user_list) -> None:
        mock_sync_user_list.return_value = [self.entry]
        response = self.client.post(reverse("api_sync_anilist"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["synced"], 1)
