from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.anime.models import Anime, UserAnime
from apps.anime.services import apply_progress_update
from apps.anime.services import update_user_anime_status
from apps.productivity.services import get_weekly_episodes_watched
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
    def test_plus_one_increment_updates_weekly_stat(self) -> None:
        user = get_user_model().objects.create_user(
            username="weekly-log-user",
            password="password123",
        )
        anime = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="778",
            title_english="Weekly Log Target",
            episodes=12,
        )
        user_anime = UserAnime.objects.create(
            user=user,
            anime=anime,
            status="watching",
            progress=4,
        )

        apply_progress_update(user_anime, progress=5)

        self.assertEqual(get_weekly_episodes_watched(user), 1)

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


class UpdateUserAnimeStatusTests(TestCase):
    def test_planning_to_watching_sets_start_date(self) -> None:
        user = get_user_model().objects.create_user(
            username="status-user",
            password="password123",
        )
        anime = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="880",
            title_english="Status Anime",
            episodes=12,
        )
        UserAnime.objects.create(user=user, anime=anime, status="planning", progress=0)

        updated = update_user_anime_status(user, anime_id=anime.id, status="watching")

        today = timezone.localdate()
        self.assertEqual(updated.status, "watching")
        self.assertEqual(updated.start_date, today)


class UpdateStatusViewTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="htmx-status-user",
            password="password123",
        )
        self.client.force_login(self.user)
        self.anime = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="902",
            title_english="HTMX Target",
            episodes=12,
        )
        self.user_anime = UserAnime.objects.create(
            user=self.user,
            anime=self.anime,
            status="watching",
            progress=3,
        )

    def test_update_status_from_search_uses_hx_redirect(self) -> None:
        referer = "http://testserver/search/?q=x"
        response = self.client.post(
            reverse("anime_status", args=[self.anime.id]),
            {"status": "completed"},
            HTTP_HX_REQUEST="true",
            HTTP_REFERER=referer,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("HX-Redirect"), referer)
        self.user_anime.refresh_from_db()
        self.assertEqual(self.user_anime.status, "completed")

    def test_update_status_from_dashboard_returns_oob_partial(self) -> None:
        response = self.client.post(
            reverse("anime_status", args=[self.anime.id]),
            {"status": "dropped"},
            HTTP_HX_REQUEST="true",
            HTTP_REFERER="http://testserver/",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hx-swap-oob")
        self.user_anime.refresh_from_db()
        self.assertEqual(self.user_anime.status, "dropped")

    def test_update_status_from_dashboard_appends_success_toast(self) -> None:
        response = self.client.post(
            reverse("anime_status", args=[self.anime.id]),
            {"status": "dropped"},
            HTTP_HX_REQUEST="true",
            HTTP_REFERER="http://testserver/",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="toast-container" hx-swap-oob="beforeend"')
        self.assertContains(response, "List status updated.")
        self.assertContains(response, "check-circle")

    def test_update_status_respects_watching_limit(self) -> None:
        settings, _ = UserSettings.objects.get_or_create(user=self.user)
        settings.max_watching_limit = 1
        settings.ignore_watching_limit = False
        settings.save()

        other = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="903",
            title_english="Second",
            episodes=11,
        )
        UserAnime.objects.create(user=self.user, anime=other, status="planning", progress=0)

        response = self.client.post(
            reverse("anime_status", args=[other.id]),
            {"status": "watching"},
            HTTP_HX_REQUEST="true",
            HTTP_REFERER="http://testserver/",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Watching Limit Reached")
        self.assertContains(response, 'id="toast-container" hx-swap-oob="beforeend"')
        self.assertContains(response, "alert-circle")
        planning = UserAnime.objects.get(user=self.user, anime=other)
        self.assertEqual(planning.status, "planning")


class ToastFeedbackViewTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="toast-user",
            password="password123",
        )
        self.client.force_login(self.user)
        self.anime = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="611",
            title_english="Toast Target",
            episodes=12,
        )
        self.user_anime = UserAnime.objects.create(
            user=self.user,
            anime=self.anime,
            status="watching",
            progress=3,
        )

    @patch("apps.anime.views.tracker_update_progress")
    def test_progress_plus_one_appends_success_toast(self, mock_update) -> None:
        mock_update.return_value = {"progress": 4, "status": "CURRENT"}

        response = self.client.post(
            reverse("anime_progress", args=[self.anime.id]),
            {"progress": "4"},
            HTTP_HX_REQUEST="true",
            HTTP_REFERER="http://testserver/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="toast-container" hx-swap-oob="beforeend"')
        self.assertContains(response, "Marked episode 4 watched.")
        self.assertContains(response, "check-circle")

    @patch("apps.anime.views.sync_user_list")
    def test_sync_list_appends_success_toast(self, _mock_sync) -> None:
        response = self.client.post(
            reverse("sync_list"),
            HTTP_HX_REQUEST="true",
            HTTP_REFERER="http://testserver/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="toast-container" hx-swap-oob="beforeend"')
        self.assertContains(response, "AniList synced successfully!")

    def test_ignore_watching_limit_appends_success_toast(self) -> None:
        response = self.client.post(
            reverse("ignore_watching_limit"),
            HTTP_HX_REQUEST="true",
            HTTP_REFERER="http://testserver/",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="toast-container" hx-swap-oob="beforeend"')
        self.assertContains(response, "Watching-limit warnings disabled.")

    @patch("apps.anime.views.sync_user_list")
    def test_sync_list_without_htmx_redirects(self, _mock_sync) -> None:
        response = self.client.post(reverse("sync_list"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("dashboard"))


class DashboardAuthTemplateTests(TestCase):
    def test_logged_out_sidebar_shows_guest_cta(self) -> None:
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Guest")
        self.assertContains(response, "Connect AniList")
        self.assertNotContains(response, "AniList Connected")
        self.assertNotContains(response, "Disconnect AniList")

    @patch("apps.anime.views.sync_user_list")
    def test_logged_in_without_token_shows_reconnect_not_connected(
        self, _mock_sync
    ) -> None:
        user = get_user_model().objects.create_user(
            username="sidebar-user",
            password="password123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reconnect AniList")
        self.assertContains(response, "Not connected")
        self.assertNotContains(response, "AniList Connected")

    def test_sidebar_includes_search_link(self) -> None:
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("anime_search"))
        self.assertContains(response, ">Search</span>")

    def test_search_page_marks_nav_item_active(self) -> None:
        response = self.client.get(reverse("anime_search"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("anime_search")}" class="neo-nav-item active"',
        )
