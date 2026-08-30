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
if ! shortcuts sign --mode anyone --input "$INPUT" --output "$OUTPUT"; then
  echo >&2
  echo "sign.sh: signing failed." >&2
  echo "  Older macOS wants the short flags instead. Try:" >&2
  echo "    shortcuts sign -m anyone -i '$INPUT' -o '$OUTPUT'" >&2
  exit 1
fi

# Signing can exit 0 without producing anything; say so rather than
# sending you off to look for a file that was never written.
if [[ ! -s "$OUTPUT" ]]; then
  echo "sign.sh: signing reported success but produced no file at:" >&2
  echo "  $OUTPUT" >&2
  exit 1
fi

ABS="$(cd "$(dirname "$OUTPUT")" && pwd)/$(basename "$OUTPUT")"
echo "signed: $ABS  ($(du -h "$ABS" | cut -f1))"
echo
echo "Next:"
echo "  1. Add it to this Mac:      open '$ABS'"
echo "  2. Reveal it in Finder:     open -R '$ABS'"
echo "     (build/ is easy to miss — it is inside the repo, not in Downloads.)"
echo "  3. AirDrop it to the iPhone, or let iCloud sync carry it across."
echo "  4. On the iPhone: Shortcuts > File Article > (i) > Show in Share Sheet = on."
echo "  5. On the Mac: Shortcuts > File Article > (i) > Use as Quick Action >"
echo "     Services Menu, so it appears in Safari's Share menu and Finder."
