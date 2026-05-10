from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.anime.models import Anime

from .services import get_recommendations


class RecommendationServiceTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="recommendation-user",
            password="password123",
            tracker_type="anilist",
        )

    @patch("apps.recommendations.services.tracker_get_recommendations")
    def test_get_recommendations_attaches_local_anime_ids(self, mock_tracker_get) -> None:
        mock_tracker_get.return_value = [
            {
                "tracker_id": "9901",
                "title": "Recommendation Target",
                "episodes": 12,
                "season": "spring",
                "season_year": 2025,
                "cover_image_url": "https://example.com/recommendation.jpg",
            }
        ]

        payload = get_recommendations(self.user, limit=1)

        self.assertEqual(len(payload["items"]), 1)
        item = payload["items"][0]
        anime = Anime.objects.get(tracker_type="anilist", tracker_id="9901")
        self.assertEqual(item["anime_id"], anime.id)
        self.assertEqual(anime.title_english, "Recommendation Target")
