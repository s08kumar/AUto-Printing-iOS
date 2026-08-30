"""Is a filed PDF the article, or the paywall that stood in front of it?

A Shortcut renders links in a web view that is not signed in to anything, so
a share can quietly produce a one-page "subscribe to continue" capture. That
looks identical to a real article in Finder — same name, same icon — and is
only obvious when you open it. This tells the two apart in bulk.

The signals are crude on purpose: page count, file size, how much text the
content streams hold, and whether that text reads like a subscription wall.
No PDF library, no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .pdfmeta import _inflate_streams

# Judging a PDF needs a sample, not the whole thing. These caps keep a
# 40-file library under a second instead of appearing to hang.
MAX_READ_BYTES = 2 * 1024 * 1024
MAX_INFLATED_BYTES = 2 * 1024 * 1024
MAX_TEXT_SCAN_BYTES = 1024 * 1024

_PAGE_RE = re.compile(rb"/Type\s*/Page[^s]")
_TEXT_SHOW_RE = re.compile(rb"\(([^()]{0,500})\)\s*Tj", re.DOTALL)
_TEXT_ARRAY_RE = re.compile(rb"\[([^\[\]]{0,1000})\]\s*TJ", re.DOTALL)
_TEXT_HEX_RE = re.compile(rb"<([0-9A-Fa-f\s]{4,2000})>\s*Tj", re.DOTALL)

# Phrases a paywall interstitial uses and an article almost never does.
PAYWALL_PHRASES = (
    "subscribe to continue",
    "subscribe now",
    "already a subscriber",
    "continue reading",
    "create an account to",
    "sign in to read",
    "to read the full",
    "start your free trial",
    "this article is for subscribers",
    "you have reached your limit",
    "register to continue",
)

# Below this, a "PDF of an article" is almost certainly not one.
SMALL_FILE_BYTES = 25_000
THIN_TEXT_CHARS = 900


@dataclass
class PdfReport:
    path: Path
    size: int = 0
    pages: int = 0
    text_chars: int = 0
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    readable: bool = True

    @property
    def suspicious(self) -> bool:
        return bool(self.reasons)

    @property
    def verdict(self) -> str:
        if not self.readable:
            return "unreadable"
        return "suspect" if self.suspicious else "looks fine"


def count_pages(data: bytes) -> int:
    """Number of page objects. `/Pages` is the tree node, so it is excluded."""
    return len(_PAGE_RE.findall(data))


def extract_text(data: bytes, limit: int = 200_000) -> str:
    """Rough text of the content streams, enough to spot a paywall phrase."""
    data = data[:MAX_TEXT_SCAN_BYTES]
    pieces: list[bytes] = []
    total = 0
    for pattern in (_TEXT_SHOW_RE, _TEXT_ARRAY_RE):
        for match in pattern.finditer(data):
            chunk = match.group(1)
            pieces.append(chunk)
            total += len(chunk)
            if total >= limit:
                break
    for match in _TEXT_HEX_RE.finditer(data):
        digits = re.sub(rb"[^0-9A-Fa-f]", b"", match.group(1))
        if len(digits) % 2:
            digits = digits[:-1]
        try:
            pieces.append(bytes.fromhex(digits.decode("ascii")))
        except ValueError:
            continue
        total += len(digits) // 2
        if total >= limit:
            break
    raw = b" ".join(pieces)
    raw = re.sub(rb"\\[0-7]{1,3}", b" ", raw)
    raw = re.sub(rb"\\(.)", rb"\1", raw)
    return raw.decode("latin-1", "replace")


def inspect(path: Path) -> PdfReport:
    """Judge one PDF. Never raises."""
    path = Path(path)
    report = PdfReport(path=path)
    try:
        report.size = path.stat().st_size
        with path.open("rb") as handle:
            raw = handle.read(MAX_READ_BYTES)
    except OSError:
        report.readable = False
        report.reasons.append("could not be read")
        return report

    if not raw.startswith(b"%PDF"):
        report.readable = False
        report.reasons.append("not a PDF")
        return report

    body = raw + b"\n" + _inflate_streams(raw)[:MAX_INFLATED_BYTES]
    report.pages = count_pages(body)
    text = extract_text(body)
    report.text_chars = len(text.strip())

    lowered = text.lower()
    hits = [phrase for phrase in PAYWALL_PHRASES if phrase in lowered]
    if hits:
        report.reasons.append(f"paywall wording: \"{hits[0]}\"")

    # Plenty of text settles it. A dense, image-free article is legitimately
    # small — 20 kB carrying 25,000 characters is a whole feature, not a stub —
    # so size only counts against a file we could not otherwise vouch for.
    substantial = report.text_chars >= THIN_TEXT_CHARS
    if report.size < SMALL_FILE_BYTES and not substantial:
        report.reasons.append(f"only {report.size / 1000:.0f} kB")
    if report.text_chars == 0:
        # Unreadable text is not evidence of absent text — many PDFs encode
        # glyphs in ways this deliberately simple extractor cannot follow. Say
        # so, and judge on size and page count alone.
        report.notes.append("could not read the text; judged on size and pages only")
    elif report.pages == 1 and report.text_chars < THIN_TEXT_CHARS:
        report.reasons.append("one page with almost no text")
    return report


def inspect_folder(folder: Path, limit: int = 0, progress=None) -> list[PdfReport]:
    """Inspect the PDFs in `folder`, newest first.

    Placeholders that iCloud has not downloaded are skipped rather than
    forcing a download that could take minutes.
    """
    folder = Path(folder)
    if not folder.is_dir():
        return []
    pdfs = [
        p for p in folder.rglob("*.pdf")
        if p.is_file() and not p.name.startswith(".")
    ]
    pdfs.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    if limit:
        pdfs = pdfs[:limit]

    reports = []
    for index, path in enumerate(pdfs, 1):
        if progress is not None:
            progress(index, len(pdfs), path)
        reports.append(inspect(path))
    return reports
