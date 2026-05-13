from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.anime.models import UserAnime
from apps.tracker.adapters.anilist_adapter import SAVE_LIST_ENTRY_MUTATION
from apps.tracker.adapters.anilist_adapter import SEARCH_QUERY
from apps.tracker.adapters.anilist_adapter import AniListAdapter
from apps.tracker.services import sync_user_list


class AniListAdapterSearchAndSaveTests(TestCase):
    def setUp(self) -> None:
        self.adapter = AniListAdapter()
        self.user = get_user_model().objects.create_user(
            username="anilist-adapter-user",
            password="password123",
            tracker_type="anilist",
            tracker_access_token="test-access-token",
        )

    @patch.object(AniListAdapter, "_request")
    def test_search_anime_returns_tracker_compatible_payload(self, mock_request) -> None:
        mock_request.return_value = {
            "Page": {
                "media": [
                    {
                        "id": 100,
                        "title": {
                            "romaji": "Romaji Title",
                            "english": "English Title",
                            "native": "Native Title",
                        },
                        "season": "FALL",
                        "seasonYear": 2025,
                        "episodes": 24,
                        "description": "A show.",
                        "coverImage": {"large": "https://cdn.example/large.jpg"},
                        "bannerImage": "https://cdn.example/banner.jpg",
                        "studios": {"nodes": [{"name": "MAPPA"}, {"name": "Ignored"}]},
                    },
                    {"title": {"romaji": "No id"}, "season": "WINTER"},
                ]
            }
        }

        results = self.adapter.search_anime("naruto", limit=10)

        self.assertEqual(len(results), 1)
        hit = results[0]
        self.assertEqual(hit["tracker_type"], "anilist")
        self.assertEqual(hit["tracker_id"], "100")
        self.assertEqual(hit["title_english"], "English Title")
        self.assertEqual(hit["title_romaji"], "Romaji Title")
        self.assertEqual(hit["title_native"], "Native Title")
        self.assertEqual(hit["season"], "fall")
        self.assertEqual(hit["season_year"], 2025)
        self.assertEqual(hit["episodes"], 24)
        self.assertEqual(hit["studio"], "MAPPA")
        self.assertEqual(hit["cover_image_url"], "https://cdn.example/large.jpg")
        self.assertEqual(hit["banner_image_url"], "https://cdn.example/banner.jpg")
        self.assertEqual(hit["description"], "A show.")

        mock_request.assert_called_once_with(
            None,
            SEARCH_QUERY,
            {"search": "naruto", "perPage": 10},
        )

    @patch.object(AniListAdapter, "_request")
    def test_save_list_entry_maps_watching_to_current(self, mock_request) -> None:
        mock_request.return_value = {
            "SaveMediaListEntry": {
                "id": 9,
                "status": "CURRENT",
                "progress": 4,
                "score": None,
            }
        }

        out = self.adapter.save_list_entry(
            self.user, "55", status="watching", progress=4, score=None
        )

        self.assertEqual(out["status"], "CURRENT")
        mock_request.assert_called_once_with(
            self.user,
            SAVE_LIST_ENTRY_MUTATION,
            {"mediaId": 55, "status": "CURRENT", "progress": 4},
        )

    @patch.object(AniListAdapter, "_request")
    def test_save_list_entry_maps_other_statuses_uppercase(self, mock_request) -> None:
        mock_request.return_value = {
            "SaveMediaListEntry": {
                "id": 1,
                "status": "PLANNING",
                "progress": 0,
                "score": None,
            }
        }

        self.adapter.save_list_entry(self.user, "12", status="planning")
        mock_request.assert_called_once_with(
            self.user,
            SAVE_LIST_ENTRY_MUTATION,
            {"mediaId": 12, "status": "PLANNING"},
        )

        mock_request.reset_mock()
        mock_request.return_value = {
            "SaveMediaListEntry": {
                "id": 1,
                "status": "COMPLETED",
                "progress": 12,
                "score": 8.5,
            }
        }
        self.adapter.save_list_entry(
            self.user, "12", status="completed", progress=12, score=8.5
        )
        mock_request.assert_called_once_with(
            self.user,
            SAVE_LIST_ENTRY_MUTATION,
            {
                "mediaId": 12,
                "status": "COMPLETED",
                "progress": 12,
                "score": 8.5,
            },
        )

    def test_save_list_entry_rejects_unknown_status(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.adapter.save_list_entry(self.user, "1", status="not-a-real-status")
        self.assertIn("Unsupported AniList status", str(ctx.exception))


class SyncUserListTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="sync-user",
            password="password123",
            tracker_type="anilist",
        )

    @patch("apps.tracker.services.AniListAdapter.get_user_list")
    def test_sync_creates_and_updates_user_entries(self, mock_get_user_list) -> None:
        mock_get_user_list.side_effect = [
            [
                {
                    "tracker_type": "anilist",
                    "tracker_id": "101",
                    "title_english": "Sync Target",
                    "status": "watching",
                    "progress": 3,
                    "episodes": 12,
                }
            ],
            [
                {
                    "tracker_type": "anilist",
                    "tracker_id": "101",
                    "title_english": "Sync Target",
                    "status": "completed",
                    "progress": 12,
                    "episodes": 12,
                }
            ],
        ]

        first_sync = sync_user_list(self.user)
        self.assertEqual(len(first_sync), 1)
        entry = UserAnime.objects.get(user=self.user, anime__tracker_id="101")
        self.assertEqual(entry.status, "watching")
        self.assertEqual(entry.progress, 3)

        second_sync = sync_user_list(self.user)
        self.assertEqual(len(second_sync), 1)
        entry.refresh_from_db()
        self.assertEqual(UserAnime.objects.filter(user=self.user).count(), 1)
        self.assertEqual(entry.status, "completed")
        self.assertEqual(entry.progress, 12)
