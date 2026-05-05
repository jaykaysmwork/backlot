#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="/app/capture_output"
SAMPLE_DIR="/app/sample_data"

# Check if capture_output has any real session data
has_real_data=false
if find "$DATA_DIR" -name "session.json" -not -type l -print -quit 2>/dev/null | grep -q .; then
  has_real_data=true
fi

# Only symlink sample_data when capture_output has no real sessions
if [ "$has_real_data" = false ] && [ -d "$SAMPLE_DIR" ]; then
  for project in "$SAMPLE_DIR"/*/; do
    [ -d "$project" ] || continue
    pname="$(basename "$project")"
    for session in "$project"/*/; do
      [ -d "$session" ] || continue
      sname="$(basename "$session")"
      target="$DATA_DIR/$pname/$sname"
      if [ ! -e "$target" ]; then
        mkdir -p "$DATA_DIR/$pname"
        ln -s "$session" "$target"
      fi
    done
  done
fi

export CAPTURE_OUTPUT_DIR="$DATA_DIR"

exec "$@"
