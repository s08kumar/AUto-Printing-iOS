import unittest

from articlefiler.classify import Signals, classify
from articlefiler.publications import PublicationRegistry


class ClassifyTests(unittest.TestCase):
    def setUp(self):
        self.registry = PublicationRegistry.bundled()

    def name(self, **kwargs) -> str:
        return classify(Signals(**kwargs), self.registry).filename

    def decide(self, **kwargs):
        return classify(Signals(**kwargs), self.registry)

    # -- the URL is the strongest signal --------------------------------

    def test_url_identifies_the_publication(self):
        self.assertEqual(
            self.name(url="https://www.wsj.com/x", title="Markets wobble as Fed holds - WSJ"),
            "WSJ - Markets wobble as Fed holds.pdf",
        )

    def test_url_wins_over_a_misleading_title_suffix(self):
        decision = self.decide(
            url="https://www.nytimes.com/x", title="A story about the Financial Times"
        )
        self.assertEqual(decision.acronym, "NYT")
        self.assertEqual(decision.source, "url")

    def test_metadata_url_is_used_when_no_explicit_url(self):
        decision = self.decide(
            metadata_urls=("https://hbr.org/2026/01/x",), filename_stem="Untitled"
        )
        self.assertEqual(decision.acronym, "HBR")

    def test_first_matching_metadata_url_wins_over_noise(self):
        decision = self.decide(
            metadata_urls=("https://fonts.example.com/a", "https://www.ft.com/content/x"),
            title="The heat pump decade",
        )
        self.assertEqual(decision.acronym, "FT")

    # -- falling back to the title --------------------------------------

    def test_title_suffix_identifies_the_publication(self):
        decision = self.decide(filename_stem="Why the grid needs storage - The Economist")
        self.assertEqual(decision.acronym, "Economist")
        self.assertEqual(decision.source, "title-suffix")
        self.assertEqual(decision.filename, "Economist - Why the grid needs storage.pdf")

    def test_a_word_prefix_survives_a_second_pass(self):
        """Satish files as "Economist - ...", so mixed-case prefixes must be
        recognised as already-filed rather than re-processed."""
        decision = self.decide(filename_stem="Economist - Grid storage")
        self.assertEqual(decision.acronym, "Economist")
        self.assertEqual(decision.source, "existing-prefix")
        self.assertEqual(decision.filename, "Economist - Grid storage.pdf")

    def test_apple_news_link_falls_through_to_the_title(self):
        decision = self.decide(
            url="https://apple.news/AbCdEf", title="The heat pump decade | Financial Times"
        )
        self.assertEqual(decision.acronym, "FT")
        self.assertEqual(decision.source, "title-suffix")

    def test_publisher_name_is_stripped_even_when_the_url_identified_it(self):
        decision = self.decide(
            url="https://www.mckinsey.com/x", title="Reimagining efficiency | McKinsey"
        )
        self.assertEqual(decision.filename, "McKinsey - Reimagining efficiency.pdf")

    # -- unknown publications -------------------------------------------

    def test_unknown_publication_files_without_a_prefix(self):
        decision = self.decide(title="Some independent blog post")
        self.assertEqual(decision.filename, "Some independent blog post.pdf")
        self.assertFalse(decision.identified)

    def test_fallback_acronym_is_used_when_configured(self):
        decision = classify(
            Signals(title="Some blog post"), self.registry, fallback_acronym="MISC"
        )
        self.assertEqual(decision.filename, "MISC - Some blog post.pdf")
        self.assertEqual(decision.source, "fallback")

    def test_no_signals_at_all_still_produces_a_name(self):
        decision = self.decide()
        self.assertEqual(decision.filename, "Untitled article.pdf")

    # -- junk titles -----------------------------------------------------

    def test_producer_junk_titles_are_ignored(self):
        decision = self.decide(
            metadata_title="Microsoft Word - draft.docx",
            filename_stem="FT - The heat pump decade",
        )
        self.assertEqual(decision.filename, "FT - The heat pump decade.pdf")

    def test_untitled_metadata_is_ignored_in_favour_of_the_filename(self):
        decision = self.decide(metadata_title="Untitled", filename_stem="Grid storage - WSJ")
        self.assertEqual(decision.acronym, "WSJ")

    # -- idempotency -----------------------------------------------------

    def test_an_already_filed_name_survives_a_second_pass(self):
        first = self.name(url="https://www.wsj.com/x", title="Markets wobble - WSJ")
        second = self.name(filename_stem=first[:-4])
        self.assertEqual(first, second)

    def test_existing_prefix_identifies_the_publication(self):
        decision = self.decide(filename_stem="NYT - Old article")
        self.assertEqual(decision.acronym, "NYT")
        self.assertEqual(decision.source, "existing-prefix")

    def test_an_unknown_existing_prefix_is_not_invented_into_a_publication(self):
        decision = self.decide(filename_stem="XYZ - Something")
        self.assertFalse(decision.identified)

    def test_a_collision_suffix_does_not_change_the_decision(self):
        decision = self.decide(filename_stem="NYT - Old article (2)")
        self.assertEqual(decision.filename, "NYT - Old article.pdf")

    # -- extensions and templates ----------------------------------------

    def test_extension_is_carried_through(self):
        decision = classify(
            Signals(title="Grid storage - WSJ"), self.registry, extension=".png"
        )
        self.assertEqual(decision.filename, "WSJ - Grid storage.png")

    def test_custom_template(self):
        decision = classify(
            Signals(title="Grid storage - WSJ"),
            self.registry,
            template="{date} {acronym} - {title}",
            date="2026-08-29",
        )
        self.assertEqual(decision.filename, "2026-08-29 WSJ - Grid storage.pdf")


if __name__ == "__main__":
    unittest.main()


class UuidFilenameTests(unittest.TestCase):
    """Shortcuts' Make PDF emits an unnamed file, so Save File falls back to a
    UUID. That is an identifier, not a headline, and must not be filed as one."""

    def setUp(self):
        self.registry = PublicationRegistry.bundled()
        self.uuid = "60357F89-77FB-4575-8C97-A16D70C8DD7F"

    def test_a_url_inside_the_pdf_beats_the_uuid(self):
        decision = classify(
            Signals(filename_stem=self.uuid,
                    metadata_urls=("https://www.nytimes.com/2026/08/30/world/x.html",),
                    metadata_title="What to Know About Deadly Flash Floods"),
            self.registry,
        )
        self.assertEqual(decision.filename,
                         "NYT - What to Know About Deadly Flash Floods.pdf")

    def test_a_metadata_title_beats_the_uuid(self):
        decision = classify(
            Signals(filename_stem=self.uuid,
                    metadata_title="Grid storage explained - The Economist"),
            self.registry,
        )
        self.assertEqual(decision.filename, "Economist - Grid storage explained.pdf")

    def test_with_nothing_else_the_uuid_is_kept(self):
        # Better a stable identifier than every such file colliding on
        # "Untitled article".
        decision = classify(Signals(filename_stem=self.uuid), self.registry)
        self.assertEqual(decision.filename, f"{self.uuid}.pdf")

    def test_lowercase_uuids_are_recognised_too(self):
        decision = classify(
            Signals(filename_stem=self.uuid.lower(),
                    metadata_title="Markets wobble - WSJ"),
            self.registry,
        )
        self.assertEqual(decision.filename, "WSJ - Markets wobble.pdf")

    def test_a_headline_that_merely_contains_hex_is_not_junk(self):
        decision = classify(
            Signals(filename_stem="Why 60357F89 matters - WSJ"), self.registry
        )
        self.assertEqual(decision.filename, "WSJ - Why 60357F89 matters.pdf")


class UrlSlugTitleTests(unittest.TestCase):
    """Make PDF gives the file no title at all, so the article URL embedded in
    it is often the only thing naming the piece."""

    def setUp(self):
        self.registry = PublicationRegistry.bundled()

    def test_a_slug_becomes_a_headline(self):
        from articlefiler.classify import title_from_url

        self.assertEqual(
            title_from_url("https://www.nytimes.com/2026/08/30/world/asia/nepal-floods.html"),
            "Nepal Floods",
        )

    def test_it_skips_identifier_segments(self):
        from articlefiler.classify import title_from_url

        self.assertEqual(
            title_from_url("https://www.wsj.com/articles/fed-holds-rates-steady/index.html"),
            "Fed Holds Rates Steady",
        )

    def test_a_bare_domain_yields_nothing(self):
        from articlefiler.classify import title_from_url

        self.assertEqual(title_from_url("https://www.wsj.com/"), "")

    def test_a_single_word_slug_is_not_treated_as_a_headline(self):
        from articlefiler.classify import title_from_url

        self.assertEqual(title_from_url("https://www.ft.com/markets"), "")

    def test_query_and_fragment_are_ignored(self):
        from articlefiler.classify import title_from_url

        self.assertEqual(
            title_from_url("https://hbr.org/2026/01/leading-in-a-crisis?utm=x#top"),
            "Leading In A Crisis",
        )

    def test_a_uuid_named_pdf_is_named_from_its_embedded_url(self):
        decision = classify(
            Signals(filename_stem="72236488-6421-44E8-957D-1B50BC213DBD",
                    metadata_urls=("https://www.nytimes.com/2026/08/30/world/asia/nepal-floods.html",)),
            self.registry,
        )
        self.assertEqual(decision.filename, "NYT - Nepal Floods.pdf")
        self.assertTrue(any("recovered from the article URL" in n for n in decision.notes))

    def test_a_real_title_still_wins_over_the_slug(self):
        decision = classify(
            Signals(filename_stem="72236488-6421-44E8-957D-1B50BC213DBD",
                    metadata_title="What to Know About Deadly Flash Floods",
                    metadata_urls=("https://www.nytimes.com/2026/08/30/world/asia/nepal-floods.html",)),
            self.registry,
        )
        self.assertEqual(decision.filename,
                         "NYT - What to Know About Deadly Flash Floods.pdf")
