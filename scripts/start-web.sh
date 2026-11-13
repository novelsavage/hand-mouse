#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"
if [[ ! -d node_modules ]]; then
  npm ci
fi
if [[ ! -f web/tracking-worker.js ]] || [[ web/tracking-worker-source.js -nt web/tracking-worker.js ]] || [[ package-lock.json -nt web/tracking-worker.js ]]; then
  npm run build
fi
exec uv run python web_server.py "$@"
