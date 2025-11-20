#!/usr/bin/env bash
# Starts backend dev server with reload watching only the backend directory
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source ./ag/bin/activate
# Use --reload-dir to limit file watch to the backend code only (avoid watching 'projects/' artifacts)
python -m uvicorn backend.api:app --port 8000 --log-level info --reload --reload-dir backend
