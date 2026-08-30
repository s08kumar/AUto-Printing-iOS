#!/usr/bin/env bash
# Install the article filer on this Mac: create the folders, write the config,
# and register a launch agent that watches the inbox in the background.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.articlefiler.watcher"
AGENT_DIR="$HOME/Library/LaunchAgents"
AGENT="$AGENT_DIR/$LABEL.plist"
LOG="$HOME/Library/Logs/article-filer.log"
PYTHON="${PYTHON:-/usr/bin/python3}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "install.sh: this installer is for macOS. On iPhone you only need the Shortcut." >&2
  exit 2
fi

if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "install.sh: need Python 3.9 or newer at $PYTHON (set PYTHON=... to choose another)." >&2
  exit 2
fi

echo "==> Creating folders and config"
(cd "$REPO" && "$PYTHON" -m articlefiler init)

echo "==> Installing the launch agent"
mkdir -p "$AGENT_DIR"
# Substituted in Python, not sed: '&' and '|' are literal there, so a path
# like /Users/me/R&D/... cannot corrupt the plist.
TEMPLATE="$REPO/mac/com.articlefiler.watcher.plist.template" \
AGENT_OUT="$AGENT" PY_BIN="$PYTHON" REPO_DIR="$REPO" LOG_FILE="$LOG" \
"$PYTHON" - <<'PYEOF'
import os
from pathlib import Path
from xml.sax.saxutils import escape

text = Path(os.environ["TEMPLATE"]).read_text(encoding="utf-8")
for token, value in (
    ("__PYTHON__", os.environ["PY_BIN"]),
    ("__REPO__", os.environ["REPO_DIR"]),
    ("__LOG__", os.environ["LOG_FILE"]),
):
    text = text.replace(token, escape(value))  # these land inside XML elements
Path(os.environ["AGENT_OUT"]).write_text(text, encoding="utf-8")
PYEOF

# bootout is noisy the first time round; an existing agent must go before a reload.
launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$AGENT"
launchctl enable "gui/$UID/$LABEL"

echo "==> Checking"
(cd "$REPO" && "$PYTHON" -m articlefiler doctor) || true

# iCloud Drive is behind Full Disk Access. Without it the watcher runs happily
# and files nothing, so check now rather than leaving it to be discovered.
if ! (cd "$REPO" && "$PYTHON" -c '
import sys
from articlefiler.access import check_readable
from articlefiler.config import Config
problem = check_readable(Config.load().inbox_path)
sys.exit(1 if problem and "permission denied" in problem else 0)
'); then
  echo
  echo "############################################################"
  echo "  ACTION NEEDED: grant Full Disk Access before this works"
  echo "############################################################"
  (cd "$REPO" && "$PYTHON" -c 'from articlefiler.access import FULL_DISK_ACCESS_HELP; print(FULL_DISK_ACCESS_HELP)')
  echo
fi

cat <<EOF

Installed. The watcher now runs at login and files anything dropped into the
inbox folder.

  status : launchctl print gui/$UID/$LABEL | head -20
  log    : tail -f "$LOG"
  remove : $REPO/mac/uninstall.sh

If the check above asked for Full Disk Access, do that first — the watcher
cannot read iCloud Drive without it, and it fails silently.
EOF
