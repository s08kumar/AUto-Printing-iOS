"""Render a URL to PDF by driving Safari on the Mac.

The newspaper apps offer no Print and no PDF, so an article can only leave them
as a link. Rendering that link has to happen somewhere signed in to the
subscription — which means Safari on the Mac, because a Shortcut's web view and
a headless browser are both logged out and would capture the paywall.

Safari has no scripting command for "Export as PDF", so this drives the menu
item through System Events. That needs Accessibility permission and is the
least robust part of this project; `check_environment` reports what is missing
rather than failing obscurely.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

IS_MACOS = sys.platform == "darwin"

# Safari's File menu item, ellipsis included — System Events matches exactly.
EXPORT_MENU_ITEM = "Export as PDF…"

DEFAULT_LOAD_TIMEOUT = 45.0

ACCESSIBILITY_HELP = """\
macOS is blocking control of Safari (Accessibility).

  System Settings > Privacy & Security > Accessibility
  Add and switch on:  Terminal
  (and /usr/bin/python3 if you run the watcher in the background)

Automation permission is also asked for the first time this runs — allow
Terminal to control Safari and System Events when prompted."""


@dataclass
class RenderResult:
    url: str
    path: Path | None = None
    title: str = ""
    error: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.path is not None and self.path.is_file()


def _applescript_string(value: str) -> str:
    """Quote a Python string for embedding in AppleScript source."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _run_osascript(source: str, timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["osascript", "-"],
        input=source,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def page_title(url: str, timeout: float = DEFAULT_LOAD_TIMEOUT) -> RenderResult:
    """Open `url` in Safari, wait for it to load, and report its title.

    Kept separate from the export so the load can be verified on its own —
    when something goes wrong it matters whether the page arrived.
    """
    if not IS_MACOS:
        return RenderResult(url=url, error="rendering needs macOS and Safari")

    source = f"""
    set theURL to {_applescript_string(url)}
    tell application "Safari"
        activate
        set theDoc to make new document with properties {{URL:theURL}}
        set loaded to false
        repeat with i from 1 to {int(timeout * 2)}
            delay 0.5
            try
                if (do JavaScript "document.readyState" in current tab of front window) is "complete" then
                    set loaded to true
                    exit repeat
                end if
            end try
        end repeat
        if not loaded then return "TIMEOUT"
        delay 1.5
        return (do JavaScript "document.title" in current tab of front window)
    end tell
    """
    try:
        result = _run_osascript(source, timeout + 30)
    except (OSError, subprocess.SubprocessError) as error:
        return RenderResult(url=url, error=f"could not run osascript: {error}")

    output = (result.stdout or "").strip()
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        error = "Safari could not be controlled"
        if "-1743" in stderr or "not allowed" in stderr.lower():
            error = "permission denied controlling Safari"
        return RenderResult(url=url, error=f"{error}: {stderr[:300]}")
    if output == "TIMEOUT":
        return RenderResult(url=url, error=f"page did not finish loading within {timeout:.0f}s")
    return RenderResult(url=url, title=output)


def render_url(
    url: str,
    out_dir: Path,
    *,
    timeout: float = DEFAULT_LOAD_TIMEOUT,
    close_tab: bool = True,
) -> RenderResult:
    """Render `url` to a PDF in `out_dir`, named after the page title."""
    from .titles import sanitise_component

    loaded = page_title(url, timeout=timeout)
    if loaded.error:
        return loaded

    title = sanitise_component(loaded.title) or "Untitled article"
    out_dir = Path(out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Export into a scratch folder first: the save dialog will not overwrite,
    # and a half-written file in the inbox would be picked up mid-write.
    with tempfile.TemporaryDirectory() as scratch:
        source = f"""
        tell application "Safari" to activate
        delay 0.4
        tell application "System Events"
            tell process "Safari"
                set frontmost to true
                click menu item {_applescript_string(EXPORT_MENU_ITEM)} ¬
                    of menu "File" of menu bar 1
                delay 1.5
                keystroke "g" using {{command down, shift down}}
                delay 0.8
                keystroke {_applescript_string(str(scratch))}
                delay 0.5
                keystroke return
                delay 1.0
                keystroke "a" using {{command down}}
                delay 0.2
                keystroke {_applescript_string(title)}
                delay 0.5
                keystroke return
                delay 2.5
            end tell
        end tell
        return "OK"
        """
        try:
            result = _run_osascript(source, 120)
        except (OSError, subprocess.SubprocessError) as error:
            return RenderResult(url=url, title=title, error=f"export failed: {error}")

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            error = "could not drive Safari's Export as PDF"
            if "-1719" in stderr or "-25211" in stderr or "assistive" in stderr.lower():
                error = "Accessibility permission is missing"
            return RenderResult(url=url, title=title, error=f"{error}: {stderr[:300]}")

        produced = sorted(Path(scratch).glob("*.pdf"))
        if not produced:
            return RenderResult(
                url=url,
                title=title,
                error="Safari's export produced no file (the save dialog may have "
                      "been left open, or the menu item name has changed)",
            )
        destination = out_dir / f"{title}.pdf"
        index = 2
        while destination.exists():
            destination = out_dir / f"{title} ({index}).pdf"
            index += 1
        shutil.move(str(produced[0]), str(destination))

    if close_tab:
        _run_osascript(
            'tell application "Safari" to close front window', 15
        )

    return RenderResult(url=url, path=destination, title=title)


URL_IN_TEXT = re.compile(r"https?://[^\s<>\"']{8,2000}")


def url_from_drop(path: Path) -> str:
    """The URL inside a small text file the iPhone dropped, or ""."""
    path = Path(path)
    if path.suffix.lower() not in (".txt", ".url", ".webloc"):
        return ""
    try:
        if path.stat().st_size > 64 * 1024:
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    match = URL_IN_TEXT.search(text)
    return match.group(0).rstrip(".,;)]") if match else ""


def check_environment() -> list[str]:
    """Problems that would stop rendering, in the order worth fixing them."""
    problems: list[str] = []
    if not IS_MACOS:
        return ["rendering needs macOS and Safari"]
    if not Path("/Applications/Safari.app").exists():
        problems.append("Safari is not installed at /Applications/Safari.app")

    probe = 'tell application "System Events" to return name of first process'
    try:
        result = _run_osascript(probe, 20)
    except (OSError, subprocess.SubprocessError) as error:
        return [f"osascript is unavailable: {error}"]
    if result.returncode != 0:
        problems.append("Accessibility permission is missing")
    return problems
