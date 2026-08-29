#!/usr/bin/env bash
# Sign a generated .shortcut so iOS and macOS will open it.
#
# Unsigned shortcut files are rejected by the Shortcuts app. macOS ships a
# `shortcuts` CLI that signs them; there is no equivalent on iOS, so this step
# has to happen on the Mac. AirDrop the signed file to the iPhone afterwards.
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "sign.sh: signing needs macOS (the 'shortcuts' CLI is macOS-only)." >&2
  exit 2
fi

if ! command -v shortcuts >/dev/null 2>&1; then
  echo "sign.sh: the 'shortcuts' command is missing (needs macOS 12 Monterey or later)." >&2
  exit 2
fi

INPUT="${1:-build/File Article.shortcut}"
OUTPUT="${2:-${INPUT%.shortcut}.signed.shortcut}"

if [[ ! -f "$INPUT" ]]; then
  echo "sign.sh: no such file: $INPUT" >&2
  echo "Generate it first:  python3 shortcut/build_shortcut.py" >&2
  exit 1
fi

# --mode anyone lets the file open on a device that never saw this Mac.
shortcuts sign --mode anyone --input "$INPUT" --output "$OUTPUT"

echo "signed: $OUTPUT"
echo
echo "Next:"
echo "  1. Double-click it here to add the shortcut to this Mac."
echo "  2. AirDrop it to your iPhone, or let iCloud sync carry it across."
echo "  3. On the iPhone: Shortcuts > File Article > (i) > Show in Share Sheet = on."
