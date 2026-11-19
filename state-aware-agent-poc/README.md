# State-Aware AI Agent PoC

연구용 **상태 인지 AI Agent** PoC입니다.  
외부에서 제공된 인지평가 정량값(`cognitive_load`, `attention`, `fatigue`)을 사용자 개인 Baseline과 비교하여 **Cognitive Gap**을 계산하고, 구조화된 **State Report JSON**을 생성합니다.

> 실제 의료 진단 시스템이 아닙니다. 콘텐츠 추천·XR 제어는 수행하지 않습니다.

---

## 목적

- 개인 Baseline 대비 현재 상태 변화 분석
- 단기/누적 추세 및 지속성(persistence) 반영
- 4계층 장기 Memory(Profile / Baseline / Episodic / Summary) 영구 저장
- 후속 Agent가 소비할 수 있는 State Report 산출

---

## 아키텍처

```
[Input JSON]
    ↓
FastAPI  (/api/v1/state/analyze)
    ↓
LangGraph Pipeline
  validate_input
  → load_profile_memory
  → load_baseline_memory
  → load_recent_episodes
  → compute_cognitive_gap
  → analyze_trend
  → classify_state (policy + config)
  → generate_state_report (+ optional Qwen narrative)
  → save_episode
  → update_summary_memory
    ↓
SQLite (장기 Memory)
    ↓
State Report JSON → React Dashboard
```

### LLM (선택)

- 로컬 **Ollama `qwen3.5:9b`** 사용
- 16GB RAM 환경을 고려해 `num_ctx=4096`, `num_predict=256`으로 제한
- LLM 장애 시에도 결정적 분석 파이프라인은 정상 동작

---

## 폴더 구조

```
backend/app/
  api/          FastAPI 라우터
  agents/       LangGraph 노드·그래프
  policies/     상태 분류 정책
  services/     Baseline/Gap/Seed/LLM
  repositories/ DB 접근
  models/       SQLAlchemy
  schemas/      Pydantic
frontend/src/
  pages 역할 → App 탭
  components/   Dashboard 구성 요소
  api/          REST 클라이언트
```

---

## 설치 방법

### Backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env  # 필요 시 수정
```

### Frontend

```bash
cd frontend
npm install
```

### Ollama (서술 관찰용, 선택)

```bash
ollama serve
ollama pull qwen3.5:9b
```

---

## 실행 방법

### Backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

또는 루트에서:

```bash
./scripts/run_backend.sh
```

### Frontend

```bash
cd frontend
npm run dev
```

또는:

```bash
./scripts/run_frontend.sh
```

브라우저: http://localhost:5173  
API 문서: http://localhost:8000/docs

첫 화면에서 **Mock Seed**를 누르면 데모 사용자 `U001`(Baseline 보유), `U002`(Baseline 없음)가 생성됩니다.

---

## API 사용 예시

### 상태 분석

```bash
curl -X POST http://localhost:8000/api/v1/state/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "U001",
    "session_id": "S001",
    "timestamp": "2026-07-21T10:00:00+09:00",
    "cognitive_metrics": {
      "cognitive_load": 0.72,
      "attention": 0.58,
      "fatigue": 0.68
    },
    "context": {
      "content_id": "C102",
      "content_type": "education",
      "difficulty": 0.8,
      "visual_complexity": 0.75,
      "audio_stimulation": 0.6,
      "elapsed_time_min": 25
    },
    "data_quality": {
      "cognitive_confidence": 0.90,
      "completeness": 0.95
    }
  }'
```

### 사용자 / Baseline

```bash
# 사용자 생성
curl -X POST http://localhost:8000/api/v1/users \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"U010","profile":{"preferred_content_types":["education"],"xr_experience_level":"beginner"}}'

# 정상 샘플 등록
curl -X POST http://localhost:8000/api/v1/users/U010/baseline-observations \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"OBS1","cognitive_load":0.45,"attention":0.7,"fatigue":0.35,"confidence":0.9,"completeness":0.95,"is_normal_confirmed":true}'

# Baseline 생성 (정상 샘플 ≥ 3)
curl -X POST http://localhost:8000/api/v1/users/U010/baseline/build

# Memory 조회
curl http://localhost:8000/api/v1/users/U001/episodes
curl http://localhost:8000/api/v1/users/U001/summary
```

---

## Baseline 생성 방법

1. 사용자 생성
2. `is_normal_confirmed=true` 인 정상 세션 샘플을 최소 3개 등록  
   (`confidence≥0.8`, `completeness≥0.8`)
3. `POST /baseline/build` 호출
4. 중앙값+절사평균 기반 center, IQR 기반 정상범위 저장
5. 자동 갱신은 드리프트 허용치 초과 시 보류

개인 Baseline이 없으면 `state_level=UNKNOWN`입니다.  
`.env`의 `USE_GROUP_DEFAULT_BASELINE=true`로 그룹 기본값을 사용할 수 있으며, 이 경우 report에 `baseline.source=group_default`로 명시됩니다.

---

## State Report 예시

```json
{
  "state_report_id": "SR-A1B2C3D4",
  "user_id": "U001",
  "session_id": "S001",
  "state_level": "ACTION_REQUIRED",
  "baseline": { "source": "personal", "version": "v1", "reliability": 0.84 },
  "cognitive_gap": {
    "cognitive_load": {
      "current": 0.72,
      "baseline": 0.48,
      "deviation": 0.24,
      "status": "above_baseline",
      "trend": "increasing",
      "persistent": true
    }
  },
  "analysis_confidence": 0.84,
  "requires_response": true,
  "warnings": []
}
```

상태 수준: `NORMAL` | `WATCH` | `ACTION_REQUIRED` | `UNKNOWN`

---

## 테스트 방법

```bash
cd backend
source .venv/bin/activate
pytest -v
```

포함 시나리오: Baseline 없음→UNKNOWN, 정상→NORMAL, 단일 이탈→WATCH, 복수 지속 이탈→ACTION_REQUIRED, 낮은 confidence, 422 검증, Memory 유지, Baseline 최소 샘플, 비정상 세션 제외 등.

---

## 현재 한계

- 센서/외부 인지평가 API 미연동 (mock 입력)
- Baseline 자동 갱신은 보수적(수동 build + 드리프트 가드)
- 조건별(콘텐츠 난이도별) Baseline은 스키마만 확장 가능, PoC는 통합 Baseline
- Qwen 서술 관찰은 보조 정보이며 분류 결과에 영향 없음
- 의료·임상 검증 없음

---

## 향후 T2 감정·감성 결과 연계 계획

1. `affective_metrics` 입력 채널 추가 (각성/쾌·불쾌 등 외부 정량값)
2. Affective Gap을 Cognitive Gap과 병렬 계산
3. Summary Memory에 인지–정서 동시 패턴 기록
4. State Report에 `affective_gap` 섹션 추가 (추천/XR 명령 없이 관찰만)
5. 정책 모듈에서 교차 지속성(cross-persistence) 규칙 확장

---

## 환경 변수 요약

| 변수 | 기본 | 설명 |
|------|------|------|
| `OLLAMA_MODEL` | `qwen3.5:9b` | 로컬 LLM |
| `OLLAMA_NUM_CTX` | `4096` | 16GB RAM 고려 컨텍스트 |
| `OLLAMA_ENABLED` | `true` | false면 서술 생략 |
| `MIN_BASELINE_SAMPLES` | `3` | Baseline 최소 샘플 |
| `USE_GROUP_DEFAULT_BASELINE` | `false` | 그룹 Baseline 사용 |
| `WATCH_DEVIATION_THRESHOLD` | `0.15` | WATCH 편차 |
| `ACTION_DEVIATION_THRESHOLD` | `0.30` | ACTION 편차 |
| `PERSISTENCE_THRESHOLD` | `2` | 지속 판정 횟수 |
