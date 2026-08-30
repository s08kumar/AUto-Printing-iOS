import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from articlefiler.config import Config
from articlefiler.filer import (
    apply_plan,
    is_icloud_stub,
    plan_file,
    process_inbox,
    unique_path,
)
from articlefiler.publications import PublicationRegistry


def pdf_with_title(title: str) -> bytes:
    return (
        b"%PDF-1.7\n1 0 obj\n<< /Title (" + title.encode() + b") >>\nendobj\n"
        b"trailer\n<< /Info 1 0 R >>\n%%EOF\n"
    )


class FilerTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        root = Path(self._tmp.name)
        self.library = root / "Articles"
        self.inbox = self.library / "_Inbox"
        self.inbox.mkdir(parents=True)
        self.config = Config(
            library=str(self.library),
            inbox=str(self.inbox),
            resolve_redirects=False,  # never touch the network in tests
        )
        self.registry = PublicationRegistry.bundled()

    def tearDown(self):
        self._tmp.cleanup()

    def drop(self, name: str, data: bytes = b"%PDF-1.7\ncontent\n") -> Path:
        path = self.inbox / name
        path.write_bytes(data)
        return path

    def file_one(self, path: Path):
        return apply_plan(plan_file(path, self.config, self.registry))


class RenamingTests(FilerTestCase):
    def test_files_a_pdf_named_after_its_headline(self):
        source = self.drop("Why the grid needs storage - The Economist.pdf")
        plan = self.file_one(source)
        self.assertEqual(plan.action, "move")
        self.assertFalse(source.exists())
        self.assertTrue((self.library / "Economist - Why the grid needs storage.pdf").is_file())

    def test_uses_the_pdf_title_over_a_meaningless_filename(self):
        source = self.drop("Untitled.pdf", pdf_with_title("Fed holds rates - WSJ"))
        self.file_one(source)
        self.assertTrue((self.library / "WSJ - Fed holds rates.pdf").is_file())

    def test_unknown_publication_is_filed_without_a_prefix(self):
        source = self.drop("A personal blog post.pdf")
        self.file_one(source)
        self.assertTrue((self.library / "A personal blog post.pdf").is_file())

    def test_a_sidecar_json_supplies_the_url_and_title(self):
        source = self.drop("scan0001.pdf")
        sidecar = self.inbox / "scan0001.json"
        sidecar.write_text(json.dumps({"url": "https://hbr.org/x", "title": "Leading in a crisis"}))
        self.file_one(source)
        self.assertTrue((self.library / "HBR - Leading in a crisis.pdf").is_file())
        self.assertFalse(sidecar.exists(), "the sidecar should be cleaned up")

    def test_non_pdf_attachments_are_filed_with_their_extension(self):
        source = self.drop("Grid storage - WSJ.png", b"\x89PNG\r\n")
        self.file_one(source)
        self.assertTrue((self.library / "WSJ - Grid storage.png").is_file())

    def test_filing_is_idempotent(self):
        source = self.drop("Markets wobble - WSJ.pdf")
        first = self.file_one(source).destination
        second = apply_plan(plan_file(first, self.config, self.registry))
        self.assertEqual(second.action, "skip")
        self.assertTrue(first.is_file())


class CollisionTests(FilerTestCase):
    def test_identical_content_is_dropped_rather_than_duplicated(self):
        data = pdf_with_title("Fed holds rates - WSJ")
        self.file_one(self.drop("a.pdf", data))
        second = self.drop("b.pdf", data)
        plan = self.file_one(second)
        self.assertEqual(plan.action, "duplicate")
        self.assertFalse(second.exists())
        self.assertEqual(len(list(self.library.glob("*.pdf"))), 1)

    def test_different_content_gets_a_numbered_name(self):
        self.file_one(self.drop("a.pdf", pdf_with_title("Fed holds rates - WSJ")))
        self.file_one(self.drop("b.pdf", pdf_with_title("Fed holds rates - WSJ") + b"different"))
        names = sorted(p.name for p in self.library.glob("*.pdf"))
        self.assertEqual(names, ["WSJ - Fed holds rates (2).pdf", "WSJ - Fed holds rates.pdf"])

    def test_unique_path_finds_the_next_free_slot(self):
        target = self.library / "x.pdf"
        self.library.mkdir(exist_ok=True)
        target.write_bytes(b"1")
        (self.library / "x (2).pdf").write_bytes(b"2")
        self.assertEqual(unique_path(target).name, "x (3).pdf")


class SkipTests(FilerTestCase):
    def test_hidden_files_are_skipped(self):
        plan = plan_file(self.drop(".DS_Store"), self.config, self.registry)
        self.assertEqual(plan.action, "skip")

    def test_unsupported_extensions_are_skipped(self):
        plan = plan_file(self.drop("notes.docx"), self.config, self.registry)
        self.assertEqual(plan.action, "skip")
        self.assertIn(".docx", plan.reason)

    def test_undownloaded_icloud_placeholders_are_skipped(self):
        placeholder = self.drop(".WSJ - Markets.pdf.icloud")
        self.assertTrue(is_icloud_stub(placeholder))
        plan = plan_file(placeholder, self.config, self.registry)
        self.assertEqual(plan.action, "skip")
        self.assertIn("iCloud", plan.reason)

    def test_dry_run_leaves_the_disk_alone(self):
        source = self.drop("Markets wobble - WSJ.pdf")
        plan = apply_plan(plan_file(source, self.config, self.registry), dry_run=True)
        self.assertEqual(plan.action, "move")
        self.assertTrue(source.exists())
        self.assertFalse((self.library / "WSJ - Markets wobble.pdf").exists())


class SubfolderTests(FilerTestCase):
    def test_publication_subfolders(self):
        self.config.subfolder = "publication"
        self.file_one(self.drop("Markets wobble - WSJ.pdf"))
        self.assertTrue((self.library / "WSJ" / "WSJ - Markets wobble.pdf").is_file())

    def test_unknown_publication_goes_to_unsorted(self):
        self.config.subfolder = "publication"
        self.file_one(self.drop("A blog post.pdf"))
        self.assertTrue((self.library / "Unsorted" / "A blog post.pdf").is_file())

    def test_month_subfolders(self):
        from datetime import datetime

        self.config.subfolder = "month"
        source = self.drop("Markets wobble - WSJ.pdf")
        plan = apply_plan(plan_file(source, self.config, self.registry))
        self.assertEqual(plan.destination.parent.name, datetime.now().strftime("%Y-%m"))


class ProcessInboxTests(FilerTestCase):
    def test_files_everything_waiting(self):
        self.drop("Markets wobble - WSJ.pdf")
        self.drop("Grid storage - The Economist.pdf")
        self.drop(".DS_Store")
        plans = process_inbox(self.config, self.registry, settle=False)
        moved = [p for p in plans if p.action == "move"]
        self.assertEqual(len(moved), 2)
        self.assertEqual(len(list(self.inbox.iterdir())), 1)  # only .DS_Store remains

    def test_an_empty_inbox_is_fine(self):
        self.assertEqual(process_inbox(self.config, self.registry, settle=False), [])

    def test_a_missing_inbox_is_fine(self):
        self.config.inbox = str(self.library / "nope")
        self.assertEqual(process_inbox(self.config, self.registry, settle=False), [])


class ConfigTests(unittest.TestCase):
    def test_inbox_defaults_to_a_subfolder_of_the_library(self):
        config = Config(library="/tmp/Articles")
        self.assertEqual(config.inbox_path, Path("/tmp/Articles/_Inbox"))

    def test_icloud_relative_path_for_the_shortcut(self):
        config = Config()  # the default library lives in iCloud Drive
        self.assertTrue(config.icloud_relative_library.startswith("/"))
        self.assertIn("Articles", config.icloud_relative_library)

    def test_a_library_outside_icloud_still_yields_a_path(self):
        config = Config(library="/tmp/Elsewhere")
        self.assertEqual(config.icloud_relative_library, "/Elsewhere")

    def test_round_trips_through_json(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            Config(library="/tmp/A", subfolder="month").save(path)
            self.assertEqual(Config.load(path).subfolder, "month")

    def test_rejects_an_unknown_subfolder_mode(self):
        with self.assertRaises(ValueError):
            Config(subfolder="weekly").validate()

    def test_rejects_a_template_without_a_title(self):
        with self.assertRaises(ValueError):
            Config(template="{acronym}").validate()


if __name__ == "__main__":
    unittest.main()


class PermissionTests(FilerTestCase):
    """macOS hides iCloud Drive behind Full Disk Access; the failure must be
    legible rather than a traceback, because it is the usual reason nothing
    gets filed."""

    def test_an_unreadable_inbox_raises_a_typed_error(self):
        from unittest.mock import patch

        from articlefiler.filer import AccessDenied, iter_inbox

        with patch.object(Path, "iterdir", side_effect=PermissionError(1, "Operation not permitted")):
            with self.assertRaises(AccessDenied) as caught:
                iter_inbox(self.config)
        self.assertIn("permission denied", str(caught.exception))
        self.assertIn("_Inbox", str(caught.exception))

    def test_the_watcher_reports_the_problem_only_once(self):
        from unittest.mock import patch

        from articlefiler.watch import Watcher

        watcher = Watcher(self.config, self.registry)
        with patch("articlefiler.watch.process_inbox", side_effect=PermissionError("nope")):
            with patch("articlefiler.watch.log") as log:
                watcher.tick()
                first = log.error.call_count
                watcher.tick()
                self.assertEqual(log.error.call_count, first, "should not repeat every poll")
        self.assertGreater(first, 0)

    def test_check_readable_passes_for_a_normal_folder(self):
        from articlefiler.access import check_readable

        self.assertIsNone(check_readable(self.inbox))

    def test_the_remedy_is_offered_only_for_protected_folders(self):
        from articlefiler.access import access_error_message, is_protected

        icloud = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Articles"
        self.assertTrue(is_protected(icloud))
        self.assertFalse(is_protected(Path("/tmp/Articles")))
        message = access_error_message(Path("/tmp/x"), "permission denied listing: /tmp/x")
        self.assertNotIn("Full Disk Access", message)


class LoggingTests(unittest.TestCase):
    def test_no_console_handler_when_output_is_redirected(self):
        """launchd points stdout at the same file the FileHandler writes, so a
        stream handler would double every line."""
        import logging
        from unittest.mock import patch

        from articlefiler.watch import setup_logging

        with TemporaryDirectory() as tmp:
            config = Config(library=str(Path(tmp) / "L"), log_path=str(Path(tmp) / "x.log"))
            with patch("sys.stderr") as stderr:
                stderr.isatty.return_value = False
                setup_logging(config)
                streams = [h for h in logging.getLogger().handlers
                           if type(h) is logging.StreamHandler]
                self.assertEqual(streams, [])

            with patch("sys.stderr") as stderr:
                stderr.isatty.return_value = True
                setup_logging(config)
                streams = [h for h in logging.getLogger().handlers
                           if type(h) is logging.StreamHandler]
                self.assertEqual(len(streams), 1, "interactive runs should still echo")
        logging.getLogger().handlers.clear()


class ShortcutsFolderTests(FilerTestCase):
    """The Save File action takes a subpath resolved against a base we cannot
    set, so files land in the Shortcuts folder. Watching there too avoids
    binding every device by hand through the folder picker."""

    def test_the_shortcuts_folder_is_watched(self):
        names = [p.name for p in self.config.inbox_paths]
        self.assertIn("_Inbox", names)
        self.assertTrue(any("Shortcuts" in str(p) for p in self.config.inbox_paths))

    def test_files_are_drained_from_an_extra_inbox(self):
        extra = Path(self._tmp.name) / "Shortcuts" / "Articles"
        extra.mkdir(parents=True)
        (extra / "Grid storage - The Economist.pdf").write_bytes(b"%PDF-1.7\n")
        self.config.extra_inboxes = (str(extra),)

        plans = process_inbox(self.config, self.registry, settle=False)
        self.assertEqual([p.action for p in plans], ["move"])
        self.assertTrue((self.library / "Economist - Grid storage.pdf").is_file())
        self.assertEqual(list(extra.iterdir()), [])

    def test_inbox_paths_are_deduplicated(self):
        self.config.extra_inboxes = (str(self.inbox),)
        self.assertEqual(len(self.config.inbox_paths), len(set(self.config.inbox_paths)))

    def test_one_unreadable_inbox_does_not_block_the_others(self):
        self.config.extra_inboxes = ("/root/definitely-not-readable-xyz",)
        (self.inbox / "Markets wobble - WSJ.pdf").write_bytes(b"%PDF-1.7\n")
        plans = process_inbox(self.config, self.registry, settle=False)
        self.assertEqual([p.action for p in plans], ["move"])


class VerifyTests(unittest.TestCase):
    """Telling an article from the paywall that stood in front of it."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name: str, pages: int, text: list, pad: int = 0) -> Path:
        import zlib

        body = b"%PDF-1.7\n" + b"<< /Type /Page >>\n" * pages
        stream = b" ".join(b"(" + t.encode() + b") Tj" for t in text)
        body += b"stream\n" + zlib.compress(stream) + b"\nendstream\n"
        body += b"%" + b"x" * pad + b"\n%%EOF\n"
        path = self.tmp / name
        path.write_bytes(body)
        return path

    def test_a_real_article_passes(self):
        from articlefiler.verify import inspect

        path = self.write("good.pdf", 5, ["A headline"] + ["word " * 60] * 6, pad=60000)
        report = inspect(path)
        self.assertFalse(report.suspicious, report.reasons)
        self.assertEqual(report.pages, 5)

    def test_paywall_wording_is_flagged(self):
        from articlefiler.verify import inspect

        path = self.write("wall.pdf", 1, ["Subscribe to continue reading"], pad=60000)
        report = inspect(path)
        self.assertTrue(report.suspicious)
        self.assertTrue(any("paywall wording" in r for r in report.reasons))

    def test_a_thin_single_page_is_flagged(self):
        from articlefiler.verify import inspect

        report = inspect(self.write("thin.pdf", 1, ["Hi"], pad=60000))
        self.assertTrue(any("almost no text" in r for r in report.reasons))

    def test_the_page_tree_node_is_not_counted_as_a_page(self):
        from articlefiler.verify import count_pages

        self.assertEqual(count_pages(b"/Type /Pages /Type /Page "), 1)

    def test_a_non_pdf_is_reported_not_raised(self):
        from articlefiler.verify import inspect

        path = self.tmp / "x.pdf"
        path.write_bytes(b"not a pdf")
        report = inspect(path)
        self.assertFalse(report.readable)
        self.assertEqual(report.verdict, "unreadable")

    def test_a_missing_file_is_reported_not_raised(self):
        from articlefiler.verify import inspect

        self.assertFalse(inspect(self.tmp / "nope.pdf").readable)
