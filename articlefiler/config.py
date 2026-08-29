"""Where things live, and the handful of knobs worth turning."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .titles import DEFAULT_MAX_TITLE_LENGTH, DEFAULT_TEMPLATE

APP_NAME = "article-filer"

# The iCloud Drive root as macOS mounts it.
ICLOUD_ROOT = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"

# Satish's filing cabinet. Everything else is derived from this.
DEFAULT_LIBRARY_NAME = "NYT-WSJ-Mckinsey-HBR-Economist Articles"

# Anything dropped here by hand (Safari "Save as PDF", Files, AirDrop) gets
# renamed and moved into the library. The shortcut writes straight to the
# library, so this is the fallback lane, not the main one.
INBOX_NAME = "_Inbox"

FILEABLE_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".heic", ".webarchive", ".txt", ".md")

SUBFOLDER_MODES = ("none", "publication", "month")


def config_dir() -> Path:
    override = os.environ.get("ARTICLE_FILER_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base).expanduser() if base else Path.home() / ".config") / APP_NAME


def config_path() -> Path:
    return config_dir() / "config.json"


def user_publications_path() -> Path:
    return config_dir() / "publications.json"


def default_log_path() -> Path:
    mac_logs = Path.home() / "Library" / "Logs"
    if mac_logs.is_dir():
        return mac_logs / f"{APP_NAME}.log"
    return config_dir() / f"{APP_NAME}.log"


@dataclass
class Config:
    """Runtime settings, loaded from `~/.config/article-filer/config.json`."""

    library: str = str(ICLOUD_ROOT / DEFAULT_LIBRARY_NAME)
    inbox: str = ""  # defaults to <library>/_Inbox
    template: str = DEFAULT_TEMPLATE
    max_title_length: int = DEFAULT_MAX_TITLE_LENGTH
    subfolder: str = "none"
    fallback_acronym: str = ""  # "" leaves unknown publications un-prefixed
    extensions: tuple[str, ...] = FILEABLE_EXTENSIONS
    poll_interval: float = 5.0
    settle_seconds: float = 2.0
    log_path: str = ""
    resolve_redirects: bool = True  # follow apple.news / bit.ly to find the publisher
    network_timeout: float = 8.0

    # -- derived --------------------------------------------------------

    @property
    def library_path(self) -> Path:
        return Path(self.library).expanduser()

    @property
    def inbox_path(self) -> Path:
        if self.inbox:
            return Path(self.inbox).expanduser()
        return self.library_path / INBOX_NAME

    @property
    def log_file(self) -> Path:
        return Path(self.log_path).expanduser() if self.log_path else default_log_path()

    @property
    def icloud_relative_library(self) -> str:
        """The library as an iOS Shortcut spells it, e.g. "/Newspapers"."""
        try:
            relative = self.library_path.relative_to(ICLOUD_ROOT)
        except ValueError:
            return "/" + self.library_path.name
        return "/" + str(relative)

    # -- persistence ----------------------------------------------------

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or config_path()
        config = cls()
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            config = cls.from_dict(raw)
        return config

    @classmethod
    def from_dict(cls, raw: dict) -> "Config":
        known = {f for f in cls.__dataclass_fields__}
        data = {k: v for k, v in raw.items() if k in known}
        if "extensions" in data:
            data["extensions"] = tuple(
                e if e.startswith(".") else "." + e for e in data["extensions"]
            )
        config = cls(**data)
        config.validate()
        return config

    def validate(self) -> None:
        if self.subfolder not in SUBFOLDER_MODES:
            raise ValueError(
                f"subfolder must be one of {', '.join(SUBFOLDER_MODES)}, got {self.subfolder!r}"
            )
        if self.max_title_length < 10:
            raise ValueError("max_title_length must be at least 10")
        if "{title}" not in self.template:
            raise ValueError("template must contain {title}")

    def to_dict(self) -> dict:
        data = asdict(self)
        data["extensions"] = list(self.extensions)
        return data

    def save(self, path: Path | None = None) -> Path:
        path = path or config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        return path
