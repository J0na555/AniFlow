from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.common.forms import NEO_CHECKBOX_CLASS, NEO_INPUT_CLASS
from apps.users.forms import UserSettingsForm
from apps.users.views import POST_LOGIN_REDIRECT_SESSION_KEY, _safe_post_login_redirect

OAUTH_SETTINGS = {
    "ANILIST_CLIENT_ID": "test-client-id",
    "ANILIST_CLIENT_SECRET": "test-client-secret",
    "ANILIST_REDIRECT_URI": "http://localhost:8000/auth/anilist/callback/",
    "FRONTEND_ALLOWED_REDIRECT_ORIGINS": [
        "http://localhost:3000",
        "https://app.example.com",
    ],
}


@override_settings(**OAUTH_SETTINGS)
class SafePostLoginRedirectTests(TestCase):
    def test_allows_configured_origin_with_path(self) -> None:
        target = "http://localhost:3000/library"
        self.assertEqual(_safe_post_login_redirect(target), target)

    def test_allows_origin_without_trailing_slash_mismatch(self) -> None:
        target = "https://app.example.com/auth/callback"
        self.assertEqual(_safe_post_login_redirect(target), target)

    def test_rejects_unknown_origin(self) -> None:
        self.assertIsNone(_safe_post_login_redirect("https://evil.com/phish"))

    def test_rejects_relative_url(self) -> None:
        self.assertIsNone(_safe_post_login_redirect("/dashboard"))

    def test_rejects_scheme_relative_url(self) -> None:
        self.assertIsNone(_safe_post_login_redirect("//evil.com/path"))

    def test_rejects_empty_candidate(self) -> None:
        self.assertIsNone(_safe_post_login_redirect(""))
        self.assertIsNone(_safe_post_login_redirect(None))


@override_settings(**OAUTH_SETTINGS)
class AnilistLoginTests(TestCase):
    def test_login_redirects_to_anilist_authorize(self) -> None:
        response = self.client.get(reverse("anilist_login"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("anilist.co/api/v2/oauth/authorize", response["Location"])
        self.assertIn("client_id=test-client-id", response["Location"])
        self.assertIn("state=", response["Location"])
        self.assertIn("anilist_oauth_state", self.client.session)

    def test_login_stores_safe_next_in_session(self) -> None:
        next_url = "http://localhost:3000/library"
        response = self.client.get(reverse("anilist_login"), {"next": next_url})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session[POST_LOGIN_REDIRECT_SESSION_KEY], next_url)

    def test_login_ignores_unsafe_next(self) -> None:
        response = self.client.get(
            reverse("anilist_login"),
            {"next": "https://evil.com/steal"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertNotIn(POST_LOGIN_REDIRECT_SESSION_KEY, self.client.session)


@override_settings(**OAUTH_SETTINGS)
class AnilistCallbackTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def _prime_oauth_state(self, state: str = "valid-state") -> None:
        session = self.client.session
        session["anilist_oauth_state"] = state
        session.save()

    def test_callback_rejects_state_mismatch(self) -> None:
        self._prime_oauth_state("expected-state")

        response = self.client.get(
            reverse("anilist_callback"),
            {"code": "auth-code", "state": "wrong-state"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Invalid OAuth response", status_code=400)

    def test_callback_rejects_missing_code(self) -> None:
        self._prime_oauth_state("valid-state")

        response = self.client.get(
            reverse("anilist_callback"),
            {"state": "valid-state"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Invalid OAuth response", status_code=400)

    def test_callback_rejects_oauth_error_param(self) -> None:
        response = self.client.get(
            reverse("anilist_callback"),
            {"error": "access_denied"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "authorization error", status_code=400)

    @patch("apps.users.views.sync_user_list")
    @patch("apps.users.views._fetch_viewer")
    @patch("apps.users.views.httpx.post")
    def test_callback_exchanges_code_and_logs_in_user(
        self,
        mock_httpx_post,
        mock_fetch_viewer,
        mock_sync_user_list,
    ) -> None:
        self._prime_oauth_state("valid-state")

        token_response = MagicMock()
        token_response.raise_for_status.return_value = None
        token_response.json.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
        }
        mock_httpx_post.return_value = token_response
        mock_fetch_viewer.return_value = {"id": 4242, "name": "TestViewer"}

        response = self.client.get(
            reverse("anilist_callback"),
            {"code": "auth-code", "state": "valid-state"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("dashboard"))
        user = get_user_model().objects.get(tracker_user_id="4242")
        self.assertEqual(user.tracker_access_token, "access-token")
        self.assertEqual(user.tracker_refresh_token, "refresh-token")
        mock_sync_user_list.assert_called_once_with(user)

    @patch("apps.users.views.sync_user_list")
    @patch("apps.users.views._fetch_viewer")
    @patch("apps.users.views.httpx.post")
    def test_callback_redirects_to_safe_post_login_target(
        self,
        mock_httpx_post,
        mock_fetch_viewer,
        mock_sync_user_list,
    ) -> None:
        self._prime_oauth_state("valid-state")
        session = self.client.session
        session[POST_LOGIN_REDIRECT_SESSION_KEY] = "http://localhost:3000/library"
        session.save()

        token_response = MagicMock()
        token_response.raise_for_status.return_value = None
        token_response.json.return_value = {
            "access_token": "access-token",
            "refresh_token": "",
        }
        mock_httpx_post.return_value = token_response
        mock_fetch_viewer.return_value = {"id": 7777, "name": "RedirectUser"}

        response = self.client.get(
            reverse("anilist_callback"),
            {"code": "auth-code", "state": "valid-state"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "http://localhost:3000/library")
        mock_sync_user_list.assert_called_once()


class SettingsFormWidgetTests(TestCase):
    def test_form_controls_use_shared_neo_widget_classes(self) -> None:
        form = UserSettingsForm()

        self.assertIn("neo-input", NEO_INPUT_CLASS)
        self.assertIn(NEO_INPUT_CLASS, str(form["preferred_source"]))
        self.assertIn(NEO_INPUT_CLASS, str(form["max_watching_limit"]))
        self.assertIn(NEO_CHECKBOX_CLASS, str(form["ignore_watching_limit"]))

    def test_settings_page_renders_styled_controls(self) -> None:
        user = get_user_model().objects.create_user(
            username="settings-widget-user",
            password="password123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("user_settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "neo-input")
