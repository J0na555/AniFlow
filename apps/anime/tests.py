from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.anime.models import Anime, UserAnime
from apps.anime.services import WatchingLimitReached
from apps.anime.services import add_to_library
from apps.anime.services import apply_progress_update
from apps.users.models import UserSettings
from apps.streaming.models import StreamingSource
from apps.streaming.router import StreamingRoute


class ResumeAnimeViewTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="resume-user",
            password="password123",
        )
        self.client.force_login(self.user)
        self.anime = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="501",
            title_english="Resume Target",
            episodes=24,
        )
        self.user_anime = UserAnime.objects.create(
            user=self.user,
            anime=self.anime,
            status="watching",
            progress=2,
        )

    @patch("apps.anime.views.resolve_streaming_route")
    def test_resume_redirects_to_direct_route_when_available(self, mock_resolve) -> None:
        mock_resolve.return_value = StreamingRoute(
            url="https://example.com/watch/episode-3",
            source=None,
            needs_confirmation=False,
        )

        response = self.client.get(reverse("anime_resume", args=[self.anime.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://example.com/watch/episode-3")

    @patch("apps.anime.views.resolve_streaming_route")
    def test_resume_redirects_to_confirmation_when_match_unverified(
        self, mock_resolve
    ) -> None:
        source, _ = StreamingSource.objects.get_or_create(
            name="Gogoanime",
            defaults={
                "base_url": "https://example.com",
                "search_url_template": "https://example.com/search?q={query}",
                "episode_pattern": "/watch/{slug}-episode-{episode}",
                "priority": 1,
            },
        )
        mock_resolve.return_value = StreamingRoute(
            url="https://example.com/watch/episode-3",
            source=source,
            needs_confirmation=True,
        )

        response = self.client.get(reverse("anime_resume", args=[self.anime.id]))

        expected_base = reverse(
            "anime_confirm_mapping",
            kwargs={"anime_id": self.anime.id, "source_id": source.id},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{expected_base}?next_episode=3")


class ApplyProgressUpdateTests(TestCase):
    def test_progress_marks_start_and_completion_dates(self) -> None:
        user = get_user_model().objects.create_user(
            username="progress-user",
            password="password123",
        )
        anime = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="777",
            title_english="Progress Target",
            episodes=12,
        )
        user_anime = UserAnime.objects.create(
            user=user,
            anime=anime,
            status="planning",
            progress=0,
        )

        updated = apply_progress_update(user_anime, progress=12, tracker_status="watching")

        today = timezone.localdate()
        self.assertEqual(updated.status, "completed")
        self.assertEqual(updated.progress, 12)
        self.assertEqual(updated.start_date, today)
        self.assertEqual(updated.completed_date, today)


class AddToLibraryTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="library-user",
            password="password123",
            tracker_type="anilist",
            tracker_access_token="token",
        )

    def _sample_payload(self, tracker_id: str = "9001") -> dict:
        return {
            "tracker_type": "anilist",
            "tracker_id": tracker_id,
            "title_romaji": "Payload Romaji",
            "title_english": "Payload English",
            "title_native": "",
            "season": "spring",
            "season_year": 2024,
            "episodes": 12,
            "studio": "Test Studio",
            "cover_image_url": "https://cdn.example/p.jpg",
            "banner_image_url": "",
            "description": "Synopsis",
        }

    @patch("apps.tracker.services.save_list_entry")
    def test_add_to_library_with_payload_creates_anime_and_calls_tracker(
        self, mock_save_entry
    ) -> None:
        mock_save_entry.return_value = {
            "id": 1,
            "status": "PLANNING",
            "progress": 0,
            "score": None,
        }

        entry = add_to_library(
            self.user,
            tracker_id="9001",
            status="planning",
            payload=self._sample_payload(),
        )

        anime = Anime.objects.get(tracker_type="anilist", tracker_id="9001")
        self.assertEqual(anime.title_english, "Payload English")
        self.assertEqual(entry.user, self.user)
        self.assertEqual(entry.anime, anime)
        self.assertEqual(entry.status, "planning")
        mock_save_entry.assert_called_once_with(
            self.user,
            "9001",
            status="planning",
            progress=0,
            score=None,
        )

    @patch("apps.tracker.services.save_list_entry")
    def test_add_to_library_reuses_existing_anime_without_payload(
        self, mock_save_entry
    ) -> None:
        mock_save_entry.return_value = {"id": 2, "status": "CURRENT", "progress": 1}
        anime = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="7777",
            title_english="Existing",
            episodes=24,
        )

        entry = add_to_library(
            self.user,
            tracker_id="7777",
            status="watching",
            progress=1,
            payload=None,
        )

        self.assertEqual(Anime.objects.filter(tracker_id="7777").count(), 1)
        self.assertEqual(entry.anime_id, anime.id)
        mock_save_entry.assert_called_once()

    @patch("apps.tracker.services.save_list_entry")
    def test_add_to_library_invalid_status(self, mock_save_entry) -> None:
        with self.assertRaises(ValueError):
            add_to_library(
                self.user,
                tracker_id="9001",
                status="on-hold-invalid",
                payload=self._sample_payload(),
            )
        mock_save_entry.assert_not_called()

    def test_add_to_library_missing_local_anime_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            add_to_library(
                self.user,
                tracker_id="99999",
                status="planning",
                payload=None,
            )
        self.assertIn("tracker_id", str(ctx.exception))

    @patch("apps.tracker.services.save_list_entry")
    def test_add_to_library_enforces_watching_limit(self, mock_save_entry) -> None:
        mock_save_entry.return_value = {"id": 1, "status": "CURRENT"}
        settings, _ = UserSettings.objects.get_or_create(user=self.user)
        settings.max_watching_limit = 1
        settings.ignore_watching_limit = False
        settings.save(update_fields=["max_watching_limit", "ignore_watching_limit"])

        other_anime = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="existing-watch",
            title_english="Already Watching",
            episodes=12,
        )
        UserAnime.objects.create(
            user=self.user,
            anime=other_anime,
            status="watching",
            progress=1,
        )

        with self.assertRaises(WatchingLimitReached):
            add_to_library(
                self.user,
                tracker_id="9002",
                status="watching",
                payload=self._sample_payload("9002"),
            )
        mock_save_entry.assert_not_called()
        self.assertFalse(UserAnime.objects.filter(anime__tracker_id="9002").exists())

    @patch("apps.anime.services.logger.warning")
    @patch("apps.tracker.services.save_list_entry")
    def test_add_to_library_tracker_error_still_persists_locally(
        self, mock_save_entry, _mock_log_warning
    ) -> None:
        mock_save_entry.side_effect = RuntimeError("AniList unavailable")

        entry = add_to_library(
            self.user,
            tracker_id="9003",
            status="dropped",
            payload=self._sample_payload("9003"),
        )

        self.assertEqual(entry.status, "dropped")
        mock_save_entry.assert_called_once()
        self.assertTrue(
            UserAnime.objects.filter(
                user=self.user, anime__tracker_id="9003"
            ).exists()
        )

    @patch("apps.tracker.services.save_list_entry")
    def test_add_to_library_skips_limit_when_already_watching_same_title(
        self, mock_save_entry
    ) -> None:
        mock_save_entry.return_value = {"id": 1, "status": "CURRENT"}
        settings, _ = UserSettings.objects.get_or_create(user=self.user)
        settings.max_watching_limit = 1
        settings.ignore_watching_limit = False
        settings.save(update_fields=["max_watching_limit", "ignore_watching_limit"])

        payload = self._sample_payload("9004")
        anime = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="9004",
            title_english="Solo",
            episodes=12,
        )
        UserAnime.objects.create(
            user=self.user,
            anime=anime,
            status="watching",
            progress=2,
        )

        entry = add_to_library(
            self.user,
            tracker_id="9004",
            status="watching",
            progress=5,
            payload=payload,
        )

        self.assertEqual(entry.progress, 5)
        mock_save_entry.assert_called_once()
