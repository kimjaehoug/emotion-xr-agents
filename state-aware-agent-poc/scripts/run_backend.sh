#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  python3.11 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi
mkdir -p data
# 프로젝트 루트 .env 로드를 위해 cwd를 backend로 두고 DATABASE_URL은 상대경로
export $(grep -v '^#' "$ROOT/.env" | xargs) 2>/dev/null || true
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
