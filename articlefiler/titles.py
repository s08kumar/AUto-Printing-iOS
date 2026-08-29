"""Turning a raw page title into a clean, filesystem-safe filename component."""

from __future__ import annotations

import html
import re
import unicodedata

# Illegal or hostile in a filename on APFS, iCloud Drive, SMB and Windows.
_ILLEGAL = r'/\\:*?"<>|\x00-\x1f\x7f'
_ILLEGAL_RE = re.compile("[" + _ILLEGAL + "]")

# Leading site furniture that share sheets sometimes prepend.
_LEADING_JUNK_RE = re.compile(
    r"^\s*(?:opinion|analysis|exclusive|breaking|live|video|podcast|editorial)\s*[:|\-–—]\s*",
    re.IGNORECASE,
)

_WHITESPACE_RE = re.compile(r"\s+")
_CONTROL_WHITESPACE_RE = re.compile(r"[\r\n\t\v\f]")

# " ... (1)", " ... copy", " ... 2" that macOS/iOS add on a name collision.
_COPY_SUFFIX_RE = re.compile(r"\s*(?:\(\d{1,3}\)|copy(?:\s+\d+)?)\s*$", re.IGNORECASE)

DEFAULT_MAX_TITLE_LENGTH = 110
DEFAULT_TEMPLATE = "{acronym} - {title}"


def clean_title(raw: str, *, strip_leading_junk: bool = False) -> str:
    """Normalise a page title into something worth putting in a filename.

    Decodes HTML entities, normalises Unicode, flattens whitespace and removes
    characters that a filesystem would reject. Curly quotes and em dashes are
    kept: they are legal and they read better.

    >>> clean_title("Fed&rsquo;s next move:  what\\u2019s at stake?")
    'Fed’s next move- what’s at stake'
    """
    if not raw:
        return ""
    text = html.unescape(str(raw))
    text = unicodedata.normalize("NFC", text)
    text = text.replace(" ", " ").replace("​", "")
    text = _CONTROL_WHITESPACE_RE.sub(" ", text)
    if strip_leading_junk:
        text = _LEADING_JUNK_RE.sub("", text)
    # ':' and '/' carry meaning in a headline, so map them rather than drop them.
    text = text.replace(":", "-").replace("/", "-")
    text = _ILLEGAL_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    text = re.sub(r"\s*-\s*-\s*", " - ", text)
    text = text.strip(" .-–—")
    return text


def truncate(text: str, limit: int = DEFAULT_MAX_TITLE_LENGTH) -> str:
    """Shorten to `limit` characters on a word boundary, without a dangling comma.

    >>> truncate("one two three four", 11)
    'one two'
    """
    if limit <= 0 or len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    if space >= limit // 2:
        cut = cut[:space]
    return cut.rstrip(" ,;:.-–—")


def sanitise_component(raw: str, *, limit: int = DEFAULT_MAX_TITLE_LENGTH) -> str:
    """`clean_title` followed by `truncate`."""
    return truncate(clean_title(raw), limit)


def strip_copy_suffix(stem: str) -> str:
    """Drop a trailing " (2)" / " copy" that iOS or macOS added on collision."""
    stripped = _COPY_SUFFIX_RE.sub("", stem).strip()
    return stripped or stem


def build_filename(
    acronym: str | None,
    title: str,
    *,
    extension: str = ".pdf",
    template: str = DEFAULT_TEMPLATE,
    max_title_length: int = DEFAULT_MAX_TITLE_LENGTH,
    date: str = "",
    fallback_title: str = "Untitled article",
) -> str:
    """Compose "NYT - Headline.pdf".

    An unknown publication collapses the template gracefully rather than
    leaving a limp " - Headline.pdf" behind.

    >>> build_filename("NYT", "The Fed blinks")
    'NYT - The Fed blinks.pdf'
    >>> build_filename(None, "The Fed blinks")
    'The Fed blinks.pdf'
    """
    clean = sanitise_component(title, limit=max_title_length) or fallback_title
    acr = clean_title(acronym or "").strip()
    stem = template.format(acronym=acr, title=clean, date=date or "")
    # Collapse the gaps a missing acronym or date leaves behind.
    stem = re.sub(r"^[\s\-–—_]+", "", stem)
    stem = re.sub(r"[\s\-–—_]+$", "", stem)
    stem = _WHITESPACE_RE.sub(" ", stem).strip()
    stem = _ILLEGAL_RE.sub("", stem) or fallback_title
    ext = extension if extension.startswith(".") or not extension else "." + extension
    return stem + ext


_ALREADY_PREFIXED_RE = re.compile(r"^([A-Z][A-Z0-9&]{1,7})\s+-\s+(\S.*)$")


def split_prefixed(stem: str) -> tuple[str, str] | None:
    """Split "NYT - Headline" into ("NYT", "Headline"), else None.

    >>> split_prefixed("WSJ - Markets wobble")
    ('WSJ', 'Markets wobble')
    >>> split_prefixed("Markets wobble - a note")
    """
    match = _ALREADY_PREFIXED_RE.match(stem.strip())
    if not match:
        return None
    return match.group(1), match.group(2).strip()
