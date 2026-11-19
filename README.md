# 감정·감성 인지 기반 XR 개인화 에이전트 (PoC)

사용자의 **발화 감정**과 **인지 상태**(인지 부하·집중도·피로도)를 함께 읽고, 그 결과에 맞춰 **XR 환경을 조절**하는 연구용 에이전트 3종입니다.
에이전트마다 사용자별 장기 메모리를 두어, 세션이 쌓일수록 개인 특성을 학습함.

> 연구용 PoC입니다. 의료 진단·치료 목적이 아니며, 실제 HMD 대신 Mock XR 런타임을 사용합니다.

---

## 1. 전체 흐름

```
 사용자 발화 ("화면 전환이 빨라 불안해요")
        │
        ▼
┌──────────────────────────┐
│ ① 감정 매핑 에이전트       │  KOTE 44·18 세부 감정 분류 → 7대 기본 감정 매핑
│   emotion-mapping-agent   │
└────────────┬─────────────┘
             │ emotion_context (기본 감정·강도)
             ▼
┌──────────────────────────┐   인지 지표 (인지 부하·집중도·피로도)
│ ② 상태인지 에이전트        │ ◀─ 외부 인지평가 값 입력
│   state-aware-agent-poc   │  개인 기준선 대비 변화 분석 → State Report
└────────────┬─────────────┘
             │ State Report + memory_context
             ▼
┌──────────────────────────┐
│ ③ XR 환경제어 에이전트     │  허용된 정책·조작 범위 안에서 XR 조절 계획 생성·검증·실행
│   xr-control-agent-poc    │
└──────────────────────────┘
```

- 에이전트 사이는 **JSON 계약**(`emotion_context`, State Report, `memory_context`)으로만 연결됨. 서로 직접 호출하지 않으므로 하나씩 따로 실행·시험할 수 있음.
- 세 에이전트 모두 **LLM 없이도 동작**함. LLM이 없거나 응답이 규칙을 어기면 규칙 기반 판단으로 대체함.

---

## 2. 폴더 구성

| 폴더 | 하는 일 | 기술 스택 | 기본 포트 |
|---|---|---|---|
| [`emotion-mapping-agent/`](emotion-mapping-agent) | 한국어 문장의 감정을 세부 감정(KOTE 44·18)으로 분류하고 7대 기본 감정으로 매핑함. 매핑 규칙집을 버전으로 관리함. | FastAPI · sqlite3 · 정적 HTML 대시보드 | 8080 |
| [`state-aware-agent-poc/`](state-aware-agent-poc) | 인지 지표를 사용자 개인 기준선과 비교해 변화·지속성을 계산하고 State Report를 만듦. | FastAPI · SQLAlchemy · LangGraph · React/Vite | API 8000 · 화면 5173 |
| [`xr-control-agent-poc/`](xr-control-agent-poc) | State Report를 받아 XR 조절 계획(시각 복잡도·청각 자극·상호작용 빈도 등)을 세우고, 정책 검증을 통과한 것만 실행함. | FastAPI · SQLAlchemy · React/Vite | API 8001 · 화면 5174 |

각 폴더에 자세한 설명이 담긴 `README.md`가 따로 있음.

---

## 3. 공통 메모리 구조

세 에이전트는 같은 메모리 핵심 모듈(`memory/core.py`, 세 폴더에 동일 사본)을 공유함.

| 메모리 | 내용 | 특징 |
|---|---|---|
| 분석 이력 로그 | 모든 분석·피드백 기록 | 수정·삭제 없이 누적만 함 |
| 세션 이력 | 세션별 감정·인지 상태와 조절 결과 | 중요도(참조 빈도·최근성·감정 강도·고유도)가 낮으면 요약해 보관함 |
| 개인 특성 메모리 | "시각 자극에 민감함" 같은 사용자 특성 카드 | 근거 세션과 유효 기간을 함께 저장. 새 정보는 덮어쓰지 않고 새 카드로 추가해 변경 이력을 남김 |
| 판단 규칙 | 사용자별 경고 규칙, 감정 매핑 규칙집 | 규칙집 변경은 제안 → 검토 → 승인 순서로만 반영됨 |
| 작업 메모리 | 이번 분석에 필요한 기억만 골라 담은 묶음 | 어휘 유사도·최근성·중요도로 관련 기억을 찾음 |

- 저장 전에 전화번호·이메일 등 개인정보를 가림.
- `core.py`를 고칠 때는 세 폴더의 사본을 함께 맞춰야 함.

---

## 4. 실행 방법

필요 환경: Python 3.10 이상(상태·XR 백엔드는 3.11 권장), Node.js 18 이상.

### 4-1. 감정 매핑 에이전트 (:8080)

```bash
cd emotion-mapping-agent
pip install -r requirements.txt
cp .env.example .env            # LLM을 쓸 때만 주소·키 수정
LLM_MODE=offline python3 -m uvicorn main:app --port 8080
```

브라우저에서 http://127.0.0.1:8080 접속.

### 4-2. 상태인지 에이전트 (:8000 / 화면 :5173)

```bash
cd state-aware-agent-poc
cp .env.example .env
OLLAMA_ENABLED=false ./scripts/run_backend.sh     # 처음 실행 시 가상환경을 만들고 패키지를 설치함
./scripts/run_frontend.sh                          # 다른 터미널에서 실행
```

브라우저에서 http://localhost:5173 접속.

### 4-3. XR 환경제어 에이전트 (:8001 / 화면 :5174)

```bash
cd xr-control-agent-poc
cp backend/.env.example backend/.env
LOCAL_LLM_BASE_URL=http://127.0.0.1:9/v1 ./scripts/run_backend.sh   # LLM 연결이 실패해 규칙 기반 계획으로 동작함
./scripts/run_frontend.sh
```

브라우저에서 http://localhost:5174 접속.

### LLM을 쓸 때

| 에이전트 | 설정 | 비고 |
|---|---|---|
| 감정 매핑 | `.env`의 `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODE=auto` | OpenAI 호환 API |
| 상태인지 | `.env`의 `OLLAMA_ENABLED=true`, `OLLAMA_BASE_URL` | Ollama |
| XR 환경제어 | `backend/.env`의 `LOCAL_LLM_BASE_URL` | Qwen3.5-9B 등 OpenAI 호환 로컬 서버 |

---

## 5. 테스트

```bash
cd emotion-mapping-agent && python3 -m pytest
cd state-aware-agent-poc/backend && .venv/bin/python -m pytest
cd xr-control-agent-poc/backend && .venv/bin/python -m pytest
```

---

## 6. 참고

- 메모리 설계는 「AI 에이전트를 깊이 이해하기」 3장(에이전트 메모리)을 참고함.
- 실행 중 만들어지는 메모리 DB(`*.db`)와 `.env`는 저장소에 올리지 않음.
