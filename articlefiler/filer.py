"""Renaming a downloaded article and moving it into the library."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .classify import Decision, Signals, classify, read_sidecar, resolve_aggregator_url
from .config import Config
from .pdfmeta import read_pdf_metadata, read_spotlight_metadata
from .publications import PublicationRegistry
from .titles import strip_copy_suffix

# iCloud keeps not-yet-downloaded files as a hidden ".name.ext.icloud" stub.
_ICLOUD_STUB_RE = re.compile(r"^\.(?P<real>.+)\.icloud$")

SIDECAR_SUFFIXES = (".json", ".url", ".url.txt")


@dataclass
class Plan:
    """What we intend to do with one file."""

    source: Path
    destination: Path
    decision: Decision
    action: str = "move"  # move | skip | duplicate
    reason: str = ""

    @property
    def renamed(self) -> bool:
        return self.source.name != self.destination.name

    def describe(self) -> str:
        if self.action == "skip":
            return f"skip   {self.source.name}  ({self.reason})"
        if self.action == "duplicate":
            return f"dup    {self.source.name}  (identical copy already filed)"
        arrow = "->" if self.renamed else "=="
        return f"file   {self.source.name}\n       {arrow} {self.destination}"


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def is_icloud_stub(path: Path) -> bool:
    return bool(_ICLOUD_STUB_RE.match(path.name))


def request_icloud_download(path: Path) -> bool:
    """Ask iCloud to materialise a placeholder file. macOS only; best effort."""
    try:
        result = subprocess.run(
            ["brctl", "download", str(path)], capture_output=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def gather_signals(path: Path, config: Config) -> Signals:
    """Collect every clue about `path` — sidecar, PDF metadata, Spotlight, name."""
    signals = read_sidecar(path)
    signals.filename_stem = strip_copy_suffix(path.stem)

    if path.suffix.lower() == ".pdf":
        meta = read_pdf_metadata(path)
        if not meta.title:
            spotlight = read_spotlight_metadata(path)
            meta.title = meta.title or spotlight.title
            meta.urls = meta.urls or spotlight.urls
        signals.metadata_title = meta.title
        signals.metadata_urls = meta.urls

    if config.resolve_redirects and signals.url:
        signals.url = resolve_aggregator_url(signals.url, timeout=config.network_timeout)
    return signals


def destination_folder(config: Config, decision: Decision, when: datetime) -> Path:
    library = config.library_path
    if config.subfolder == "publication":
        return library / (decision.acronym or "Unsorted")
    if config.subfolder == "month":
        return library / when.strftime("%Y-%m")
    return library


def unique_path(path: Path) -> Path:
    """`path`, or `path` with " (2)", " (3)" … appended until it is free."""
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not find a free filename near {path}")


def plan_file(
    path: Path,
    config: Config,
    registry: PublicationRegistry,
    *,
    now: datetime | None = None,
) -> Plan:
    """Decide what to do with one file, without touching the disk."""
    now = now or datetime.now()
    empty = Decision(filename=path.name)

    if is_icloud_stub(path):
        return Plan(path, path, empty, action="skip", reason="not downloaded from iCloud yet")
    if path.name.startswith("."):
        return Plan(path, path, empty, action="skip", reason="hidden file")
    if path.suffix.lower() not in config.extensions:
        return Plan(path, path, empty, action="skip", reason=f"ignoring {path.suffix or 'no'} files")
    if any(str(path).endswith(suffix) for suffix in SIDECAR_SUFFIXES):
        return Plan(path, path, empty, action="skip", reason="sidecar file")

    signals = gather_signals(path, config)
    decision = classify(
        signals,
        registry,
        extension=path.suffix.lower(),
        template=config.template,
        max_title_length=config.max_title_length,
        fallback_acronym=config.fallback_acronym,
        date=now.strftime("%Y-%m-%d"),
    )

    folder = destination_folder(config, decision, now)
    target = folder / decision.filename

    if target.exists() and target.resolve() != path.resolve():
        try:
            if sha256(target) == sha256(path):
                return Plan(path, target, decision, action="duplicate")
        except OSError:
            pass
        target = unique_path(target)

    if target.resolve() == path.resolve():
        return Plan(path, target, decision, action="skip", reason="already correctly filed")

    return Plan(path, target, decision, action="move")


def apply_plan(plan: Plan, *, dry_run: bool = False, keep_duplicates: bool = False) -> Plan:
    """Carry out a plan. Returns the plan, with `destination` set to reality."""
    if plan.action == "skip" or dry_run:
        return plan

    if plan.action == "duplicate":
        if not keep_duplicates:
            plan.source.unlink(missing_ok=True)
            _remove_sidecars(plan.source)
        return plan

    plan.destination.parent.mkdir(parents=True, exist_ok=True)
    final = unique_path(plan.destination)
    try:
        os.replace(plan.source, final)
    except OSError:
        # Different volumes, or iCloud being iCloud.
        shutil.move(str(plan.source), str(final))
    plan.destination = final
    _remove_sidecars(plan.source)
    return plan


def _remove_sidecars(path: Path) -> None:
    stem = str(path.with_suffix(""))
    for suffix in SIDECAR_SUFFIXES:
        sidecar = Path(stem + suffix)
        if sidecar.is_file():
            sidecar.unlink(missing_ok=True)


def is_settled(path: Path, settle_seconds: float) -> bool:
    """True when the file has stopped growing — iCloud may still be writing it."""
    try:
        stat = path.stat()
    except OSError:
        return False
    if settle_seconds <= 0:
        return True
    age = datetime.now().timestamp() - stat.st_mtime
    return age >= settle_seconds and stat.st_size > 0


def iter_inbox(config: Config) -> list[Path]:
    """Fileable entries sitting in the inbox, oldest first."""
    inbox = config.inbox_path
    if not inbox.is_dir():
        return []
    entries = [p for p in inbox.iterdir() if p.is_file()]
    entries.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0)
    return entries


def process_inbox(
    config: Config,
    registry: PublicationRegistry,
    *,
    dry_run: bool = False,
    settle: bool = True,
) -> list[Plan]:
    """Rename and file everything currently sitting in the inbox."""
    results: list[Plan] = []
    for path in iter_inbox(config):
        if is_icloud_stub(path):
            request_icloud_download(path)
            continue
        if settle and not is_settled(path, config.settle_seconds):
            continue
        plan = plan_file(path, config, registry)
        results.append(apply_plan(plan, dry_run=dry_run))
    return results
