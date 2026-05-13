from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.anime.models import Anime, UserAnime
from apps.users.models import UserSettings


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

    @patch("apps.anime.api_services.tracker_save_list_entry")
    def test_status_endpoint_pushes_to_tracker_when_connected(
        self, mock_tracker_save
    ) -> None:
        mock_tracker_save.return_value = {
            "id": 1,
            "status": "COMPLETED",
            "progress": 12,
        }
        self.user.tracker_access_token = "connected-token"
        self.user.save(update_fields=["tracker_access_token"])

        response = self.client.post(
            reverse("api_library_status", args=[self.anime.id]),
            data=json.dumps({"status": "completed"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        mock_tracker_save.assert_called_once_with(
            self.user,
            self.anime.tracker_id,
            status="completed",
            progress=self.anime.episodes,
        )
        self.assertNotIn("tracker_warning", response.json())

    @patch("apps.anime.api_services.logger.warning")
    @patch("apps.anime.api_services.tracker_save_list_entry")
    def test_status_endpoint_returns_tracker_warning_when_tracker_fails(
        self, mock_tracker_save, _mock_log_warning
    ) -> None:
        mock_tracker_save.side_effect = RuntimeError("AniList error")
        self.user.tracker_access_token = "connected-token"
        self.user.save(update_fields=["tracker_access_token"])

        response = self.client.post(
            reverse("api_library_status", args=[self.anime.id]),
            data=json.dumps({"status": "paused"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("tracker_warning", body)
        self.assertIn("tracker", body["tracker_warning"].lower())
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, "paused")

    @patch("apps.tracker.services.save_list_entry")
    def test_library_add_happy_path(self, mock_save_entry) -> None:
        mock_save_entry.return_value = {
            "id": 10,
            "status": "PLANNING",
            "progress": 0,
            "score": None,
        }
        self.user.tracker_access_token = "tok"
        self.user.save(update_fields=["tracker_access_token"])
        Anime.objects.create(
            tracker_type="anilist",
            tracker_id="4400",
            title_english="Discoverable Add",
            episodes=13,
        )

        response = self.client.post(
            reverse("api_library_add"),
            data=json.dumps({"tracker_id": "4400", "status": "planning"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["item"]["tracker_id"], "4400")
        self.assertEqual(payload["item"]["status"], "planning")
        mock_save_entry.assert_called_once()

    def test_library_add_requires_authentication(self) -> None:
        self.client.logout()
        response = self.client.post(
            reverse("api_library_add"),
            data=json.dumps({"tracker_id": "4400", "status": "planning"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_library_add_requires_tracker_connection(self) -> None:
        self.assertEqual(self.user.tracker_access_token, "")
        response = self.client.post(
            reverse("api_library_add"),
            data=json.dumps({"tracker_id": "4400", "status": "planning"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "tracker_not_connected")

    @patch("apps.tracker.services.save_list_entry")
    def test_library_add_invalid_status(self, mock_save_entry) -> None:
        self.user.tracker_access_token = "tok"
        self.user.save(update_fields=["tracker_access_token"])
        Anime.objects.create(
            tracker_type="anilist",
            tracker_id="4401",
            title_english="Status Target",
            episodes=12,
        )

        response = self.client.post(
            reverse("api_library_add"),
            data=json.dumps({"tracker_id": "4401", "status": "bogus"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_status")
        mock_save_entry.assert_not_called()

    @patch("apps.tracker.services.save_list_entry")
    def test_library_add_unknown_tracker_returns_404(self, mock_save_entry) -> None:
        self.user.tracker_access_token = "tok"
        self.user.save(update_fields=["tracker_access_token"])

        response = self.client.post(
            reverse("api_library_add"),
            data=json.dumps({"tracker_id": "999999", "status": "planning"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "not_found")
        mock_save_entry.assert_not_called()

    @patch("apps.tracker.services.save_list_entry")
    def test_library_add_conflict_when_watching_limit_reached(
        self, mock_save_entry
    ) -> None:
        mock_save_entry.return_value = {"id": 1, "status": "CURRENT"}
        self.user.tracker_access_token = "tok"
        self.user.save(update_fields=["tracker_access_token"])
        settings, _ = UserSettings.objects.get_or_create(user=self.user)
        settings.max_watching_limit = 1
        settings.ignore_watching_limit = False
        settings.save(update_fields=["max_watching_limit", "ignore_watching_limit"])

        Anime.objects.create(
            tracker_type="anilist",
            tracker_id="5500",
            title_english="Second Title",
            episodes=11,
        )

        response = self.client.post(
            reverse("api_library_add"),
            data=json.dumps({"tracker_id": "5500", "status": "watching"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "watching_limit_reached")
        mock_save_entry.assert_not_called()

    @patch("apps.anime.services.logger.warning")
    @patch("apps.tracker.services.save_list_entry")
    def test_library_add_succeeds_locally_when_tracker_errors(
        self, mock_save_entry, _mock_log_warning
    ) -> None:
        mock_save_entry.side_effect = RuntimeError("upstream failure")
        self.user.tracker_access_token = "tok"
        self.user.save(update_fields=["tracker_access_token"])
        Anime.objects.create(
            tracker_type="anilist",
            tracker_id="6600",
            title_english="Shaky Tracker",
            episodes=10,
        )

        response = self.client.post(
            reverse("api_library_add"),
            data=json.dumps({"tracker_id": "6600", "status": "paused"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            UserAnime.objects.filter(
                user=self.user, anime__tracker_id="6600", status="paused"
            ).exists()
        )

    @patch("apps.anime.api_services.sync_user_list")
    def test_sync_anilist_endpoint_returns_count(self, mock_sync_user_list) -> None:
        mock_sync_user_list.return_value = [self.entry]
        response = self.client.post(reverse("api_sync_anilist"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["synced"], 1)
