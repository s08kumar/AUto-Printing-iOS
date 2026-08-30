import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from articlefiler.publications import (
    Publication,
    PublicationRegistry,
    normalise_host,
)


class NormaliseHostTests(unittest.TestCase):
    def test_strips_scheme_path_and_query(self):
        self.assertEqual(
            normalise_host("https://www.nytimes.com/2026/01/02/x.html?s=1#top"),
            "nytimes.com",
        )

    def test_strips_port_userinfo_and_case(self):
        self.assertEqual(normalise_host("HTTP://user@M.Economist.com:8443/a"), "economist.com")

    def test_keeps_meaningful_subdomains(self):
        self.assertEqual(
            normalise_host("https://economictimes.indiatimes.com/x"),
            "economictimes.indiatimes.com",
        )

    def test_bare_host_passes_through(self):
        self.assertEqual(normalise_host("ft.com"), "ft.com")

    def test_empty_input(self):
        self.assertEqual(normalise_host(""), "")

    def test_short_host_is_not_eaten_by_noise_stripping(self):
        # "in.com" must not lose its "in." prefix and become "com".
        self.assertEqual(normalise_host("https://in.com"), "in.com")


class RegistryLookupTests(unittest.TestCase):
    def setUp(self):
        self.registry = PublicationRegistry.bundled()

    def test_matches_known_domain(self):
        self.assertEqual(self.registry.match_url("https://www.wsj.com/a/b").acronym, "WSJ")

    def test_matches_subdomain(self):
        self.assertEqual(self.registry.match_url("https://blogs.ft.com/x").acronym, "FT")

    def test_matches_short_link_domain(self):
        self.assertEqual(self.registry.match_url("https://nyti.ms/3abc").acronym, "NYT")

    def test_longest_domain_wins(self):
        registry = PublicationRegistry(
            [
                Publication("GEN", "Generic", ("example.com",)),
                Publication("SPEC", "Specific", ("news.example.com",)),
            ]
        )
        self.assertEqual(registry.match_url("https://news.example.com/a").acronym, "SPEC")

    def test_aggregators_never_match(self):
        self.assertIsNone(self.registry.match_url("https://apple.news/AbCdEf"))

    def test_unknown_domain(self):
        self.assertIsNone(self.registry.match_url("https://some-blog.example/post"))

    def test_partial_domain_is_not_a_match(self):
        # "notft.com" must not match "ft.com".
        self.assertIsNone(self.registry.match_url("https://notft.com/a"))


class TitleSuffixTests(unittest.TestCase):
    def setUp(self):
        self.registry = PublicationRegistry.bundled()

    def test_strips_dash_suffix(self):
        pub, title = self.registry.match_title("Fed holds rates - WSJ")
        self.assertEqual(pub.acronym, "WSJ")
        self.assertEqual(title, "Fed holds rates")

    def test_strips_pipe_suffix(self):
        pub, title = self.registry.match_title("The heat pump decade | Financial Times")
        self.assertEqual(pub.acronym, "FT")
        self.assertEqual(title, "The heat pump decade")

    def test_strips_em_dash_suffix(self):
        pub, title = self.registry.match_title("Grid storage — The Economist")
        self.assertEqual(pub.acronym, "Economist")
        self.assertEqual(title, "Grid storage")

    def test_longest_suffix_wins(self):
        pub, title = self.registry.match_title("Steel prices - The Hindu BusinessLine")
        self.assertEqual(pub.acronym, "Hindu")
        self.assertEqual(title, "Steel prices")

    def test_no_suffix_returns_none(self):
        self.assertIsNone(self.registry.match_title("Just a headline"))

    def test_suffix_alone_is_not_stripped_to_nothing(self):
        self.assertIsNone(self.registry.match_title("WSJ"))


class RegistryLoadingTests(unittest.TestCase):
    def test_override_file_replaces_by_acronym(self):
        with TemporaryDirectory() as tmp:
            override = Path(tmp) / "publications.json"
            override.write_text(
                json.dumps(
                    {
                        "publications": [
                            {"acronym": "NYT", "name": "NYT", "domains": ["example.test"]},
                            {"acronym": "ZZZ", "name": "Test Weekly", "domains": ["zzz.test"]},
                        ]
                    }
                )
            )
            registry = PublicationRegistry.load([override])
            self.assertEqual(registry.match_url("https://example.test/a").acronym, "NYT")
            self.assertIsNone(registry.match_url("https://nytimes.com/a"))
            self.assertEqual(registry.match_url("https://zzz.test/a").acronym, "ZZZ")

    def test_missing_override_file_is_ignored(self):
        registry = PublicationRegistry.load([Path("/nonexistent/publications.json")])
        self.assertGreater(len(registry), 0)

    def test_domain_map_is_flat(self):
        mapping = PublicationRegistry.bundled().domain_map()
        self.assertEqual(mapping["wsj.com"], "WSJ")
        self.assertEqual(mapping["hbr.org"], "HBR")

    def test_every_acronym_is_unique(self):
        acronyms = PublicationRegistry.bundled().acronyms()
        self.assertEqual(len(acronyms), len(set(acronyms)))


if __name__ == "__main__":
    unittest.main()


class PrefixShapeTests(unittest.TestCase):
    """The already-filed check matches a prefix containing no whitespace, so a
    two-word prefix would silently stop working."""

    def test_no_bundled_prefix_contains_whitespace(self):
        for pub in PublicationRegistry.bundled():
            self.assertNotIn(" ", pub.acronym, f"{pub.name} has a multi-word prefix")

    def test_a_multi_word_prefix_is_rejected(self):
        with self.assertRaises(ValueError):
            Publication.from_dict({"acronym": "Washington Post", "name": "x"})

    def test_an_empty_prefix_is_rejected(self):
        with self.assertRaises(ValueError):
            Publication.from_dict({"acronym": "  ", "name": "x"})

    def test_word_prefixes_round_trip_through_filing(self):
        from articlefiler.titles import split_prefixed

        registry = PublicationRegistry.bundled()
        known = registry.acronyms()
        for stem, expected in (
            ("Economist - Grid storage", "Economist"),
            ("McKinsey - Reimagining efficiency", "McKinsey"),
            ("BusinessStandard - Steel prices", "BusinessStandard"),
            ("NYT - The Fed blinks", "NYT"),
        ):
            self.assertEqual(split_prefixed(stem, known)[0], expected)
