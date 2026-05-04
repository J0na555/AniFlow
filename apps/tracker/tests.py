from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.anime.models import UserAnime
from apps.tracker.services import sync_user_list


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
