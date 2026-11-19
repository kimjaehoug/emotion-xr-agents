# Emotion Mapping Agent

한국어 감정 문장을 **KOTE 44대 / 18대** 감정으로 분류한 뒤, LLM 에이전트가 **7대 기본감정**으로 매핑하는 시스템입니다.

## 파이프라인

```
입력 문장
  → ClassifierAgent (KOTE 44 + 18대 분류)
  → MapperAgent (7대 기본감정 매핑)
  → 결과 + 변환 과정
```

## 설정

```bash
cp .env.example .env
# .env에서 LLM_API_KEY 설정
```

| 환경 변수 | 설명 | 기본값 |
|-----------|------|--------|
| `LLM_BASE_URL` | OpenAI 호환 API URL | `http://210.117.143.180:11525/v1` |
| `LLM_API_KEY` | API 토큰 | (필수 설정) |
| `LLM_MODEL` | 모델명 (비우면 자동 감지) | `` |
| `PORT` | 웹 서버 포트 | `8080` |

## 실행

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

브라우저에서 `http://localhost:8080` 접속

## API

- `POST /api/analyze` — 감정 분석
- `GET /api/emotions` — 감정 목록
- `GET /api/health` — 상태 확인
