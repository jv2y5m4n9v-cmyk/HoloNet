#!/usr/bin/env sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ ! -x "$ROOT/venv/bin/python" ]; then
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' || {
    echo "Python 3.12 or newer is required." >&2
    exit 1
  }
  python3 -m venv "$ROOT/venv"
fi
"$ROOT/venv/bin/python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' || {
  echo "The venv must use Python 3.12 or newer." >&2
  exit 1
}
exec "$ROOT/venv/bin/python" "$ROOT/app.py" "$@"
