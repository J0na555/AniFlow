from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.anime.models import Anime
from apps.streaming.matcher import match_anime
from apps.streaming.models import AnimeStreamingMapping, StreamingSource
from apps.streaming.services import get_or_create_mapping
from apps.streaming.types import StreamingCandidate, StreamingMatch


class _StaticSearchAdapter:
    def __init__(self, candidates: list[StreamingCandidate]) -> None:
        self._candidates = candidates

    def search(self, query: str) -> list[StreamingCandidate]:
        return self._candidates


class MatcherTests(TestCase):
    def setUp(self) -> None:
        self.anime = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="901",
            title_english="Matcher Target",
            season_year=2024,
            episodes=12,
            studio="Bones",
        )
        self.candidate = StreamingCandidate(
            title="Matcher Target",
            slug="matcher-target",
            year=2024,
            episodes=12,
            studio="Bones",
        )

    @patch("apps.streaming.matcher.score_candidate", return_value=0.8)
    def test_match_requires_confirmation_in_mid_threshold(self, _mock_score) -> None:
        match = match_anime(self.anime, _StaticSearchAdapter([self.candidate]))

        self.assertIsNotNone(match)
        self.assertTrue(match.needs_confirmation)
        self.assertEqual(match.candidate.slug, "matcher-target")

    @patch("apps.streaming.matcher.score_candidate", return_value=0.7)
    def test_match_rejects_below_confirmation_threshold(self, _mock_score) -> None:
        match = match_anime(self.anime, _StaticSearchAdapter([self.candidate]))

        self.assertIsNone(match)


class StreamingMappingServiceTests(TestCase):
    def setUp(self) -> None:
        self.anime = Anime.objects.create(
            tracker_type="anilist",
            tracker_id="902",
            title_english="Mapped Target",
        )
        self.source = StreamingSource.objects.create(
            name="Mapping Source",
            base_url="https://example.com",
            search_url_template="https://example.com/search?q={query}",
            episode_pattern="/watch/{slug}-episode-{episode}",
            priority=10,
        )

    @patch("apps.streaming.services.match_anime")
    def test_get_or_create_mapping_creates_unverified_mapping(self, mock_match_anime) -> None:
        mock_match_anime.return_value = StreamingMatch(
            candidate=StreamingCandidate(title="Mapped Target", slug="mapped-target"),
            score=0.801,
            needs_confirmation=True,
        )

        mapping, created = get_or_create_mapping(
            self.anime,
            self.source,
            _StaticSearchAdapter([]),
        )

        self.assertTrue(created)
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.source_identifier, "mapped-target")
        self.assertEqual(mapping.confidence_score, Decimal("0.801"))
        self.assertFalse(mapping.verified)

    @patch("apps.streaming.services.match_anime")
    def test_get_or_create_mapping_reuses_existing_mapping(self, mock_match_anime) -> None:
        existing = AnimeStreamingMapping.objects.create(
            anime=self.anime,
            source=self.source,
            source_identifier="existing-slug",
            confidence_score=Decimal("0.950"),
            verified=True,
        )

        mapping, created = get_or_create_mapping(
            self.anime,
            self.source,
            _StaticSearchAdapter([]),
        )

        self.assertFalse(created)
        self.assertEqual(mapping, existing)
        mock_match_anime.assert_not_called()
