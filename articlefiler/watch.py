"""A polling watcher for the inbox folder.

Polling rather than FSEvents on purpose: iCloud Drive materialises files in
ways that filesystem-event APIs report inconsistently, and a five-second poll
over a folder that holds a handful of PDFs costs nothing.
"""

from __future__ import annotations

import logging
import signal
import time
from pathlib import Path

from .config import Config
from .filer import Plan, process_inbox
from .publications import PublicationRegistry

log = logging.getLogger("article-filer")


def setup_logging(config: Config, verbose: bool = False) -> None:
    log_file = config.log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(log_file, encoding="utf-8")]
    handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )


class Watcher:
    """Watches the inbox until asked to stop."""

    def __init__(self, config: Config, registry: PublicationRegistry):
        self.config = config
        self.registry = registry
        self._running = True

    def stop(self, *_args) -> None:
        log.info("stopping")
        self._running = False

    def install_signal_handlers(self) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self.stop)

    def tick(self) -> list[Plan]:
        try:
            plans = process_inbox(self.config, self.registry)
        except Exception:  # a bad file must never kill the daemon
            log.exception("failed while processing the inbox")
            return []
        for plan in plans:
            if plan.action == "move":
                log.info("filed %s -> %s", plan.source.name, plan.destination.name)
                for note in plan.decision.notes:
                    log.debug("  %s", note)
            elif plan.action == "duplicate":
                log.info("dropped duplicate %s", plan.source.name)
            else:
                log.debug("skipped %s (%s)", plan.source.name, plan.reason)
        return plans

    def run(self) -> None:
        self.config.inbox_path.mkdir(parents=True, exist_ok=True)
        self.config.library_path.mkdir(parents=True, exist_ok=True)
        log.info("watching %s", self.config.inbox_path)
        log.info("filing into %s", self.config.library_path)
        while self._running:
            self.tick()
            deadline = time.monotonic() + self.config.poll_interval
            while self._running and time.monotonic() < deadline:
                time.sleep(min(0.5, max(0.05, deadline - time.monotonic())))
        log.info("stopped")
