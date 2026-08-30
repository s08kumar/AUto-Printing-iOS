#!/usr/bin/env bash
# Collect what's needed to diagnose an install, in one pasteable report.
#
# Prints only this project's own state: whether the Shortcut is installed, what
# the launch agent is doing, and how the filer is configured. It does NOT dump
# your other shortcuts, and it does not print the contents of any article.
#
#   ./mac/diagnose.sh            # this project only
#   ./mac/diagnose.sh --all      # also list every shortcut name you have
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.articlefiler.watcher"
PYTHON="${PYTHON:-/usr/bin/python3}"
SHOW_ALL="${1:-}"

rule() { printf '\n=== %s ===\n' "$1"; }

echo "article-filer diagnostics — $(date '+%Y-%m-%d %H:%M')"
echo "macOS $(sw_vers -productVersion 2>/dev/null || echo '?'), $(uname -m)"
echo "repo: $REPO @ $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo 'not a git checkout')"

rule "Is the Shortcut installed?"
if command -v shortcuts >/dev/null 2>&1; then
  if [[ "$SHOW_ALL" == "--all" ]]; then
    shortcuts list
  else
    # Only ours, so a paste never leaks the names of unrelated shortcuts.
    shortcuts list 2>/dev/null | grep -i -e 'article' -e 'file article' \
      || echo "no shortcut with 'article' in its name is installed"
  fi
else
  echo "the 'shortcuts' CLI is missing (needs macOS 12 or later)"
fi

rule "Shortcuts app storage"
# Sizes and dates only — the store is a database, not readable text.
ls -lh ~/Library/Shortcuts/ 2>/dev/null || echo "~/Library/Shortcuts does not exist"

rule "Launch agent"
if launchctl print "gui/$UID/$LABEL" >/dev/null 2>&1; then
  launchctl print "gui/$UID/$LABEL" | grep -E '^\s*(state|pid|last exit code|program|path) ' \
    || echo "loaded, but no state lines matched"
else
  echo "not loaded"
fi
ls -l ~/Library/LaunchAgents/"$LABEL".plist 2>/dev/null || echo "no launch agent plist installed"

rule "Filer doctor"
(cd "$REPO" && "$PYTHON" -m articlefiler doctor 2>&1)

rule "Config"
cat ~/.config/article-filer/config.json 2>/dev/null || echo "no config file yet"

rule "Folder state"
LIB="$(cd "$REPO" && "$PYTHON" -c 'from articlefiler.config import Config; print(Config.load().library_path)' 2>/dev/null)"
if [[ -n "$LIB" && -d "$LIB" ]]; then
  echo "library: $LIB"
  echo "  $(find "$LIB" -maxdepth 1 -type f | wc -l | tr -d ' ') filed article(s)"
  echo "  $(find "$LIB/_Inbox" -maxdepth 1 -type f 2>/dev/null | wc -l | tr -d ' ') item(s) in the inbox"
  echo "  most recent filenames (these are article titles — omit if you'd rather not share):"
  ls -t "$LIB" 2>/dev/null | grep -v '^_Inbox$' | head -5 | sed 's/^/    /'
else
  echo "library folder not found"
fi

rule "Recent log"
tail -n 25 ~/Library/Logs/article-filer.log 2>/dev/null || echo "no log yet"

echo
echo "--- end of report ---"
