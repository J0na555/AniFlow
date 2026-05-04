from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.anime.models import Anime, UserAnime
from apps.anime.services import apply_progress_update
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
