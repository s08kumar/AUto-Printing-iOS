"""The publication registry: maps a URL host or a page-title suffix to an acronym."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

_DATA_FILE = Path(__file__).with_name("data") / "publications.json"

# Hosts that only ever wrap somebody else's article, so their own domain must
# never be treated as the publication (Apple News, link shorteners, read-later
# services). We fall back to the page title for these.
AGGREGATOR_HOSTS = frozenset(
    {
        "apple.news",
        "news.google.com",
        "getpocket.com",
        "instapaper.com",
        "t.co",
        "bit.ly",
        "lnkd.in",
        "flip.it",
        "webcache.googleusercontent.com",
    }
)

# Sub-domain noise that carries no publication meaning.
_HOST_NOISE = ("www.", "m.", "amp.", "mobile.", "eu.", "us.", "in.")


@dataclass(frozen=True)
class Publication:
    """One newspaper, magazine or research house."""

    acronym: str
    name: str
    domains: tuple[str, ...] = ()
    title_suffixes: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict) -> "Publication":
        return cls(
            acronym=str(raw["acronym"]).strip(),
            name=str(raw.get("name") or raw["acronym"]).strip(),
            domains=tuple(
                d.strip().lower().lstrip(".") for d in raw.get("domains", []) if str(d).strip()
            ),
            title_suffixes=tuple(
                s.strip() for s in raw.get("title_suffixes", []) if str(s).strip()
            ),
        )

    def to_dict(self) -> dict:
        return {
            "acronym": self.acronym,
            "name": self.name,
            "domains": list(self.domains),
            "title_suffixes": list(self.title_suffixes),
        }


def normalise_host(value: str) -> str:
    """Reduce a URL (or a bare host) to a comparable lower-case host.

    >>> normalise_host("https://www.nytimes.com/2026/01/02/x.html?s=1")
    'nytimes.com'
    >>> normalise_host("M.Economist.com:8443")
    'economist.com'
    """
    if not value:
        return ""
    host = value.strip()
    host = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", host)  # scheme
    host = host.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    host = host.rsplit("@", 1)[-1]  # userinfo
    host = host.split(":", 1)[0]  # port
    host = host.strip(".").lower()
    for noise in _HOST_NOISE:
        if host.startswith(noise) and len(host) > len(noise) + 3:
            host = host[len(noise) :]
            break
    return host


def _host_matches(host: str, domain: str) -> bool:
    """True when `host` is `domain` or a sub-domain of it."""
    return host == domain or host.endswith("." + domain)


class PublicationRegistry:
    """Lookup table over the known publications."""

    def __init__(self, publications: Iterable[Publication]):
        self._publications: list[Publication] = []
        self._by_acronym: dict[str, Publication] = {}
        for pub in publications:
            self.add(pub)

    # -- construction ---------------------------------------------------

    @classmethod
    def from_json(cls, path: Path) -> "PublicationRegistry":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        entries = raw["publications"] if isinstance(raw, dict) else raw
        return cls(Publication.from_dict(e) for e in entries)

    @classmethod
    def bundled(cls) -> "PublicationRegistry":
        return cls.from_json(_DATA_FILE)

    @classmethod
    def load(cls, overrides: Sequence[Path] = ()) -> "PublicationRegistry":
        """The bundled registry, with later files overriding earlier acronyms."""
        registry = cls.bundled()
        for path in overrides:
            path = Path(path)
            if path.is_file():
                registry.merge(cls.from_json(path))
        return registry

    # -- mutation -------------------------------------------------------

    def add(self, pub: Publication) -> None:
        """Add a publication, replacing any existing entry with the same acronym."""
        key = pub.acronym.upper()
        existing = self._by_acronym.get(key)
        if existing is not None:
            self._publications.remove(existing)
        self._by_acronym[key] = pub
        self._publications.append(pub)

    def merge(self, other: "PublicationRegistry") -> None:
        for pub in other:
            self.add(pub)

    # -- access ---------------------------------------------------------

    def __iter__(self) -> Iterator[Publication]:
        return iter(self._publications)

    def __len__(self) -> int:
        return len(self._publications)

    def by_acronym(self, acronym: str) -> Publication | None:
        return self._by_acronym.get((acronym or "").strip().upper())

    def match_url(self, url: str) -> Publication | None:
        """Find the publication that owns `url`, longest domain first."""
        host = normalise_host(url)
        if not host or host in AGGREGATOR_HOSTS:
            return None
        best: tuple[int, Publication] | None = None
        for pub in self._publications:
            for domain in pub.domains:
                if _host_matches(host, domain) and (best is None or len(domain) > best[0]):
                    best = (len(domain), pub)
        return best[1] if best else None

    def match_title(self, title: str) -> tuple[Publication, str] | None:
        """Find a publication named in the trailing segment of a page title.

        Returns `(publication, title_without_the_suffix)`, longest suffix first
        so that "The Hindu BusinessLine" beats "The Hindu".
        """
        if not title:
            return None
        best: tuple[int, Publication, str] | None = None
        for pub in self._publications:
            for suffix in pub.title_suffixes:
                trimmed = _strip_suffix(title, suffix)
                if trimmed is not None and (best is None or len(suffix) > best[0]):
                    best = (len(suffix), pub, trimmed)
        if best is None:
            return None
        return best[1], best[2]

    def acronyms(self) -> list[str]:
        return [p.acronym for p in self._publications]

    def domain_map(self) -> dict[str, str]:
        """Flat {domain: acronym} map, for exporting into an iOS Shortcut."""
        mapping: dict[str, str] = {}
        for pub in self._publications:
            for domain in pub.domains:
                mapping.setdefault(domain, pub.acronym)
        return mapping


# Separators a site may put between the headline and its own name.
_SEPARATORS = ("|", "–", "—", "-", "·", "•", "«", "»", "::", "~")

_SEPARATOR_CLASS = "".join(re.escape(s) for s in _SEPARATORS if len(s) == 1)


def _strip_suffix(title: str, suffix: str) -> str | None:
    """Remove a trailing " - <suffix>" from `title`; None when it is not there."""
    pattern = re.compile(
        r"\s*(?:[" + _SEPARATOR_CLASS + r"]|::)\s*" + re.escape(suffix) + r"\s*$",
        re.IGNORECASE,
    )
    trimmed, count = pattern.subn("", title)
    if count and trimmed.strip():
        return trimmed.strip()
    return None


def load_default_registry() -> PublicationRegistry:
    """Bundled registry plus the user's overrides file, when one exists."""
    from .config import user_publications_path

    return PublicationRegistry.load([user_publications_path()])
