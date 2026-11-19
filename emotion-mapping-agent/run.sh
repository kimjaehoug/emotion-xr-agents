#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo ".env 파일이 생성되었습니다. LLM_API_KEY를 설정해주세요."
fi

python3 -m uvicorn main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8080}" --reload
