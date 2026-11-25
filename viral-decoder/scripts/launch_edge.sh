#!/usr/bin/env bash
# Launch a dedicated Edge instance with a remote-debugging port for CDP scraping.
# MUST be run with run_in_background=true so the process persists after the shell exits.
# Usage (from WorkBuddy Bash tool, run_in_background=true):
#   bash launch_edge.sh [port] [profile_dir]
PORT="${1:-9223}"
PROFILE="${2:-./_edge_profile}"
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
[ -f "$EDGE" ] || EDGE="/c/Program Files/Microsoft/Edge/Application/msedge.exe"
mkdir -p "$PROFILE"
echo "Launching Edge CDP on port $PORT, profile $PROFILE"
exec "$EDGE" --remote-debugging-port="$PORT" --user-data-dir="$(cygpath -w "$PROFILE" 2>/dev/null || echo "$PROFILE")" \
  --no-first-run --no-default-browser-check "about:blank"
