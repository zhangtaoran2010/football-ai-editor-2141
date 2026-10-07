#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
PYTHONPATH="$ROOT/src" exec python3 -m football_ai_editor.cli doctor "$@"
