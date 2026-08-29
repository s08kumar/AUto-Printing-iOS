"""Best-effort metadata extraction from a PDF, using nothing but the standard library.

We are not writing a PDF parser. We want two things — the document title and the
URL it was printed from — and PDFs put those in a small number of predictable
places. Anything we cannot read, we simply do not report.
"""

from __future__ import annotations

import re
import subprocess
import zlib
from dataclasses import dataclass
from pathlib import Path

MAX_SCAN_BYTES = 8 * 1024 * 1024  # metadata lives near the ends; 8 MB is plenty
MAX_STREAMS = 400

_INFO_KEY_RE = {
    "title": rb"/Title\s*",
    "subject": rb"/Subject\s*",
    "keywords": rb"/Keywords\s*",
}
_XMP_TITLE_RE = re.compile(
    rb"<dc:title>.*?<rdf:li[^>]*>(.*?)</rdf:li>.*?</dc:title>", re.DOTALL | re.IGNORECASE
)
_URI_RE = re.compile(rb"/URI\s*\(([^)]{4,2048}?)\)")
_STREAM_RE = re.compile(rb"stream\r?\n", re.DOTALL)
_URL_IN_TEXT_RE = re.compile(rb"https?://[^\s()<>\"'\\]{6,600}")


@dataclass
class PdfMetadata:
    """What we managed to learn about a PDF."""

    title: str = ""
    subject: str = ""
    keywords: str = ""
    urls: tuple[str, ...] = ()

    @property
    def best_url(self) -> str:
        return self.urls[0] if self.urls else ""

    def __bool__(self) -> bool:
        return bool(self.title or self.subject or self.urls)


# -- PDF string decoding ------------------------------------------------

_ESCAPES = {
    b"n": b"\n",
    b"r": b"\r",
    b"t": b"\t",
    b"b": b"\b",
    b"f": b"\f",
    b"(": b"(",
    b")": b")",
    b"\\": b"\\",
}


def _decode_pdf_string(raw: bytes) -> str:
    """Decode a PDF literal `(...)` or hex `<...>` string into text."""
    if not raw:
        return ""
    if raw.startswith(b"<") and raw.endswith(b">"):
        hex_digits = re.sub(rb"[^0-9A-Fa-f]", b"", raw[1:-1])
        if len(hex_digits) % 2:
            hex_digits += b"0"
        try:
            data = bytes.fromhex(hex_digits.decode("ascii"))
        except ValueError:
            return ""
    elif raw.startswith(b"(") and raw.endswith(b")"):
        body = raw[1:-1]
        out = bytearray()
        i = 0
        while i < len(body):
            char = body[i : i + 1]
            if char == b"\\" and i + 1 < len(body):
                nxt = body[i + 1 : i + 2]
                if nxt in _ESCAPES:
                    out += _ESCAPES[nxt]
                    i += 2
                    continue
                if nxt.isdigit():  # octal, up to three digits
                    octal = b""
                    j = i + 1
                    while j < len(body) and len(octal) < 3 and body[j : j + 1].isdigit():
                        octal += body[j : j + 1]
                        j += 1
                    out.append(int(octal, 8) & 0xFF)
                    i = j
                    continue
                if nxt in (b"\n", b"\r"):  # line continuation
                    i += 2
                    continue
                out += nxt
                i += 2
                continue
            out += char
            i += 1
        data = bytes(out)
    else:
        data = raw

    for bom, encoding in ((b"\xfe\xff", "utf-16-be"), (b"\xff\xfe", "utf-16-le")):
        if data.startswith(bom):
            return data[2:].decode(encoding, "replace").strip()
    try:
        return data.decode("utf-8").strip()
    except UnicodeDecodeError:
        # PDFDocEncoding is Latin-1 compatible for the characters we care about.
        return data.decode("latin-1", "replace").strip()


def _balanced_string_after(data: bytes, start: int) -> bytes:
    """Read the PDF string that begins at `start`, honouring nested parentheses."""
    if start >= len(data):
        return b""
    if data[start : start + 1] == b"<":
        end = data.find(b">", start)
        return data[start : end + 1] if end != -1 else b""
    if data[start : start + 1] != b"(":
        return b""
    depth = 0
    i = start
    while i < len(data):
        char = data[i : i + 1]
        if char == b"\\":
            i += 2
            continue
        if char == b"(":
            depth += 1
        elif char == b")":
            depth -= 1
            if depth == 0:
                return data[start : i + 1]
        i += 1
    return b""


def _find_info_value(data: bytes, key_pattern: bytes) -> str:
    """Pull one /Key value out of a document information dictionary."""
    for match in re.finditer(key_pattern, data):
        value = _balanced_string_after(data, match.end())
        if value:
            text = _decode_pdf_string(value)
            if text:
                return text
    return ""


def _inflate_streams(data: bytes, limit: int = MAX_STREAMS) -> bytes:
    """Concatenate whatever Flate-compressed streams we can decompress.

    Modern PDFs hide the XMP packet and cross-reference data in object streams;
    inflating them is the difference between finding a title and not.
    """
    chunks: list[bytes] = []
    for count, match in enumerate(_STREAM_RE.finditer(data)):
        if count >= limit:
            break
        end = data.find(b"endstream", match.end())
        if end == -1:
            continue
        blob = data[match.end() : end]
        if len(blob) > 4 * 1024 * 1024:
            continue
        try:
            chunks.append(zlib.decompress(blob))
        except zlib.error:
            try:
                chunks.append(zlib.decompressobj().decompress(blob))
            except zlib.error:
                continue
    return b"\n".join(chunks)


def _collect_urls(data: bytes) -> list[str]:
    """Every http(s) URL in the blob, most frequent first, order-stable."""
    counts: dict[str, int] = {}
    for match in _URI_RE.finditer(data):
        url = _decode_pdf_string(b"(" + match.group(1) + b")")
        if url.startswith(("http://", "https://")):
            counts[url] = counts.get(url, 0) + 1
    for match in _URL_IN_TEXT_RE.finditer(data):
        url = match.group(0).decode("latin-1", "replace").rstrip(".,;)")
        counts[url] = counts.get(url, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: -kv[1])
    return [url for url, _ in ordered]


def read_pdf_metadata(path: Path) -> PdfMetadata:
    """Read title/subject/keywords/URLs out of a PDF. Never raises."""
    path = Path(path)
    try:
        raw = path.read_bytes()[:MAX_SCAN_BYTES]
    except OSError:
        return PdfMetadata()
    if not raw.startswith(b"%PDF"):
        return PdfMetadata()

    inflated = _inflate_streams(raw)
    haystacks = (raw, inflated)

    title = ""
    for blob in haystacks:
        title = _find_info_value(blob, _INFO_KEY_RE["title"])
        if title:
            break
    if not title:
        for blob in haystacks:
            xmp = _XMP_TITLE_RE.search(blob)
            if xmp:
                title = _decode_pdf_string(xmp.group(1))
                break

    subject = _find_info_value(raw, _INFO_KEY_RE["subject"]) or _find_info_value(
        inflated, _INFO_KEY_RE["subject"]
    )
    keywords = _find_info_value(raw, _INFO_KEY_RE["keywords"]) or _find_info_value(
        inflated, _INFO_KEY_RE["keywords"]
    )

    urls: list[str] = []
    for candidate in (subject, keywords):
        if candidate.startswith(("http://", "https://")):
            urls.append(candidate.split()[0])
    for blob in haystacks:
        for url in _collect_urls(blob):
            if url not in urls:
                urls.append(url)

    return PdfMetadata(
        title=title.strip(),
        subject=subject.strip(),
        keywords=keywords.strip(),
        urls=tuple(urls[:40]),
    )


def read_spotlight_metadata(path: Path) -> PdfMetadata:
    """Ask macOS Spotlight, which often knows the title and origin URL.

    Returns empty metadata anywhere `mdls` is unavailable, so callers can
    always try it.
    """
    try:
        result = subprocess.run(
            ["mdls", "-name", "kMDItemTitle", "-name", "kMDItemWhereFroms", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return PdfMetadata()
    if result.returncode != 0:
        return PdfMetadata()

    title = ""
    urls: list[str] = []
    title_match = re.search(r'kMDItemTitle\s*=\s*"(.*)"', result.stdout)
    if title_match:
        title = title_match.group(1).strip()
    for url_match in re.finditer(r'"(https?://[^"]+)"', result.stdout):
        urls.append(url_match.group(1))
    return PdfMetadata(title=title, urls=tuple(urls))
