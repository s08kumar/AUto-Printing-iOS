"""Command line interface: `python3 -m articlefiler <command>`."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .classify import Signals, classify
from .config import Config, INBOX_NAME, SUBFOLDER_MODES, config_path, user_publications_path
from .filer import apply_plan, plan_file, process_inbox
from .publications import Publication, PublicationRegistry, load_default_registry
from .watch import Watcher, setup_logging


def _load(args) -> tuple[Config, PublicationRegistry]:
    config = Config.load(Path(args.config).expanduser() if args.config else None)
    if getattr(args, "library", None):
        config.library = str(Path(args.library).expanduser())
    if getattr(args, "inbox", None):
        config.inbox = str(Path(args.inbox).expanduser())
    config.validate()
    return config, load_default_registry()


# -- commands -----------------------------------------------------------


def cmd_init(args) -> int:
    config, _ = _load(args)
    config.library_path.mkdir(parents=True, exist_ok=True)
    config.inbox_path.mkdir(parents=True, exist_ok=True)
    path = config.save(Path(args.config).expanduser() if args.config else None)
    print(f"library : {config.library_path}")
    print(f"inbox   : {config.inbox_path}")
    print(f"config  : {path}")
    print(f"log     : {config.log_file}")
    print()
    print("In the iOS Shortcut, set the Save File destination to:")
    print(f"  {config.icloud_relative_library}")
    return 0


def cmd_name(args) -> int:
    """Print the filename an article would get. Handy for testing the rules."""
    config, registry = _load(args)
    decision = classify(
        Signals(url=args.url or "", title=args.title or ""),
        registry,
        extension=args.extension,
        template=config.template,
        max_title_length=config.max_title_length,
        fallback_acronym=config.fallback_acronym,
        date=datetime.now().strftime("%Y-%m-%d"),
    )
    if args.json:
        print(
            json.dumps(
                {
                    "filename": decision.filename,
                    "acronym": decision.acronym,
                    "title": decision.title,
                    "publication": decision.publication.name if decision.publication else None,
                    "source": decision.source,
                    "notes": decision.notes,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(decision.filename)
    return 0


def cmd_file(args) -> int:
    config, registry = _load(args)
    failures = 0
    for raw in args.paths:
        path = Path(raw).expanduser()
        if not path.is_file():
            print(f"not a file: {path}", file=sys.stderr)
            failures += 1
            continue
        plan = apply_plan(plan_file(path, config, registry), dry_run=args.dry_run)
        print(plan.describe())
    return 1 if failures else 0


def cmd_run(args) -> int:
    config, registry = _load(args)
    plans = process_inbox(config, registry, dry_run=args.dry_run, settle=not args.no_settle)
    if not plans:
        print(f"nothing to file in {config.inbox_path}")
        return 0
    for plan in plans:
        print(plan.describe())
    return 0


def cmd_watch(args) -> int:
    config, registry = _load(args)
    setup_logging(config, verbose=args.verbose)
    watcher = Watcher(config, registry)
    watcher.install_signal_handlers()
    watcher.run()
    return 0


def cmd_publications(args) -> int:
    _, registry = _load(args)
    if args.add:
        acronym, name, *domains = args.add
        registry.add(
            Publication.from_dict({"acronym": acronym, "name": name, "domains": domains,
                                   "title_suffixes": [name]})
        )
        path = user_publications_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"publications": [p.to_dict() for p in registry]}, indent=2,
                       ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"added {acronym} ({name}) and saved {len(registry)} publications to {path}")
        return 0
    if args.export_map:
        print(json.dumps(registry.domain_map(), indent=2, sort_keys=True))
        return 0
    width = max(len(p.acronym) for p in registry)
    for pub in sorted(registry, key=lambda p: p.acronym):
        print(f"{pub.acronym:<{width}}  {pub.name:<34} {', '.join(pub.domains)}")
    return 0


def cmd_config(args) -> int:
    config, _ = _load(args)
    print(json.dumps(config.to_dict(), indent=2))
    return 0


def cmd_doctor(args) -> int:
    config, registry = _load(args)
    problems = 0

    def check(ok: bool, good: str, bad: str) -> None:
        nonlocal problems
        print(f"  {'OK  ' if ok else 'FAIL'}  {good if ok else bad}")
        problems += 0 if ok else 1

    print("article-filer doctor")
    print(f"  version {__version__}, python {sys.version.split()[0]}, {sys.platform}")
    check(config_path().is_file(), f"config at {config_path()}",
          f"no config yet — run: python3 -m articlefiler init")
    check(config.library_path.is_dir(), f"library {config.library_path}",
          f"library missing: {config.library_path}")
    check(config.inbox_path.is_dir(), f"inbox {config.inbox_path}",
          f"inbox missing: {config.inbox_path}")
    icloud = "com~apple~CloudDocs" in str(config.library_path)
    check(icloud, "library is inside iCloud Drive",
          "library is not inside iCloud Drive — it will not sync to your iPhone")
    writable = config.library_path.is_dir() and __import__("os").access(config.library_path, 2)
    check(writable, "library is writable", "library is not writable")
    print(f"  INFO  {len(registry)} publications known")
    print(f"  INFO  Shortcut save path: {config.icloud_relative_library}")
    pending = len(list(config.inbox_path.glob('*'))) if config.inbox_path.is_dir() else 0
    print(f"  INFO  {pending} item(s) waiting in the inbox")
    return 1 if problems else 0


# -- parser -------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="article-filer",
        description="Name newspaper article PDFs '<ACRONYM> - <Title>.pdf' and file them in iCloud.",
    )
    parser.add_argument("--version", action="version", version=f"article-filer {__version__}")
    parser.add_argument("--config", help="path to config.json")
    parser.add_argument("--library", help="override the library folder")
    parser.add_argument("--inbox", help="override the inbox folder")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create the folders and write a config file")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("name", help="show the filename an article would be given")
    p.add_argument("--url", help="the article URL")
    p.add_argument("--title", help="the page title")
    p.add_argument("--extension", default=".pdf")
    p.add_argument("--json", action="store_true", help="print the full decision")
    p.set_defaults(func=cmd_name)

    p = sub.add_parser("file", help="rename and file specific files")
    p.add_argument("paths", nargs="+")
    p.add_argument("-n", "--dry-run", action="store_true")
    p.set_defaults(func=cmd_file)

    p = sub.add_parser("run", help="file everything waiting in the inbox, once")
    p.add_argument("-n", "--dry-run", action="store_true")
    p.add_argument("--no-settle", action="store_true",
                   help="do not wait for files to stop changing")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("watch", help="keep watching the inbox (used by the launch agent)")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("publications", help="list, add or export publications")
    p.add_argument("--add", nargs="+", metavar=("ACRONYM NAME", "DOMAIN"),
                   help="add a publication: --add HBR 'Harvard Business Review' hbr.org")
    p.add_argument("--export-map", action="store_true",
                   help="print a {domain: acronym} map for the iOS Shortcut")
    p.set_defaults(func=cmd_publications)

    p = sub.add_parser("config", help="print the effective configuration")
    p.set_defaults(func=cmd_config)

    p = sub.add_parser("doctor", help="check the setup")
    p.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError) as error:
        print(f"article-filer: {error}", file=sys.stderr)
        return 1
