#!/usr/bin/env bash
# Remove the launch agent. Your filed articles and config are left alone.
set -euo pipefail

LABEL="com.articlefiler.watcher"
AGENT="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
rm -f "$AGENT"

echo "Removed the launch agent."
echo "Left in place: your articles, ~/.config/article-filer/, and the log."
