# React Frontend

React.js 프론트엔드 (Vite + TypeScript + Tailwind CSS + shadcn/ui)

## 설치

```bash
npm install
```

## 개발 서버 실행

**1. 백엔드 API 먼저 실행** (프로젝트 루트에서)

```bash
cd .. && uvicorn api.main:app --reload --port 8000
```

**2. 프론트엔드 실행**

```bash
npm run dev
```

브라우저에서 http://localhost:3000 접속.  
이미지/PDF 설계도 업로드 후 **Start Analysis** → Upload → Preprocess → **BiCep 변환** → **Policy 검증** → RedTeam → Result 흐름으로 동작합니다.

## 빌드

```bash
npm run build
```

## 프로젝트 구조

```
frontend/
├── src/
│   ├── components/           # React 컴포넌트
│   │   ├── ui/              # shadcn/ui 기본 컴포넌트
│   │   │   ├── button.tsx
│   │   │   ├── checkbox.tsx
│   │   │   ├── dialog.tsx
│   │   │   └── accordion.tsx
│   │   ├── UploadCard.tsx    ✅ 파일 업로드 (드래그 앤 드롭)
│   │   ├── PipelineBar.tsx   ✅ 파이프라인 진행 상태
│   │   ├── ResultSummary.tsx ✅ 결과 요약 메트릭
│   │   ├── ResultGrid.tsx    ✅ 결과 카드 Grid (2x2)
│   │   ├── DetailModal.tsx   ✅ 상세 모달
│   │   ├── ChatPanel.tsx     ✅ AI 챗봇 슬라이딩 패널
│   │   └── MainContent.tsx   ✅ 메인 컨텐츠 오케스트레이터
│   ├── services/            # API 호출
│   │   └── api.ts
│   ├── store/               # Zustand 상태 관리
│   │   └── app.ts
│   ├── types/               # TypeScript 타입
│   │   └── api.ts
│   ├── lib/                 # 유틸리티
│   │   └── utils.ts
│   ├── hooks/               # Custom hooks
│   ├── App.tsx              # 메인 앱
│   ├── main.tsx             # 엔트리 포인트
│   └── index.css            # 글로벌 스타일 (Glassmorphism 포함)
├── public/                  # 정적 파일
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

## 주요 기능 (계획)

- ✅ 프로젝트 구조 및 설정 파일
- ✅ Glassmorphism 스타일 시스템
- ✅ API 서비스 레이어
- ✅ Zustand 상태 관리
- ✅ 파일 업로드 컴포넌트 (드래그 앤 드롭)
- ✅ 파이프라인 진행 바
- ✅ 결과 요약 메트릭
- ✅ 결과 Grid (2x2)
- ✅ 상세 모달 (취약점, 공격, Policy, 보고서)
- ✅ AI 챗봇 슬라이딩 패널
- ✅ 애니메이션 (Framer Motion)
- ✅ 실제 분석 실행 (Start Analysis → POST /api/v1/analyze, BiCep 변환 → Policy Agent 연동)
- ⬜ 에러 핸들링 개선
- ⬜ 로딩 상태 개선

## 참고

- 상세 디자인 명세: [../docs/FRONTEND.md](../docs/FRONTEND.md)
- API 명세: [../docs/API.md](../docs/API.md)
