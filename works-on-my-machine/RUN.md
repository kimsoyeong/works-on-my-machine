# 페이지 직접 실행 방법 (React 기반)

**conda 환경:** `agenthonms` 사용

---

## 1) 백엔드 API (터미널 1)

```bash
conda activate agenthonms
cd /Users/bomin/Documents/project/agenthon/works-on-my-machine
PYTHONPATH=. uvicorn api.main:app --reload --port 8000
```

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

---

## 2) React 프론트엔드 (터미널 2)

```bash
cd /Users/bomin/Documents/project/agenthon/works-on-my-machine/frontend
npm install
npm run dev
```

브라우저에서 **http://localhost:3000** 접속 후, 설계도 업로드 → **Start Analysis** 로 분석 실행.

---

## 요약

| 구분     | 명령 |
|----------|------|
| 터미널 1 | `conda activate agenthonms` → `cd works-on-my-machine` → `PYTHONPATH=. uvicorn api.main:app --reload --port 8000` |
| 터미널 2 | `cd frontend` → `npm install` → `npm run dev` → **http://localhost:3000** |

**터미널 1(API)을 먼저 실행**한 다음 터미널 2에서 React를 띄우면 됩니다.
