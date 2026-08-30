#!/usr/bin/env bash
# Give Safari's "Export as PDF…" menu item a keyboard shortcut.
#
# Shortcuts' Make PDF action renders a live page and can stall indefinitely on
# a heavy news site. Safari's own export does not: the page is already
# rendered, and it is what produced every article filed so far. This makes it
# a keystroke instead of a menu dive.
#
# Default: Cmd-Shift-P. Pass another in Apple's notation to override,
# e.g. '@~p' for Cmd-Option-P  (@ = Cmd, ~ = Option, $ = Shift, ^ = Control)
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "safari-pdf-hotkey.sh: macOS only." >&2
  exit 2
fi

KEY="${1:-@\$p}"
# The ellipsis is a single character (U+2026), not three dots. macOS matches
# the menu title exactly, so this has to be right or nothing happens.
ITEM="Export as PDF…"

defaults write com.apple.Safari NSUserKeyEquivalents -dict-add "$ITEM" "$KEY"

cat <<EOF
Set "$ITEM" to $KEY in Safari.

Quit and reopen Safari, then check the File menu — the shortcut should be
shown next to "Export as PDF…". If it is not, set it by hand instead:

  System Settings > Keyboard > Keyboard Shortcuts > App Shortcuts > +
    Application: Safari
    Menu Title:  Export as PDF…      (copy this line, ellipsis included)
    Shortcut:    whatever you like

To undo:
  defaults delete com.apple.Safari NSUserKeyEquivalents
EOF
