"""Command line interface: `python3 -m articlefiler <command>`."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .access import (
    FULL_DISK_ACCESS_HELP,
    access_error_message,
    check_readable,
)
from .classify import Signals, classify
from .config import Config, INBOX_NAME, SUBFOLDER_MODES, config_path, user_publications_path
from .filer import AccessDenied, apply_plan, plan_file, process_inbox
from .publications import Publication, PublicationRegistry, load_default_registry
from .render import check_environment as render_check
from .render import render_url
from .verify import inspect, inspect_folder
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

    # The Save File action resolves its subpath against iCloud Drive/Shortcuts.
    # If that folder is absent — never created, or deleted — the save writes
    # nowhere and reports nothing, so create the landing zone up front.
    created: list[Path] = []
    for landing in config.shortcuts_inbox_paths:
        if not landing.exists():
            try:
                landing.mkdir(parents=True, exist_ok=True)
                created.append(landing)
            except OSError as error:
                print(f"could not create {landing}: {error}", file=sys.stderr)

    path = config.save(Path(args.config).expanduser() if args.config else None)
    print(f"library : {config.library_path}")
    print(f"inbox   : {config.inbox_path}")
    for landing in config.shortcuts_inbox_paths:
        note = "  (created)" if landing in created else ""
        print(f"landing : {landing}{note}")
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
        print("nothing to file. Watched folders:")
        for inbox in config.inbox_paths:
            state = "" if inbox.is_dir() else "   (does not exist)"
            print(f"  {inbox}{state}")
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


def cmd_locate(args) -> int:
    """Find recently-saved documents that are not in the library.

    When a Shortcut reports success but nothing appears where you expected,
    the file is rarely lost — it is in whatever folder the Save File action
    actually resolved to. This looks in the handful of places that can be.
    """
    from .config import ICLOUD_ROOT

    config, _ = _load(args)
    library = config.library_path
    cutoff = datetime.now().timestamp() - args.hours * 3600

    roots = [
        ICLOUD_ROOT,
        Path.home() / "Downloads",
        Path.home() / "Desktop",
        Path.home() / "Library/Mobile Documents/iCloud~is~workflow~my~workflows/Documents",
    ]

    found: list[tuple[float, Path]] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in config.extensions:
                continue
            if path in seen:
                continue
            seen.add(path)
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff:
                continue
            if library in path.parents:
                continue
            found.append((mtime, path))

    if not found:
        print(f"no documents saved outside the library in the last {args.hours}h")
        print(f"searched: {', '.join(str(r) for r in roots if r.is_dir())}")
        return 0

    found.sort(reverse=True)
    print(f"{len(found)} document(s) saved outside the library in the last {args.hours}h:")
    print(f"(library is {library})")
    for mtime, path in found[: args.limit]:
        when = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {when}  {path}")
    if len(found) > args.limit:
        print(f"  ... and {len(found) - args.limit} more")
    print()
    print("To file them:")
    print("  python3 -m articlefiler file '<path>'")
    return 0


def cmd_verify(args) -> int:
    """Report which filed PDFs look like paywall captures rather than articles."""
    config, _ = _load(args)
    if args.paths:
        reports = [inspect(Path(p).expanduser()) for p in args.paths]
    else:
        def progress(index: int, total: int, path: Path) -> None:
            # Overwritten in place, then cleared, so a slow scan never looks
            # like a hang.
            print(f"\r  reading {index}/{total}: {path.name[:50]:<50}",
                  end="", flush=True)

        reports = inspect_folder(config.library_path, limit=args.limit, progress=progress)
        print("\r" + " " * 72 + "\r", end="")

    if not reports:
        print(f"no PDFs found in {config.library_path}")
        return 0

    suspect = [r for r in reports if r.suspicious]
    width = min(58, max(len(r.path.name) for r in reports))
    print(f"{'file':<{width}}  {'pages':>5} {'text':>7} {'size':>8}  verdict")
    print("-" * (width + 34))
    for report in reports:
        if args.suspect_only and not report.suspicious:
            continue
        name = report.path.name
        name = name if len(name) <= width else name[: width - 1] + "…"
        print(
            f"{name:<{width}}  {report.pages:>5} {report.text_chars:>7} "
            f"{report.size / 1000:>7.0f}k  {report.verdict}"
        )
        for reason in report.reasons:
            print(f"{'':<{width}}    - {reason}")
        for note in report.notes:
            if args.suspect_only or report.suspicious:
                print(f"{'':<{width}}    ({note})")

    print()
    print(f"{len(reports)} checked, {len(suspect)} worth a look.")
    if suspect:
        print()
        print("A suspect file is usually the paywall rather than the article.")
        print("Re-file those from Safari, or from screenshots — see docs/PAYWALLS.md.")
    return 0


def cmd_render(args) -> int:
    """Render a URL to PDF through Safari, and file it."""
    config, registry = _load(args)

    problems = render_check()
    if problems:
        from .render import ACCESSIBILITY_HELP

        print(f"cannot render: {problems[0]}", file=sys.stderr)
        if "Accessibility" in problems[0]:
            print(file=sys.stderr)
            print(ACCESSIBILITY_HELP, file=sys.stderr)
        return 2

    failures = 0
    for url in args.urls:
        print(f"rendering {url}")
        result = render_url(url, config.inbox_path, timeout=args.timeout)
        if not result.ok:
            print(f"  failed: {result.error}", file=sys.stderr)
            failures += 1
            continue
        print(f"  captured: {result.path.name}")
        plan = apply_plan(plan_file(result.path, config, registry))
        print(f"  {plan.describe()}")
    return 1 if failures else 0


def cmd_explain(args) -> int:
    """Show every signal a file offers, and how the name was decided.

    When a file comes out named wrongly, the question is always which signals
    were actually present. This answers it rather than inviting speculation.
    """
    from .filer import gather_signals
    from .pdfmeta import read_pdf_metadata, read_spotlight_metadata

    config, registry = _load(args)

    paths = [Path(p).expanduser() for p in args.paths]
    if not paths:
        # No argument: the most recent files, wherever they landed. Saves
        # spelling out a path with spaces in it, or fighting a shell glob.
        candidates: list[Path] = []
        for folder in [config.library_path, *config.inbox_paths]:
            if not folder.is_dir():
                continue
            try:
                candidates.extend(p for p in folder.glob("*") if p.is_file())
            except OSError:
                continue
        candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
        paths = [p for p in candidates if p.suffix.lower() in config.extensions][: args.recent]
        if not paths:
            print("no documents found in:")
            for folder in [config.library_path, *config.inbox_paths]:
                print(f"  {folder}{'' if folder.is_dir() else '   (does not exist)'}")
            return 0
        print(f"most recent {len(paths)} document(s):\n")

    for path in paths:
        print(f"=== {path.name}")
        if not path.is_file():
            print("  not a file")
            continue
        print(f"  size: {path.stat().st_size:,} bytes")

        if path.suffix.lower() == ".pdf":
            meta = read_pdf_metadata(path)
            print(f"  PDF /Title    : {meta.title or '(none)'}")
            print(f"  PDF /Subject  : {meta.subject or '(none)'}")
            print(f"  PDF /Keywords : {meta.keywords or '(none)'}")
            if meta.urls:
                print(f"  URLs found    : {len(meta.urls)}")
                for url in meta.urls[:8]:
                    print(f"      {url[:100]}")
            else:
                print("  URLs found    : (none)")
            spotlight = read_spotlight_metadata(path)
            if spotlight.title or spotlight.urls:
                print(f"  Spotlight     : title={spotlight.title or '(none)'} "
                      f"urls={list(spotlight.urls[:3]) or '(none)'}")

        signals = gather_signals(path, config)
        print(f"  filename stem : {signals.filename_stem}")
        print(f"  candidates    : {signals.candidate_titles() or '(none usable)'}")

        decision = classify(
            signals, registry,
            extension=path.suffix.lower(),
            template=config.template,
            max_title_length=config.max_title_length,
            fallback_acronym=config.fallback_acronym,
        )
        print(f"  -> publication: {decision.publication.name if decision.publication else '(unknown)'}")
        print(f"  -> decided by : {decision.source}")
        print(f"  -> filename   : {decision.filename}")
        for note in decision.notes:
            print(f"     note: {note}")
        if decision.source == "unknown":
            print()
            print("  Nothing in this PDF names the article. Make PDF produces a file")
            print("  with no title and no metadata, so the Shortcut has to supply the")
            print("  name — add a Set Name action before Save File.")
    return 0


def cmd_selftest(args) -> int:
    """Prove the Mac half end to end, with a real file, and clean up after.

    Every step that has bitten us in setup gets checked here in order, so a
    failure names the link that broke rather than leaving it to be inferred.
    """
    config, registry = _load(args)
    steps: list[tuple[str, bool, str]] = []

    def step(name: str, ok: bool, detail: str = "") -> bool:
        steps.append((name, ok, detail))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
        return ok

    print("article-filer self-test")
    print(f"  library: {config.library_path}")
    print()

    if not step("library folder exists", config.library_path.is_dir(),
                "" if config.library_path.is_dir() else "run: articlefiler init"):
        return 1
    if not step("inbox folder exists", config.inbox_path.is_dir(),
                "" if config.inbox_path.is_dir() else "run: articlefiler init"):
        return 1

    problem = check_readable(config.inbox_path)
    if not step("inbox is readable", problem is None, problem or ""):
        print()
        print(FULL_DISK_ACCESS_HELP)
        return 1

    # Only the iPhone needs this, so it must not fail a Mac-only self-test.
    landing = [p for p in config.shortcuts_inbox_paths if p.is_dir()]
    print(f"  {'INFO'}  iCloud Drive/Shortcuts landing folder: "
          + ("present" if landing else "absent — only matters once the iPhone saves here"))

    # A real file, through the real code path, with a name that exercises the
    # publication lookup and the headline clean-up.
    probe = config.inbox_path / "Self test- a headline with punctuation - WSJ.pdf"
    expected = "WSJ - Self test- a headline with punctuation.pdf"
    try:
        probe.write_bytes(
            b"%PDF-1.7\n1 0 obj\n<< /Title (Self test) >>\nendobj\n"
            b"trailer\n<< /Info 1 0 R >>\n%%EOF\n"
        )
    except OSError as error:
        step("can write to the inbox", False, str(error))
        return 1
    step("can write to the inbox", True)

    try:
        plans = process_inbox(config, registry, settle=False)
    except Exception as error:  # noqa: BLE001 - report rather than traceback
        step("filing runs without error", False, str(error))
        probe.unlink(missing_ok=True)
        return 1
    step("filing runs without error", True)

    filed = config.library_path / expected
    ok = filed.is_file()
    step(f"filed as {expected}", ok,
         "" if ok else f"got: {[p.destination.name for p in plans] or 'nothing'}")

    step("inbox was emptied", not probe.exists())

    # Leave no trace: this is a test, not a filing.
    filed.unlink(missing_ok=True)
    probe.unlink(missing_ok=True)

    failures = [name for name, passed, _ in steps if not passed]
    print()
    if failures:
        print(f"{len(failures)} step(s) failed: {', '.join(failures)}")
        return 1
    print("All good. The Mac side works: drop a PDF in the inbox and it gets")
    print("named and filed. Next, prove it with a real article —")
    print("  Safari > File > Export as PDF > save into:")
    print(f"    {config.inbox_path}")
    print("  then: python3 -m articlefiler run --no-settle && python3 -m articlefiler verify")
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
    for extra in config.inbox_paths[1:]:
        state = "exists" if extra.is_dir() else "not created yet"
        print(f"  INFO  also watching: {extra}  ({state})")
    if not any(p.is_dir() for p in config.shortcuts_inbox_paths):
        print("  WARN  the iCloud Drive/Shortcuts landing folder does not exist.")
        print("        Save File resolves its subpath against it, so saves from")
        print("        the iPhone go nowhere and report nothing. Recreate it with:")
        print("          python3 -m articlefiler init")
    icloud = "com~apple~CloudDocs" in str(config.library_path)
    check(icloud, "library is inside iCloud Drive",
          "library is not inside iCloud Drive — it will not sync to your iPhone")
    writable = config.library_path.is_dir() and __import__("os").access(config.library_path, 2)
    check(writable, "library is writable", "library is not writable")

    # Existence is not access: macOS lets you see the folder and still refuses
    # to list it, which is the single most common reason nothing gets filed.
    denied = False
    for label, folder in (("library", config.library_path), ("inbox", config.inbox_path)):
        problem = check_readable(folder)
        readable = problem is None or "does not exist" in problem
        check(readable, f"{label} is readable", f"cannot read the {label}: {problem}")
        denied = denied or (problem is not None and "permission denied" in problem)
    render_problems = render_check()
    if render_problems:
        print(f"  INFO  URL rendering: unavailable — {render_problems[0]}")
    else:
        print("  INFO  URL rendering: ready (Safari)")
    print(f"  INFO  {len(registry)} publications known")
    print(f"  INFO  Shortcut save path: {config.icloud_relative_library}")
    try:
        pending = len(list(config.inbox_path.glob("*"))) if config.inbox_path.is_dir() else 0
        print(f"  INFO  {pending} item(s) waiting in the inbox")
    except PermissionError:
        print("  INFO  cannot count the inbox — see below")
    if denied:
        print()
        print(FULL_DISK_ACCESS_HELP)
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

    p = sub.add_parser("verify", help="check filed PDFs for paywall captures")
    p.add_argument("paths", nargs="*", help="specific files (default: the library)")
    p.add_argument("--limit", type=int, default=40, help="how many recent files to check")
    p.add_argument("--suspect-only", action="store_true", help="hide the healthy ones")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("locate", help="find documents saved outside the library")
    p.add_argument("--hours", type=float, default=24, help="how far back to look")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(func=cmd_locate)

    p = sub.add_parser("render", help="render a URL to PDF via Safari, then file it")
    p.add_argument("urls", nargs="+")
    p.add_argument("--timeout", type=float, default=45.0,
                   help="seconds to wait for the page to load")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("explain", help="show what signals a file offers, and why")
    p.add_argument("paths", nargs="*", help="defaults to the most recent documents")
    p.add_argument("--recent", type=int, default=3,
                   help="how many recent documents to explain when none are named")
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("selftest", help="prove the Mac side works, end to end")
    p.set_defaults(func=cmd_selftest)

    p = sub.add_parser("doctor", help="check the setup")
    p.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except AccessDenied as error:
        print(access_error_message(Path(str(error).split(": ", 1)[-1]), str(error)),
              file=sys.stderr)
        return 2
    except PermissionError as error:
        path = Path(getattr(error, "filename", "") or ".")
        print(access_error_message(path, f"permission denied: {path}"), file=sys.stderr)
        return 2
    except (ValueError, OSError) as error:
        print(f"article-filer: {error}", file=sys.stderr)
        return 1
