"""macOS keeps iCloud Drive behind Full Disk Access.

Without that permission, listing the library raises `PermissionError` — or,
worse, appears to succeed and returns nothing, so the watcher sits there
filing nothing and saying nothing about it. Detecting it explicitly and saying
what to do is the difference between a five-minute fix and an afternoon.
"""

from __future__ import annotations

import sys
from pathlib import Path

IS_MACOS = sys.platform == "darwin"

PROTECTED_MARKERS = ("Mobile Documents", "com~apple~CloudDocs")

FULL_DISK_ACCESS_HELP = """\
macOS is blocking access to iCloud Drive (Full Disk Access).

To fix it:
  1. Open System Settings > Privacy & Security > Full Disk Access
  2. Click +, then press Cmd-Shift-G and enter:  /usr/bin/python3
     Add it, and make sure its switch is on.
  3. Add Terminal too, so `article-filer` works when you run it by hand:
     /System/Applications/Utilities/Terminal.app
  4. Restart the watcher:
     launchctl kickstart -k gui/$UID/com.articlefiler.watcher

Nothing is lost in the meantime — files wait in the inbox until it can read
them."""


def is_protected(path: Path) -> bool:
    """True when `path` sits inside a folder macOS guards with TCC."""
    text = str(path)
    return any(marker in text for marker in PROTECTED_MARKERS)


def check_readable(path: Path) -> str | None:
    """Return a human-readable problem with reading `path`, or None if fine."""
    path = Path(path)
    if not path.exists():
        return f"does not exist: {path}"
    if not path.is_dir():
        return f"not a folder: {path}"
    try:
        next(iter(path.iterdir()), None)
    except PermissionError:
        return f"permission denied listing: {path}"
    except OSError as error:
        return f"cannot list {path}: {error}"
    return None


def access_error_message(path: Path, problem: str) -> str:
    """The problem, plus the Full Disk Access remedy when that is the cause."""
    lines = [problem]
    if "permission denied" in problem and IS_MACOS and is_protected(Path(path)):
        lines.append("")
        lines.append(FULL_DISK_ACCESS_HELP)
    return "\n".join(lines)
