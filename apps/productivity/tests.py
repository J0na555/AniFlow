from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.anime.models import Anime, UserAnime, UserAnimeProgressEvent
from apps.anime.services import apply_progress_update
from apps.productivity.services import enable_watching_limit_override
from apps.productivity.services import get_productivity_stats
from apps.productivity.services import get_watching_limit_state
from apps.productivity.services import get_weekly_episodes_watched
from apps.users.models import UserSettings


class WeeklyEpisodesWatchedTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="weekly-user",
            password="password123",
        )
        self.anime = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="1001",
            title_english="Weekly Target",
            episodes=24,
        )
        self.user_anime = UserAnime.objects.create(
            user=self.user,
            anime=self.anime,
            status="watching",
            progress=10,
        )

    def test_progress_increment_counts_delta_not_total(self) -> None:
        apply_progress_update(self.user_anime, progress=11)

        self.assertEqual(get_weekly_episodes_watched(self.user), 1)
        stats = get_productivity_stats(self.user)
        self.assertEqual(stats.weekly_episodes, 1)

    def test_multiple_increments_sum_deltas(self) -> None:
        apply_progress_update(self.user_anime, progress=11)
        self.user_anime.refresh_from_db()
        apply_progress_update(self.user_anime, progress=13)

        self.assertEqual(get_weekly_episodes_watched(self.user), 3)

    def test_progress_decrease_does_not_count(self) -> None:
        apply_progress_update(self.user_anime, progress=8)

        self.assertEqual(get_weekly_episodes_watched(self.user), 0)
        self.assertEqual(UserAnimeProgressEvent.objects.filter(user=self.user).count(), 0)

    def test_events_outside_current_week_are_excluded(self) -> None:
        UserAnimeProgressEvent.objects.create(
            user=self.user,
            anime=self.anime,
            delta=5,
        )
        event = UserAnimeProgressEvent.objects.get(user=self.user)
        UserAnimeProgressEvent.objects.filter(pk=event.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=10)
        )

        self.assertEqual(get_weekly_episodes_watched(self.user), 0)


class ProgressUpdateViewWeeklyStatTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="progress-view-user",
            password="password123",
        )
        self.client.force_login(self.user)
        self.anime = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="1002",
            title_english="View Target",
            episodes=24,
        )
        self.user_anime = UserAnime.objects.create(
            user=self.user,
            anime=self.anime,
            status="watching",
            progress=10,
        )

    @patch("apps.anime.views.tracker_update_progress")
    def test_plus_one_updates_weekly_episodes_in_dashboard(self, mock_tracker) -> None:
        mock_tracker.return_value = {"progress": 11, "status": "watching"}

        response = self.client.post(
            reverse("anime_progress", args=[self.anime.id]),
            {"progress": "11"},
            HTTP_HX_REQUEST="true",
            HTTP_REFERER="http://testserver/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Episodes watched this week")
        self.assertEqual(get_weekly_episodes_watched(self.user), 1)


class ProductivityStatsTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="stats-user",
            password="password123",
        )

    def test_completion_rate_excludes_planning_entries(self) -> None:
        for tracker_id, status in [
            ("2001", "completed"),
            ("2002", "completed"),
            ("2003", "watching"),
            ("2004", "planning"),
        ]:
            anime = Anime.objects.create(
                tracker_type="anilist",
                tracker_id=tracker_id,
                title_english=f"Title {tracker_id}",
                episodes=12,
            )
            UserAnime.objects.create(
                user=self.user,
                anime=anime,
                status=status,
                progress=0,
            )

        stats = get_productivity_stats(self.user)

        self.assertEqual(stats.watching_count, 1)
        self.assertEqual(stats.completed_count, 2)
        self.assertEqual(stats.completion_rate, 66.7)

    def test_completion_rate_zero_when_nothing_started(self) -> None:
        anime = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="2005",
            title_english="Planning Only",
            episodes=12,
        )
        UserAnime.objects.create(
            user=self.user,
            anime=anime,
            status="planning",
            progress=0,
        )

        stats = get_productivity_stats(self.user)

        self.assertEqual(stats.completion_rate, 0.0)


class WatchingLimitStateTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="limit-user",
            password="password123",
        )
        self.settings, _ = UserSettings.objects.get_or_create(user=self.user)

    def test_limit_reached_when_at_capacity(self) -> None:
        self.settings.max_watching_limit = 2
        self.settings.ignore_watching_limit = False
        self.settings.save()

        state = get_watching_limit_state(self.user, watching_count=2)

        self.assertTrue(state.enabled)
        self.assertTrue(state.reached)
        self.assertEqual(state.remaining_slots, 0)
        self.assertIn("Watching limit reached", state.message)

    def test_limit_disabled_when_zero(self) -> None:
        self.settings.max_watching_limit = 0
        self.settings.save()

        state = get_watching_limit_state(self.user, watching_count=5)

        self.assertFalse(state.enabled)
        self.assertFalse(state.reached)
        self.assertEqual(state.remaining_slots, 0)
        self.assertEqual(state.message, "Watching limit is disabled.")

    def test_ignored_limit_does_not_block(self) -> None:
        self.settings.max_watching_limit = 1
        self.settings.ignore_watching_limit = True
        self.settings.save()

        state = get_watching_limit_state(self.user, watching_count=3)

        self.assertTrue(state.enabled)
        self.assertFalse(state.reached)
        self.assertIn("ignored", state.message)

    def test_enable_watching_limit_override_persists_flag(self) -> None:
        self.settings.ignore_watching_limit = False
        self.settings.save()

        updated = enable_watching_limit_override(self.user)

        self.assertTrue(updated.ignore_watching_limit)
        self.settings.refresh_from_db()
        self.assertTrue(self.settings.ignore_watching_limit)
