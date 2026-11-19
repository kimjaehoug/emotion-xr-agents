# XR Control AI Agent PoC

상태 인지 AI Agent가 생성한 **State Report**를 입력받아, 로컬 **Qwen3.5-9B**로 대응 계획을 만들고,  
등록된 **Response Policy / Action Catalog / Content** 범위 안에서만 검증·실행하는 연구용 PoC입니다.

> 의료 진단·치료 권고가 아닙니다. 실제 HMD 제어 대신 **Mock XR Runtime**을 사용합니다.

관련 프로젝트: [`state-aware-agent-poc`](../state-aware-agent-poc) (상태 인지 Agent)

---

## 아키텍처

```
State Cognition Agent
        ↓ State Report JSON
FastAPI XR Control Agent (:8001)
        ↓ OpenAI-compatible HTTP
Local Qwen3.5-9B Inference Server (:8080 또는 Ollama :11434/v1)
        ↓ Action Plan JSON
Plan Validator (Schema / Policy / Action / Content / Safety)
        ↓
Action Router → Content Ranker / Mock XR Runtime
        ↓
XR Episodic · Summary Memory (SQLite)
```

Qwen 결과는 **그대로 실행하지 않습니다.** 검증 실패 시 1회 Repair → 재실패 시 **RuleBasedFallbackPlanner**.

---

## 설치

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # 필요 시 수정
```

```bash
cd frontend
npm install
```

---

## 로컬 Qwen3.5-9B 준비

### 옵션 A — llama.cpp `llama-server` (요구사항 기본: :8080)

```bash
llama-server \
  -m /path/to/qwen3.5-9b.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -c 4096
```

`.env`:

```
LOCAL_LLM_BASE_URL=http://localhost:8080/v1
LOCAL_LLM_MODEL=qwen3.5-9b
LOCAL_LLM_API_KEY=local
```

### 옵션 B — Ollama OpenAI 호환 API (이 Mac에서 검증됨)

```bash
ollama serve
ollama pull qwen3.5:9b
```

`.env` 예시 (16GB RAM → ctx 절약):

```
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_MODEL=qwen3.5:9b
LOCAL_LLM_API_KEY=local
LOCAL_LLM_TIMEOUT_SEC=120
LOCAL_LLM_JSON_SCHEMA_ENABLED=false
```

> Ollama는 `json_schema`를 지원하지 않을 수 있습니다. 클라이언트는 자동으로 스키마 없이 재시도하고 JSON을 파싱합니다.

---

## 실행

```bash
# Backend (포트 8001 — 상태 인지 Agent 8000과 분리)
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

# Frontend (포트 5174)
cd frontend && npm run dev
```

또는:

```bash
./scripts/run_backend.sh
./scripts/run_frontend.sh
```

- UI: http://127.0.0.1:5174  
- API docs: http://127.0.0.1:8001/docs  
- LLM health: `GET /api/v1/xr-agent/health/llm`

첫 화면에서 **데모 시드**를 실행하세요.

---

## 상태 인지 Agent 연동

1. State Agent `:8000`에서 `POST /api/v1/state/analyze` → State Report JSON 확보  
2. XR Agent `:8001`에 `POST /api/v1/xr-agent/plan` 또는 `/execute`로 전달  
3. 공유 스키마: `shared/state_report.py` (및 `backend/app/schemas/state_report.py`)  
4. users 테이블 재사용(선택): `STATE_AGENT_DATABASE_URL`을 State Agent SQLite로 지정 가능  
5. `emotion_context` / `candidate_causes`는 XR Agent에서 선택 수용

---

## API 예시

### LLM Health

```bash
curl http://127.0.0.1:8001/api/v1/xr-agent/health/llm
```

### Plan 생성 (실행 없음)

```bash
curl -X POST http://127.0.0.1:8001/api/v1/xr-agent/plan \
  -H 'Content-Type: application/json' \
  -d @examples/state_report_action_required.json
```

### Plan + Mock 실행

```bash
curl -X POST http://127.0.0.1:8001/api/v1/xr-agent/execute \
  -H 'Content-Type: application/json' \
  -d '{"plan_id":"AP-..."}'
```

---

## Fallback 동작

| 상황 | 결과 |
|------|------|
| LLM 연결 실패 / timeout | `rule_based_fallback` |
| JSON 파싱 실패 | Repair 1회 → 실패 시 fallback |
| 미등록 Policy/Action/Content | 차단 → repair/fallback |
| UNKNOWN / 낮은 confidence | `CONTINUE_OBSERVATION` (LLM 미호출 가능) |
| NORMAL + requires_response=false | `KEEP_CURRENT` / NO_ACTION |

응답 메타: `planner_source`, `fallback_reason`, `llm_latency_ms`, `repair_attempted`, `validation_status`

---

## 테스트

```bash
cd backend && source .venv/bin/activate
pytest -v
```

실제 로컬 LLM 통합 테스트:

```bash
RUN_LOCAL_LLM_TESTS=true pytest -v -k local_llm
```

(기본 테스트는 MockTransport만 사용)

---

## 실제 XR 엔진 교체 지점

| 인터페이스 | 파일 | 교체 방법 |
|------------|------|-----------|
| `MockXrRuntime` | `services/mock_xr_runtime.py` | 동일 메서드 시그니처로 실제 SDK 어댑터 |
| Action Catalog | DB `action_catalog` | 엔진이 지원하는 파라미터만 등록 |
| Content Ranker | `services/content_ranker.py` | 점수식/카탈로그 소스 교체 |

---

## 현재 한계

- 실제 HMD/엔진 미연동 (Mock SQLite 상태)
- Qwen이 느리면 timeout 후 fallback (의도된 안전장치)
- Prompt 원문은 기본 미저장 (`LLM_STORE_SANITIZED_PROMPTS=true` 때만)
- 콘텐츠는 사전 등록 후보만 추천 (신규 생성 금지)

---

## 폴더 구조

```
xr-control-agent-poc/
  shared/state_report.py
  backend/app/
    llm/          Qwen client · prompt · parser · repair · health
    agents/xr_control/   LangGraph 스타일 러너
    planners/     Qwen + Fallback
    validators/   schema/policy/action/content/safety
    services/     ranker · mock XR · memory · plan
  frontend/       React 대시보드 (10탭)
  scripts/
```
