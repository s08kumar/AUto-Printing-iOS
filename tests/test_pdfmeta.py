import unittest
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory

from articlefiler.pdfmeta import _decode_pdf_string, read_pdf_metadata


def minimal_pdf(body: bytes) -> bytes:
    return b"%PDF-1.7\n" + body + b"\ntrailer\n<< /Info 1 0 R >>\n%%EOF\n"


def flate_stream(payload: bytes) -> bytes:
    return b"5 0 obj\n<< /Length 1 >>\nstream\n" + zlib.compress(payload) + b"\nendstream\nendobj\n"


class DecodeStringTests(unittest.TestCase):
    def test_literal_string(self):
        self.assertEqual(_decode_pdf_string(b"(Hello world)"), "Hello world")

    def test_escaped_parentheses(self):
        self.assertEqual(_decode_pdf_string(rb"(Hello \(world\))"), "Hello (world)")

    def test_escape_sequences(self):
        self.assertEqual(_decode_pdf_string(rb"(a\tb)"), "a\tb")

    def test_octal_escape(self):
        self.assertEqual(_decode_pdf_string(rb"(caf\351)"), "café")

    def test_utf16_hex_string(self):
        self.assertEqual(_decode_pdf_string(b"<FEFF00480065006C006C006F>"), "Hello")

    def test_plain_hex_string(self):
        self.assertEqual(_decode_pdf_string(b"<48656C6C6F>"), "Hello")

    def test_odd_length_hex_is_padded(self):
        self.assertEqual(_decode_pdf_string(b"<4>"), "@")

    def test_empty_input(self):
        self.assertEqual(_decode_pdf_string(b""), "")


class ReadMetadataTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name: str, data: bytes) -> Path:
        path = self.tmp / name
        path.write_bytes(data)
        return path

    def test_reads_a_literal_title(self):
        path = self.write("a.pdf", minimal_pdf(b"1 0 obj\n<< /Title (Fed holds rates - WSJ) >>\nendobj"))
        self.assertEqual(read_pdf_metadata(path).title, "Fed holds rates - WSJ")

    def test_reads_a_utf16_title(self):
        title = "Fed’s move".encode("utf-16-be").hex().upper()
        path = self.write("b.pdf", minimal_pdf(b"1 0 obj\n<< /Title <FEFF" + title.encode() + b"> >>\nendobj"))
        self.assertEqual(read_pdf_metadata(path).title, "Fed’s move")

    def test_reads_a_title_containing_nested_parentheses(self):
        path = self.write("c.pdf", minimal_pdf(b"1 0 obj\n<< /Title (A (nested) headline) >>\nendobj"))
        self.assertEqual(read_pdf_metadata(path).title, "A (nested) headline")

    def test_finds_link_annotation_urls(self):
        body = b"1 0 obj\n<< /Title (X) >>\nendobj\n2 0 obj\n<< /URI (https://www.ft.com/content/abc) >>\nendobj"
        meta = read_pdf_metadata(self.write("d.pdf", minimal_pdf(body)))
        self.assertIn("https://www.ft.com/content/abc", meta.urls)

    def test_most_frequent_url_comes_first(self):
        body = (
            b"1 0 obj << /Title (X) >> endobj\n"
            b"<< /URI (https://ads.example.com/1) >>\n"
            b"<< /URI (https://www.wsj.com/a) >>\n"
            b"<< /URI (https://www.wsj.com/a) >>\n"
        )
        meta = read_pdf_metadata(self.write("e.pdf", minimal_pdf(body)))
        self.assertEqual(meta.best_url, "https://www.wsj.com/a")

    def test_reads_a_title_from_a_compressed_xmp_packet(self):
        xmp = (
            b"<x:xmpmeta><rdf:RDF><rdf:Description><dc:title>"
            b"<rdf:Alt><rdf:li xml:lang='x-default'>Grid storage explained</rdf:li></rdf:Alt>"
            b"</dc:title></rdf:Description></rdf:RDF></x:xmpmeta>"
        )
        meta = read_pdf_metadata(self.write("f.pdf", minimal_pdf(flate_stream(xmp))))
        self.assertEqual(meta.title, "Grid storage explained")

    def test_subject_holding_a_url_is_promoted(self):
        body = b"1 0 obj\n<< /Title (X) /Subject (https://hbr.org/2026/01/y) >>\nendobj"
        meta = read_pdf_metadata(self.write("g.pdf", minimal_pdf(body)))
        self.assertEqual(meta.best_url, "https://hbr.org/2026/01/y")

    def test_a_file_that_is_not_a_pdf_yields_nothing(self):
        self.assertFalse(read_pdf_metadata(self.write("h.pdf", b"just text")))

    def test_a_missing_file_yields_nothing_rather_than_raising(self):
        self.assertFalse(read_pdf_metadata(self.tmp / "nope.pdf"))

    def test_a_pdf_with_no_metadata_yields_nothing(self):
        self.assertFalse(read_pdf_metadata(self.write("i.pdf", minimal_pdf(b"1 0 obj\n<< >>\nendobj"))))

    def test_corrupt_compressed_stream_does_not_raise(self):
        body = b"5 0 obj\nstream\n\x78\x9c\xff\xff\xff\nendstream\nendobj\n1 0 obj << /Title (Ok) >> endobj"
        self.assertEqual(read_pdf_metadata(self.write("j.pdf", minimal_pdf(body))).title, "Ok")


if __name__ == "__main__":
    unittest.main()
