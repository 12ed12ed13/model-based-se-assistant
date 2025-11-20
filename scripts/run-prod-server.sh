#!/usr/bin/env bash
# Starts backend server without reload (suitable for running background workflows)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
source ./ag/bin/activate
python -m uvicorn backend.api:app --port 8000 --log-level info
