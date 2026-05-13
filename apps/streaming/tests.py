from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from apps.anime.models import Anime
from apps.streaming.matcher import match_anime
from apps.streaming.models import AnimeStreamingMapping, StreamingSource
from apps.streaming.services import get_or_create_mapping
from apps.streaming.sources import get_adapter_for_source
from apps.streaming.sources.aniwatch_source import AniWatchSourceAdapter
from apps.streaming.sources.aniwaves_source import AniWavesSourceAdapter
from apps.streaming.sources.gogoanime_source import GogoanimeSourceAdapter
from apps.streaming.sources.template_source import TemplateSourceAdapter
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


class StreamingSourceAdapterFactoryTests(SimpleTestCase):
    def test_get_adapter_for_source_uses_registered_aliases(self) -> None:
        source = StreamingSource(
            name="Ani Waves",
            base_url="https://example.com",
            search_url_template="https://example.com/search?q={query}",
            episode_pattern="/watch/{slug}-episode-{episode}",
        )

        adapter = get_adapter_for_source(source)

        self.assertIsInstance(adapter, AniWavesSourceAdapter)

    def test_get_adapter_for_source_keeps_gogoanime_aliases(self) -> None:
        source = StreamingSource(
            name="AniTaku",
            base_url="https://example.com",
            search_url_template="https://example.com/search?q={query}",
            episode_pattern="/watch/{slug}-episode-{episode}",
        )

        adapter = get_adapter_for_source(source)

        self.assertIsInstance(adapter, GogoanimeSourceAdapter)

    def test_get_adapter_for_source_falls_back_to_template(self) -> None:
        source = StreamingSource(
            name="Unknown Source",
            base_url="https://example.com",
            search_url_template="https://example.com/search?q={query}",
            episode_pattern="/watch/{slug}-episode-{episode}",
        )

        adapter = get_adapter_for_source(source)

        self.assertIsInstance(adapter, TemplateSourceAdapter)


class AniWavesSourceAdapterTests(SimpleTestCase):
    def test_extract_candidates_uses_slug_when_anchor_title_missing(self) -> None:
        from apps.streaming.sources.aniwaves_source import AniWavesSourceAdapter

        html = '<a href="/watch/kaguya-sama-wa-kokurasetai-tensai-tachi-no-renai-zunousen-77991"><img src="/x.jpg"></a>'

        candidates = AniWavesSourceAdapter._extract_candidates(html)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(
            candidates[0].slug,
            "kaguya-sama-wa-kokurasetai-tensai-tachi-no-renai-zunousen-77991",
        )
        self.assertIn("kaguya sama", candidates[0].title)


class AniWatchSourceAdapterTests(SimpleTestCase):
    _FEATURED_CARD_HTML = (
        '<div class="featured-cards-grid">'
        '<div class="featured-card" data-qtip-id="3294" '
        'data-qtip-link="https://jp-animenities.com/title/naruto-shippuden/">'
        '<a href="https://jp-animenities.com/title/naruto-shippuden/" '
        'title="Naruto Shipp&#363;den" class="featured-card-link">'
        '<div class="featured-card-image">'
        '<span class="featured-card-badge badge-year">2007</span>'
        '<span class="featured-card-badge badge-episodes">Ep 500</span>'
        '<span class="featured-card-badge badge-quality">HD</span>'
        "</div>"
        '<div class="featured-card-body">'
        '<div class="featured-card-title anime-name" '
        'data-title-en="Naruto Shipp&#363;den" '
        'data-title-jp="Naruto Hurricane Chronicles"> Naruto Shipp&#363;den </div>'
        "</div></a>"
        '<div class="card-qtip" role="tooltip" aria-hidden="true"></div>'
        "</div>"
        '<div class="anime-card" data-qtip-id="546" '
        'data-qtip-link="https://jp-animenities.com/title/boruto-naruto-the-movie/">'
        '<a href="https://jp-animenities.com/title/boruto-naruto-the-movie/" '
        'title="Boruto: Naruto the Movie" class="anime-card-link">'
        '<div class="anime-card-image">'
        '<span class="anime-card-badge badge-year">2015</span>'
        '<span class="anime-card-badge badge-quality">HD</span>'
        "</div>"
        '<div class="anime-card-body">'
        '<h2 class="anime-card-title anime-name" '
        'data-title-en="Boruto: Naruto the Movie" '
        'data-title-jp="Gekijouban Naruto (2015)"> Boruto: Naruto the Movie </h2>'
        "</div></a></div>"
        "</div>"
    )

    def test_extract_candidates_returns_main_and_secondary_cards(self) -> None:
        candidates = AniWatchSourceAdapter._extract_candidates(self._FEATURED_CARD_HTML)

        self.assertEqual(len(candidates), 2)

        first = candidates[0]
        self.assertEqual(first.slug, "naruto-shippuden")
        self.assertEqual(first.title, "Naruto Shippūden")
        self.assertEqual(first.year, 2007)
        self.assertEqual(first.episodes, 500)

        second = candidates[1]
        self.assertEqual(second.slug, "boruto-naruto-the-movie")
        self.assertEqual(second.title, "Boruto: Naruto the Movie")
        self.assertEqual(second.year, 2015)
        self.assertIsNone(second.episodes)

    def test_extract_candidates_deduplicates_repeated_slugs(self) -> None:
        duplicate_html = self._FEATURED_CARD_HTML + self._FEATURED_CARD_HTML

        candidates = AniWatchSourceAdapter._extract_candidates(duplicate_html)

        slugs = [candidate.slug for candidate in candidates]
        self.assertEqual(slugs, ["naruto-shippuden", "boruto-naruto-the-movie"])

    def test_extract_candidates_returns_empty_for_unrelated_html(self) -> None:
        self.assertEqual(AniWatchSourceAdapter._extract_candidates("<p>hello</p>"), [])

    def test_normalize_slug_handles_full_url_with_episode(self) -> None:
        slug = AniWatchSourceAdapter._normalize_slug(
            "https://jp-animenities.com/title/naruto-shippuden/season/1/"
        )
        self.assertEqual(slug, "naruto-shippuden")

    def test_build_episode_url_uses_configured_pattern(self) -> None:
        source = StreamingSource(
            name="AniWatch",
            base_url="https://jp-animenities.com",
            search_url_template="https://jp-animenities.com/search/?q={query}",
            episode_pattern="title/{slug}",
        )

        adapter = AniWatchSourceAdapter(source)

        url = adapter.build_episode_url(
            "https://jp-animenities.com/title/naruto-shippuden/", 7
        )

        self.assertEqual(url, "https://jp-animenities.com/title/naruto-shippuden")

    def test_build_search_url_uses_template(self) -> None:
        source = StreamingSource(
            name="AniWatch",
            base_url="https://jp-animenities.com",
            search_url_template="https://jp-animenities.com/search/?q={query}",
            episode_pattern="title/{slug}",
        )

        adapter = AniWatchSourceAdapter(source)

        self.assertEqual(
            adapter.build_search_url("naruto shippuden"),
            "https://jp-animenities.com/search/?q=naruto%20shippuden",
        )

    def test_get_adapter_for_source_resolves_aniwatch(self) -> None:
        source = StreamingSource(
            name="AniWatch",
            base_url="https://jp-animenities.com",
            search_url_template="https://jp-animenities.com/search/?q={query}",
            episode_pattern="title/{slug}",
        )

        adapter = get_adapter_for_source(source)

        self.assertIsInstance(adapter, AniWatchSourceAdapter)
