"""Deciding which publication an article came from, and what to call the file."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Iterable
from pathlib import Path

from .publications import AGGREGATOR_HOSTS, Publication, PublicationRegistry, normalise_host
from .titles import build_filename, clean_title, split_prefixed, strip_copy_suffix

# Titles that a PDF producer invented rather than a headline anyone wrote.
_JUNK_TITLE_RE = re.compile(
    r"^(?:"
    r"untitled|document\d*|print|microsoft word\s*-.*"
    # Shortcuts' Make PDF emits an unnamed file, so Save File falls back to a
    # UUID. That is an identifier, not a headline.
    r"|[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}"
    r"|.*\.(?:docx?|indd|pages|rtf|html?)"
    r")$",
    re.IGNORECASE,
)


@dataclass
class Signals:
    """Everything we know about one article before deciding on a name."""

    url: str = ""
    title: str = ""
    filename_stem: str = ""
    metadata_title: str = ""
    metadata_urls: tuple[str, ...] = ()

    def candidate_urls(self) -> list[str]:
        seen: list[str] = []
        for url in (self.url, *self.metadata_urls):
            if url and url not in seen:
                seen.append(url)
        return seen

    def candidate_titles(self) -> list[str]:
        out: list[str] = []
        for value in (self.title, self.metadata_title, self.filename_stem):
            value = (value or "").strip()
            if value and not _JUNK_TITLE_RE.match(value) and value not in out:
                out.append(value)
        return out


@dataclass
class Decision:
    """The outcome: what to call the file, and how we worked it out."""

    filename: str
    acronym: str = ""
    title: str = ""
    publication: Publication | None = None
    url: str = ""
    source: str = "unknown"  # url | title-suffix | existing-prefix | fallback | unknown
    notes: list[str] = field(default_factory=list)

    @property
    def identified(self) -> bool:
        return self.publication is not None


_SLUG_NOISE_RE = re.compile(r"\.(?:html?|php|aspx?|cms|ece)$", re.IGNORECASE)
_SLUG_ID_RE = re.compile(r"^(?:\d+|[0-9a-f]{8,}|index|amp|story|article)$", re.IGNORECASE)

# Paths that are never the article: bylines, section fronts, tag pages and the
# publisher's own housekeeping. A byline URL is the commonest link on a page,
# so frequency ranking picks it first and names the article after its author.
_NON_ARTICLE_SEGMENT = frozenset(
    {
        "by", "author", "authors", "byline", "contributor", "people",
        "section", "sections", "topic", "topics", "tag", "tags", "category",
        "subscribe", "subscription", "newsletters", "newsletter", "account",
        "privacy", "terms", "help", "careers", "jobs", "about", "contact",
        "search", "podcasts", "video", "videos", "games", "puzzles", "crossword",
    }
)

# "/2026/08/30/" — a strong signal that a URL is an article rather than a
# landing page, across NYT, WaPo, HBR, the Guardian and others.
_DATED_PATH_RE = re.compile(r"/(?:19|20)\d\d/\d\d?/\d\d?/")


def _is_article_url(url: str) -> bool:
    """True when a URL looks like a specific piece rather than a listing."""
    tail = url.split("://", 1)[-1]
    if "/" not in tail:
        return False
    path = "/" + tail.split("/", 1)[1].split("?")[0].split("#")[0]
    segments = [s.lower() for s in path.split("/") if s]
    if not segments:
        return False
    if any(segment in _NON_ARTICLE_SEGMENT for segment in segments):
        return False
    return bool(_DATED_PATH_RE.search(path)) or len(segments[-1]) > 24


def select_article_url(urls: "Iterable[str]", publication) -> str:
    """Pick the URL most likely to be *this* article, or "" when unsure.

    A rendered news page links to dozens of other pieces, so being sure is
    rare. Guessing produces a confidently wrong headline, which is worse than
    no headline at all — so ambiguity returns nothing and lets the caller fall
    back.
    """
    domains = tuple(publication.domains) if publication is not None else ()
    candidates = []
    for url in urls:
        host = normalise_host(url)
        if domains and not any(host == d or host.endswith("." + d) for d in domains):
            continue
        if _is_article_url(url):
            candidates.append(url)

    dated = [u for u in candidates if _DATED_PATH_RE.search(u)]
    pool = dated or candidates
    if len(pool) != 1:
        # Zero, or several equally plausible articles: say nothing.
        return ""
    return pool[0]


def title_from_url(url: str) -> str:
    """Recover a readable headline from an article URL's slug.

    Make PDF produces a file with no title, so the URL is often the only thing
    naming the piece:
    ".../2026/08/30/world/asia/nepal-floods.html" -> "Nepal Floods".

    >>> title_from_url("https://www.nytimes.com/2026/08/30/world/asia/nepal-floods.html")
    'Nepal Floods'
    >>> title_from_url("https://www.wsj.com/")
    ''
    """
    if not url:
        return ""
    path = url.split("://", 1)[-1].split("/", 1)
    if len(path) < 2:
        return ""
    segments = [s for s in path[1].split("?")[0].split("#")[0].split("/") if s]
    for segment in reversed(segments):
        segment = _SLUG_NOISE_RE.sub("", segment)
        if not segment or _SLUG_ID_RE.match(segment):
            continue
        words = [w for w in re.split(r"[-_+]+", segment) if w and not w.isdigit()]
        if len(words) < 2:  # a single word is rarely the headline
            continue
        return " ".join(word[:1].upper() + word[1:] for word in words)
    return ""


def read_sidecar(path: Path) -> Signals:
    """Read a `<name>.json` or `<name>.url.txt` companion written by the Shortcut.

    The Shortcut names files correctly on its own, so a sidecar is optional —
    but when one is present it is the most trustworthy signal we have.
    """
    stem_path = path.with_suffix("")
    for candidate in (path.with_suffix(".json"), Path(str(stem_path) + ".json")):
        if candidate.is_file() and candidate != path:
            try:
                raw = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(raw, dict):
                return Signals(
                    url=str(raw.get("url") or "").strip(),
                    title=str(raw.get("title") or "").strip(),
                )
    for candidate in (Path(str(stem_path) + ".url.txt"), path.with_suffix(".url")):
        if candidate.is_file():
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            match = re.search(r"https?://\S+", text)
            if match:
                return Signals(url=match.group(0).strip())
    return Signals()


def resolve_aggregator_url(url: str, *, timeout: float = 8.0) -> str:
    """Follow an Apple News / shortener link to the publisher's own URL.

    Only aggregator and shortener hosts are followed — we never fetch an
    arbitrary URL just to name a file. Returns `url` unchanged on any failure.
    """
    import urllib.error
    import urllib.request

    host = normalise_host(url)
    if not host:
        return url
    is_shortener = host in AGGREGATOR_HOSTS or (len(host) <= 9 and host.count(".") == 1)
    if not is_shortener:
        return url

    request = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "Mozilla/5.0 (Macintosh) article-filer"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            final = response.geturl()
    except (urllib.error.URLError, OSError, ValueError):
        return url
    return final or url


def classify(
    signals: Signals,
    registry: PublicationRegistry,
    *,
    extension: str = ".pdf",
    template: str = "{acronym} - {title}",
    max_title_length: int = 110,
    fallback_acronym: str = "",
    date: str = "",
) -> Decision:
    """Work out the publication and compose the filename."""
    notes: list[str] = []

    # 1. A file we have already filed keeps its identity.
    existing = split_prefixed(strip_copy_suffix(signals.filename_stem),
                              registry.acronyms())
    existing_pub = registry.by_acronym(existing[0]) if existing else None

    # 2. The URL is the strongest signal.
    publication: Publication | None = None
    matched_url = ""
    for url in signals.candidate_urls():
        found = registry.match_url(url)
        if found:
            publication, matched_url = found, url
            break
        if not matched_url and normalise_host(url) not in AGGREGATOR_HOSTS:
            matched_url = url
    source = "url" if publication else "unknown"

    # 3. Otherwise the publication usually signs the page title.
    title = ""
    for candidate in signals.candidate_titles():
        hit = registry.match_title(candidate)
        if hit:
            found_pub, trimmed = hit
            if publication is None:
                publication, source = found_pub, "title-suffix"
            if found_pub is publication or publication is None:
                title = trimmed
                break
        if not title:
            title = candidate
    if not title:
        candidates = signals.candidate_titles()
        if candidates:
            title = candidates[0]
        else:
            # No headline anywhere. A URL slug will do, but only when one
            # URL is unambiguously the article.
            chosen = select_article_url(signals.candidate_urls(), publication)
            title = title_from_url(chosen) if chosen else ""
            if title:
                notes.append(f"headline recovered from {chosen}")
            else:
                notes.append(
                    "no headline found: the PDF has no title, and its links do "
                    "not single out one article"
                )
                title = signals.filename_stem

    # Strip the publication's own name even when the URL identified it.
    if publication is not None and title:
        hit = registry.match_title(title)
        if hit and hit[0] is publication:
            title = hit[1]

    # 4. An existing correct prefix fills the remaining gaps.
    if existing:
        if publication is None and existing_pub is not None:
            publication, source = existing_pub, "existing-prefix"
        if publication is not None and existing[0].upper() == publication.acronym.upper():
            title = existing[1]
            notes.append("already filed under this prefix")

    if publication is None and fallback_acronym:
        source = "fallback"
        notes.append(f"unknown publication, using fallback {fallback_acronym}")

    acronym = publication.acronym if publication else fallback_acronym
    if publication is None and not fallback_acronym:
        notes.append("publication not identified; filing without a prefix")

    filename = build_filename(
        acronym,
        title,
        extension=extension,
        template=template,
        max_title_length=max_title_length,
        date=date,
    )
    return Decision(
        filename=filename,
        acronym=acronym or "",
        title=clean_title(title),
        publication=publication,
        url=matched_url,
        source=source,
        notes=notes,
    )
