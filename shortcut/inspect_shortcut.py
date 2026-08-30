#!/usr/bin/env python3
"""Decode a shortcut and print its actions in readable form.

Accepts an iCloud share link, a downloaded .shortcut file, or a directory of
them:

    python3 shortcut/inspect_shortcut.py https://www.icloud.com/shortcuts/<id>
    python3 shortcut/inspect_shortcut.py ~/Downloads/'File Article.shortcut'

Shortcuts that came from iCloud or from `shortcuts sign` are wrapped in an
Apple Encrypted Archive. Unwrapping needs the macOS `aea` tool, so on other
platforms this reports what it found rather than guessing.
"""

from __future__ import annotations

import argparse
import json
import plistlib
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

TOKEN = "￼"
AEA_MAGIC = b"AEA1"
ICLOUD_LINK = re.compile(r"icloud\.com/shortcuts/(?:api/records/)?([0-9a-fA-F]{16,})")


# -- acquiring the bytes ------------------------------------------------


def download_icloud(url: str) -> bytes:
    """Resolve an iCloud share link to the shortcut file it points at."""
    match = ICLOUD_LINK.search(url)
    if not match:
        raise ValueError(f"not an iCloud shortcut link: {url}")
    record_url = f"https://www.icloud.com/shortcuts/api/records/{match.group(1)}"
    with urllib.request.urlopen(record_url, timeout=30) as response:
        record = json.load(response)
    try:
        download_url = record["fields"]["shortcut"]["value"]["downloadURL"]
    except (KeyError, TypeError) as error:
        raise ValueError(f"unexpected record shape from iCloud: {error}") from error
    name = record.get("fields", {}).get("name", {}).get("value", "(unnamed)")
    print(f"iCloud record: {name}")
    with urllib.request.urlopen(download_url, timeout=60) as response:
        return response.read()


def load_bytes(source: str) -> bytes:
    if source.startswith(("http://", "https://")):
        return download_icloud(source)
    return Path(source).expanduser().read_bytes()


# -- unwrapping ---------------------------------------------------------


def unwrap(data: bytes) -> dict:
    """Return the workflow dictionary, decrypting the AEA wrapper if needed."""
    if not data.startswith(AEA_MAGIC):
        return plistlib.loads(data)

    if sys.platform != "darwin":
        raise SystemExit(
            "This shortcut is an Apple Encrypted Archive (signed).\n"
            "Unwrapping it needs the macOS `aea` tool — run this script on the Mac."
        )
    with tempfile.TemporaryDirectory() as tmp:
        packed = Path(tmp) / "in.aea"
        packed.write_bytes(data)
        unpacked = Path(tmp) / "out"
        result = subprocess.run(
            ["aea", "decrypt", "-i", str(packed), "-o", str(unpacked)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not unpacked.exists():
            raise SystemExit(
                "Could not decrypt the signed shortcut.\n"
                f"aea said: {(result.stderr or result.stdout).strip() or '(nothing)'}\n"
                "Open it in the Shortcuts app instead and read the Save File action."
            )
        blob = unpacked.read_bytes() if unpacked.is_file() else b""
        if not blob:
            for candidate in sorted(unpacked.rglob("*")):
                if candidate.is_file():
                    blob = candidate.read_bytes()
                    break
        return plistlib.loads(blob)


# -- rendering ----------------------------------------------------------


def render(value) -> str:
    if isinstance(value, dict):
        kind = value.get("WFSerializationType")
        if kind == "WFTextTokenString":
            inner = value["Value"]
            text, attachments = inner["string"], inner.get("attachmentsByRange", {})
            spans = sorted(
                (int(k.strip("{}").split(",")[0]), a) for k, a in attachments.items()
            )
            out, last = "", 0
            for offset, attachment in spans:
                out += text[last:offset]
                out += "[" + (attachment.get("VariableName")
                              or attachment.get("Type", "?")) + "]"
                last = offset + 1
            return out + text[last:]
        if kind == "WFTextTokenAttachment":
            inner = value["Value"]
            return "[" + (inner.get("VariableName") or inner.get("Type", "?")) + "]"
        if kind == "WFDictionaryFieldValue":
            return f"<{len(value['Value']['WFDictionaryFieldValueItems'])} rows>"
    return repr(value)


def describe(workflow: dict, focus: str | None = None) -> None:
    actions = workflow.get("WFWorkflowActions", [])
    print(f"actions               : {len(actions)}")
    print(f"WFWorkflowTypes       : {workflow.get('WFWorkflowTypes')}")
    print(f"WFQuickActionSurfaces : {workflow.get('WFQuickActionSurfaces', '(none)')}")
    print(f"input content classes : {len(workflow.get('WFWorkflowInputContentItemClasses', []))}")
    print("-" * 72)
    for index, action in enumerate(actions, 1):
        identifier = action.get("WFWorkflowActionIdentifier", "?")
        if focus and focus not in identifier:
            continue
        short = identifier.replace("is.workflow.actions.", "")
        parameters = action.get("WFWorkflowActionParameters", {})
        if short == "setvariable":
            print(f"{index:>3}. Set Variable -> {parameters.get('WFVariableName')}")
            continue
        print(f"{index:>3}. {short}")
        for key, value in sorted(parameters.items()):
            print(f"       {key}: {render(value)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", help="iCloud link or path to a .shortcut file")
    parser.add_argument("--save", help="also write the decoded plist here")
    parser.add_argument(
        "--only",
        help="show only actions whose identifier contains this, e.g. 'save'",
    )
    args = parser.parse_args(argv)

    workflow = unwrap(load_bytes(args.source))
    describe(workflow, focus=args.only)
    if args.save:
        Path(args.save).write_bytes(plistlib.dumps(workflow, fmt=plistlib.FMT_XML))
        print(f"\nwrote {args.save}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
