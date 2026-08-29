import unittest

from articlefiler.titles import (
    build_filename,
    clean_title,
    sanitise_component,
    split_prefixed,
    strip_copy_suffix,
    truncate,
)


class CleanTitleTests(unittest.TestCase):
    def test_decodes_html_entities(self):
        self.assertEqual(clean_title("Fed&rsquo;s move &amp; markets"), "Fed’s move & markets")

    def test_replaces_path_separators(self):
        self.assertEqual(clean_title("Oil/gas split"), "Oil-gas split")

    def test_replaces_colons(self):
        self.assertEqual(clean_title("Opinion: the grid"), "Opinion- the grid")

    def test_removes_illegal_characters(self):
        self.assertEqual(clean_title('What now? "Really" <yes>'), "What now Really yes")

    def test_collapses_whitespace_and_newlines(self):
        self.assertEqual(clean_title("A   long\n\ttitle"), "A long title")

    def test_strips_control_characters(self):
        self.assertEqual(clean_title("Clean\x00er\x1ftitle"), "Cleanertitle")

    def test_keeps_curly_quotes_and_em_dashes(self):
        self.assertEqual(clean_title("The ‘big’ shift — explained"), "The ‘big’ shift — explained")

    def test_strips_leading_and_trailing_punctuation(self):
        self.assertEqual(clean_title("  - A headline -  "), "A headline")

    def test_empty_input(self):
        self.assertEqual(clean_title(""), "")

    def test_strip_leading_junk_when_asked(self):
        self.assertEqual(
            clean_title("Opinion | The grid", strip_leading_junk=True), "The grid"
        )

    def test_leading_junk_kept_by_default(self):
        self.assertEqual(clean_title("Opinion | The grid"), "Opinion The grid")


class TruncateTests(unittest.TestCase):
    def test_short_text_is_untouched(self):
        self.assertEqual(truncate("short", 50), "short")

    def test_cuts_on_a_word_boundary(self):
        self.assertEqual(truncate("one two three four", 11), "one two")

    def test_drops_trailing_punctuation(self):
        self.assertEqual(truncate("one two, three", 9), "one two")

    def test_hard_cut_when_no_useful_space(self):
        self.assertEqual(truncate("supercalifragilistic", 8), "supercal")

    def test_zero_limit_is_a_no_op(self):
        self.assertEqual(truncate("anything", 0), "anything")


class BuildFilenameTests(unittest.TestCase):
    def test_standard_shape(self):
        self.assertEqual(build_filename("NYT", "The Fed blinks"), "NYT - The Fed blinks.pdf")

    def test_missing_acronym_collapses_the_separator(self):
        self.assertEqual(build_filename(None, "The Fed blinks"), "The Fed blinks.pdf")

    def test_empty_acronym_collapses_the_separator(self):
        self.assertEqual(build_filename("", "The Fed blinks"), "The Fed blinks.pdf")

    def test_missing_title_falls_back(self):
        self.assertEqual(build_filename("FT", ""), "FT - Untitled article.pdf")

    def test_respects_the_extension(self):
        self.assertEqual(build_filename("TE", "Grid", extension=".png"), "TE - Grid.png")

    def test_extension_without_a_dot(self):
        self.assertEqual(build_filename("TE", "Grid", extension="png"), "TE - Grid.png")

    def test_custom_template_with_date(self):
        self.assertEqual(
            build_filename("WSJ", "Markets", template="{date} {acronym} - {title}",
                           date="2026-08-29"),
            "2026-08-29 WSJ - Markets.pdf",
        )

    def test_date_template_collapses_when_date_missing(self):
        self.assertEqual(
            build_filename("WSJ", "Markets", template="{date} {acronym} - {title}"),
            "WSJ - Markets.pdf",
        )

    def test_long_title_is_truncated(self):
        name = build_filename("FT", "word " * 100, max_title_length=40)
        self.assertLessEqual(len(name), 40 + len("FT - ") + len(".pdf"))
        self.assertTrue(name.startswith("FT - word"))

    def test_result_has_no_path_separator(self):
        self.assertNotIn("/", build_filename("NYT", "A/B testing at scale"))

    def test_slashes_in_the_acronym_are_removed(self):
        self.assertEqual(build_filename("N/A", "Title"), "N-A - Title.pdf")


class PrefixTests(unittest.TestCase):
    def test_splits_a_prefixed_name(self):
        self.assertEqual(split_prefixed("WSJ - Markets wobble"), ("WSJ", "Markets wobble"))

    def test_ignores_a_lowercase_prefix(self):
        self.assertIsNone(split_prefixed("wsj - markets"))

    def test_ignores_a_plain_headline_with_a_dash(self):
        self.assertIsNone(split_prefixed("Markets wobble - a note"))

    def test_ignores_an_over_long_prefix(self):
        self.assertIsNone(split_prefixed("VERYLONGACRONYM - Markets"))

    def test_strips_a_macos_copy_suffix(self):
        self.assertEqual(strip_copy_suffix("NYT - Markets (2)"), "NYT - Markets")

    def test_strips_the_word_copy(self):
        self.assertEqual(strip_copy_suffix("NYT - Markets copy"), "NYT - Markets")

    def test_keeps_a_trailing_number_that_belongs_to_the_headline(self):
        self.assertEqual(strip_copy_suffix("The Budget 2026"), "The Budget 2026")
        self.assertEqual(strip_copy_suffix("Formula 1"), "Formula 1")


class SanitiseTests(unittest.TestCase):
    def test_cleans_and_truncates_together(self):
        self.assertEqual(sanitise_component("Opinion: a very long headline", limit=14),
                         "Opinion- a")


if __name__ == "__main__":
    unittest.main()
