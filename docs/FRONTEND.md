# React 프론트엔드 가이드

> **Status:** 구현 완료 (`frontend/` 디렉토리)

## 개요

PreFlight의 프론트엔드는 `frontend/` 디렉토리에 React + TypeScript로 구현되어 있습니다.

## 기술 스택

- Framework: React + TypeScript
- State Management: Zustand
- UI Library: shadcn/ui + Tailwind CSS
- Build Tool: Vite

## 실행

```bash
cd frontend
npm install
npm run dev
```

프론트엔드: http://localhost:5173

백엔드 API 서버도 함께 실행 필요:

```bash
uvicorn api.main:app --reload --port 8000
```

## API 통신

| Method | Endpoint          | 설명                      |
| ------ | ----------------- | ------------------------- |
| GET    | `/api/v1/health`  | 헬스 체크                 |
| POST   | `/api/v1/analyze` | 아키텍처 파일 분석        |

자세한 API 명세는 [API.md](API.md) 참조.

## 화면 구성

### 파이프라인 Progress Bar

분석 단계를 시각적으로 표시:

```
● ─→ ● ─→ ● ─┬─→ ● ┐
업로드  전처리  BiCep  │ Policy │  ─→ ● 완료
                     └─→ ● ┘
                        Recon
```

### 메인 화면 레이아웃

```
┌──────────────────────────────────────────┐
│  1. 파일 업로드 카드                      │
│     PDF, PNG, JPG · Max 20MB             │
│     ☐ Skip Policy Validation             │
│     [ ▶ Start Analysis ]                 │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│  2. 결과 요약 (분석 완료 시)              │
│  Critical | High | Medium | Low | 공격   │
└──────────────────────────────────────────┘

┌─────────────────┬────────────────────────┐
│  🚨 취약점 목록  │  ⚡ 공격 시뮬레이션     │
├─────────────────┼────────────────────────┤
│  🛡️ Policy 검증 │  📊 보고서              │
└─────────────────┴────────────────────────┘
```
