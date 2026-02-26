# 개발 가이드

## 사전 요구사항

- Python 3.10+
- Node.js 18+ (프론트엔드)
- pip

## 초기 설정

```bash
# 가상 환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 의존성 설치 (agent-framework는 pre-release이므로 --pre 필요)
pip install -r requirements.txt --pre

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 필요한 값 입력
```

## 컴포넌트별 실행

### API 서버

```bash
# 개발 모드 (자동 리로드)
uvicorn api.main:app --reload --port 8000

# 프로덕션 모드
gunicorn -c gunicorn.conf.py api.main:app
```

API 엔드포인트 테스트:

```bash
# 헬스 체크
curl http://localhost:8000/api/v1/health

# 파일 분석
curl -X POST http://localhost:8000/api/v1/analyze \
  -F "file=@/tmp/test.png"

# Swagger UI → http://localhost:8000/docs
```

### React 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

프론트엔드: http://localhost:5173

### Recon Agent 단독 테스트

```bash
python3 -c "
import asyncio
from pathlib import Path
from agents.new_agent_wrapper_v2 import analyze_bicep

async def main():
    bicep = Path('samples/sample_bicep.bicep').read_text()
    result = await analyze_bicep(bicep, agent_mode='with-tools')

    print(f'취약점: {len(result.vulnerabilities)}개')
    for sev, cnt in result.vulnerability_count.items():
        if cnt > 0:
            print(f'  {sev}: {cnt}개')
    print(f'공격 시나리오: {len(result.attack_scenarios)}개')
    print()
    print(result.report)

asyncio.run(main())
"
```

## 테스트

```bash
# 전체 테스트 실행
pytest tests/ -v

# 특정 테스트 파일 실행
pytest tests/test_api.py -v

# 커버리지 리포트
pytest tests/ --cov=api --cov=agents --cov=api/common/services --cov-report=html
```

---

## 코드 스타일

```bash
# 린팅
ruff check .

# 포매팅
ruff format .

# 타입 체크
mypy api/ agents/ api/common/services/
```

---

## 트러블슈팅

| 문제 | 해결 |
| ---- | ---- |
| `ModuleNotFoundError: No module named 'xxx'` | 가상 환경 활성화 확인: `source .venv/bin/activate` |
| API 서버 포트 충돌 | `lsof -i :8000` 후 프로세스 종료, 또는 다른 포트 사용 |
| `.env` 파일 인식 안됨 | `.env.example`을 복사하여 `.env` 생성 확인 |
| Vision LLM 호출 실패 | `AI_FOUNDRY_ENDPOINT`, `AI_FOUNDRY_API_KEY` 환경 변수 확인 |
| Policy Agent 실패 | `AZURE_OPENAI_*` 환경 변수 확인 |

---

## 개발 진행 상태

| Phase | 내용                     | 상태 |
| ----- | ------------------------ | ---- |
| 1     | 기반 구조 및 서비스      | 완료 |
| 2     | Recon Agent (LLM 기반)   | 완료 |
| 3     | FastAPI 구현             | 완료 |
| 4     | React 프론트엔드         | 완료 |
| 5     | Policy Agent (RAG + LLM) | 완료 |
| 6     | 통합 및 테스트           | 진행 중 |
