# React 프론트엔드 가이드

> **Status:** 구현 완료 (`frontend/` 디렉토리)

## 개요

PreFlight의 프론트엔드는 IaC 아키텍처 보안 검증 도구의 SPA 인터페이스입니다.
아키텍처 다이어그램 업로드 → 실시간 분석 진행 표시 → 보안 리포트 대시보드의 3단계 플로우로 구성됩니다.

## 기술 스택

| 범주 | 기술 |
|------|------|
| Framework | React 18 + TypeScript |
| Build Tool | Vite 5 |
| State Management | Zustand 4 |
| Animation | Framer Motion 11 |
| Styling | 인라인 스타일 + CSS Custom Properties (`index.css`) |
| HTTP | Axios (REST), Fetch API (SSE 스트리밍) |
| Markdown | react-markdown + remark-gfm |
| Code Highlight | react-syntax-highlighter (Prism / oneDark) |
| Icons | lucide-react, 커스텀 SVG |

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

## 디렉토리 구조

```
frontend/src/
├── main.tsx                 # 엔트리포인트
├── App.tsx                  # 레이아웃 (헤더, 배경, ScrollToTop)
├── index.css                # 테마 토큰 + 글로벌 스타일
├── components/
│   ├── MainContent.tsx      # 화면 플로우 컨트롤러 (idle/analyzing/completed)
│   ├── UploadCard.tsx       # 파일 업로드 카드 (드래그&드롭, 미리보기)
│   ├── PipelineBar.tsx      # 결과 화면 파이프라인 미니맵
│   ├── ResultSummary.tsx    # 보안 등급 대시보드 (5개 카드 그리드)
│   ├── ResultTabs.tsx       # 상세 보고서 탭 (6개 서브탭 + Bicep 코드)
│   └── ui/                  # shadcn/ui 기반 공통 컴포넌트
│       ├── button.tsx
│       └── checkbox.tsx
├── services/
│   └── api.ts               # API 클라이언트 (REST + SSE)
├── store/
│   └── app.ts               # Zustand 전역 상태
├── types/
│   └── api.ts               # API 응답 타입 정의
└── lib/
    └── utils.ts             # 유틸리티 (cn 등)
```

## 화면 플로우

```
[idle] ─── 파일 업로드 ──→ [analyzing] ─── 완료 ──→ [completed]
  │                            │                        │
  │ 에러 발생                  │ 취소 클릭               │ "+ 새 분석" 클릭
  ↓                            ↓                        ↓
[error]                      [idle]                   [idle]
```

### 1. Idle — 업로드 화면

```
┌────────────────────────────────────────────┐
│  ◉ PreFlight                     (Header)  │
├────────────────────────────────────────────┤
│                                            │
│     🔭  아키텍처 보안 검증                   │
│     IaC 템플릿의 보안 정책을 검증하고...      │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │  ◉ ARCHITECTURE DIAGRAM             │  │
│  │  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐ │  │
│  │  │  ↑ 드래그하거나 클릭하여 업로드   │ │  │
│  │  │  PNG, JPG · 최대 20MB           │ │  │
│  │  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘ │  │
│  │                              [▲]    │  │
│  └──────────────────────────────────────┘  │
│                                            │
└────────────────────────────────────────────┘
```

### 2. Analyzing — 분석 진행

```
┌────────────────────────────────────────────┐
│  ◉ PreFlight  ● 에이전트 실행 중  00:30 취소│
├────────────────────────────────────────────┤
│                                            │
│           🔭 보안 취약점 스캐닝 중            │
│                                            │
│  ─── 단계별 타임라인 ───                     │
│  ↑ 아키텍처 업로드     ✓ 완료                │
│  │                                         │
│  </> IaC 템플릿 변환   ✓ 완료                │
│  │                                         │
│  │ ┌─ 병렬 실행 ─────────────────────┐     │
│  │ │ 🤖 보안 정책 검증  │ 🤖 위협 정찰 │     │
│  │ └────────────────────────────────┘     │
│  │                                         │
│  📄 보고서 생성         ◎ 진행 중             │
│  ─                                         │
│                                            │
│  전체 진행률                           80%  │
│  ████████████████████░░░░░                  │
│  업로드   IaC변환   정책·시뮬레이션   보고서   │
└────────────────────────────────────────────┘
```

**단계별 아이콘:**

| 단계 | 아이콘 (pending) | 설명 |
|------|------------------|------|
| 아키텍처 업로드 | `↑` 업로드 화살표 | 파일 업로드 단계 |
| IaC 템플릿 변환 | `</>` 코드 브래킷 | Bicep 코드 변환 |
| 보안 정책 검증 | `🤖` 로봇 | AI 에이전트 실행 |
| 위협 시나리오 정찰 | `🤖` 로봇 | AI 에이전트 실행 |
| 보고서 생성 | `📄` 문서 | 최종 리포트 |

### 3. Completed — 결과 대시보드

```
┌────────────────────────────────────────────┐
│  ◉ PreFlight                   ＋ 새 분석   │
├────────────────────────────────────────────┤
│                                            │
│  ┌─ 파이프라인 미니맵 ─────────────────────┐│
│  │ ☑업로드 → ☑IaC변환 → ┬☑정책검증┐→ ☑보고서││
│  │                      └☑위협정찰┘  1m 3s ││
│  └─────────────────────────────────────────┘│
│                                            │
│  ⚠ 즉시 조치 필요 — Critical 2건 · 위반 3건  │
│                                            │
│  ┌─────────┬──────────┬──────────┐         │
│  │ 보안등급  │ 정책 위반  │ 발견 취약점 │         │
│  │    D     │   3/8    │    7건    │         │
│  │  42/100  │ ████░░░  │ ████░░░  │         │
│  │         ├──────────┼──────────┤         │
│  │         │ 위협시나리오│ 아키텍처   │         │
│  │         │   5건수행  │ 재현율 75% │         │
│  └─────────┴──────────┴──────────┘         │
│                                            │
│  ┌─ 보고서 탭 ─────────────────────────────┐│
│  │ 📋 보고서 │ ⚙ 개선된 Bicep      ↓ 다운로드││
│  │                                        ││
│  │ [정책준수] [보안통제] [취약점우선순위]     ││
│  │ [위협시뮬레이션] [아키텍처재현] [체크리스트]││
│  │                                        ││
│  │ (선택된 섹션의 상세 테이블)               ││
│  └────────────────────────────────────────┘│
└────────────────────────────────────────────┘
```

## API 통신

| Method | Endpoint                | 설명 |
|--------|-------------------------|------|
| GET    | `/api/v1/health`        | 헬스 체크 |
| POST   | `/api/v1/analyze`       | 아키텍처 파일 분석 (일반 REST) |
| POST   | `/api/v1/analyze/stream` | 아키텍처 파일 분석 (SSE 스트리밍) |

### SSE 이벤트 타입

```typescript
// 단계 진행 알림
{ type: 'step', data: { step: string, status: 'pending'|'in_progress'|'completed'|'error', message?: string } }

// 최종 결과
{ type: 'result', data: AnalyzeResponse }

// 에러
{ type: 'error', data: { message: string } }
```

자세한 API 명세는 [API.md](API.md) 참조.

## 상태 관리 (Zustand)

```typescript
interface AppState {
  // 화면 상태
  analysisState: 'idle' | 'uploading' | 'analyzing' | 'completed' | 'error';

  // 데이터
  uploadedFile: File | null;
  analysisResult: AnalyzeResponse | null;
  previousResult: AnalyzeResponse | null;  // 재검증 시 이전 결과 (델타 비교용)
  liveSteps: StepStatus[];                 // SSE로 수신하는 실시간 단계
  error: string | null;

  // 타이머
  analysisStartTime: number | null;
  elapsedSeconds: number | null;           // 분석 완료 시 소요 시간 기록

  // UI
  reportSection: string;                   // 보고서 활성 서브탭
}
```

## 컴포넌트 상세

### App.tsx — 레이아웃 쉘

- **Header**: 고정 상단바 (`position: fixed`), 로고 + 상태 배지 + 액션 버튼
  - `analyzing` 상태: "에이전트 실행 중" 배지 + 경과 시간 + "분석 취소" 버튼
  - `completed` 상태: "＋ 새 분석" 버튼
- **Ambient Background**: 배경 그라데이션 원형 + 도트 그리드 패턴
- **ScrollToTopButton**: 스크롤 300px 이상 시 나타나는 플로팅 버튼

### MainContent.tsx — 화면 플로우 컨트롤러

`analysisState`에 따라 3가지 뷰를 전환:

1. **Idle/Error**: 히어로 섹션 + `UploadCard` + 면책 문구
2. **Analyzing**: `AnalyzingProgress` 컴포넌트
3. **Completed**: 파이프라인 카드 + `ResultSummary` + `ResultTabs`

#### AnalyzingProgress (내부 컴포넌트)

- 레이더 애니메이션 히어로
- 5단계 수직 타임라인 (세로선 연결)
  - `StepIcon`: 상태별 아이콘 (완료=체크, 진행=스피너, 대기=단계별 고유 아이콘)
  - 병렬 그룹 박스 (보안 정책 검증 + 위협 시나리오 정찰)
  - 업로드 완료 시 이미지 미리보기 토글
- 전체 진행률 바 + 단계 라벨

### UploadCard.tsx — 파일 업로드

- 드래그&드롭 + 클릭 업로드
- 파일 검증: PNG/JPG만 허용, 최대 20MB
- 업로드 후: 이미지 미리보기 + 파일명 + 크기 + 변경 버튼
- 전송 버튼 (보라색 화살표)

### PipelineBar.tsx — 파이프라인 미니맵

결과 화면 상단에 분석 파이프라인 흐름을 시각적으로 표시:

```
☑업로드 → ☑IaC변환 → ┬☑정책검증┐ → ☑보고서생성    ⏱ 1m 3s
                      └☑위협정찰┘
```

- **StepChip**: 28×28px 아이콘 박스 + 라벨 텍스트
  - 완료: 녹색 배경 + 체크마크
  - 진행 중: 보라색 배경 + 스피너
  - 대기: 단계별 고유 아이콘 (업로드/코드/로봇/문서)
- **Arrow**: SVG 화살표 커넥터 (40×10px)
- **Fork/Merge**: SVG 분기·합류선 (병렬 단계용)
- 경과 시간: 우측 절대 위치

### ResultSummary.tsx — 보안 대시보드

5개 카드 그리드 (3열 × 2행):

| 카드 | 내용 |
|------|------|
| **보안 등급** (2행 span) | A~F 등급, 점수 게이지 차트, 등급 기준 팝오버 |
| **정책 위반** | 위반/권고 건수, 비율 바 |
| **발견 취약점** | Critical/High/Medium/Low 분포 |
| **위협 시나리오** | 침투 성공/부분/차단 분류 |
| **아키텍처 재현율** | 퍼센트 + 카테고리별 진행 바 |

- 재검증 시 이전 결과와 델타(↑↓) 표시
- 경고 배너: score < 60 또는 Critical/High 취약점 존재 시
- "상세 보기 >" 클릭 → 해당 보고서 서브탭으로 스크롤

**보안 등급 산정 공식:**
- 정책 준수 점수: 65점 만점 × (1 - 위반/전체정책)
- 취약점 점수: 35점 × 재현 신뢰도 - (Critical×15 + High×8 + Medium×4 + Low×1)
- 최종: 100점 정규화

### ResultTabs.tsx — 상세 보고서

메인 탭 2개:
- **📋 보고서**: 6개 서브탭
- **⚙ 개선된 Bicep**: 구문 하이라이팅 코드 뷰 + "재검증" 버튼

보고서 서브탭:

| 서브탭 | 내용 |
|--------|------|
| 정책 준수 검토 | 위반/권고 테이블 |
| 보안 통제 검토 | 통제 항목별 적용 여부 (✓/✗/◐) |
| 취약점 우선순위 | 심각도 필터 + 취약점 테이블 |
| 위협 시뮬레이션 | 공격 결과 테이블 + 분석 결론 마크다운 |
| 아키텍처 재현 | Docker 재현 테이블 + 재현 점수 상세 |
| 검증 체크리스트 | 항목별 통과/수정필요 상태 |

- 다운로드 버튼 (보고서 MD / Bicep 파일)
- "개선된 Bicep으로 재검증" → 이전 결과 저장 후 재분석 트리거

## 디자인 시스템

### 컬러 팔레트

| 용도 | 색상 | 코드 |
|------|------|------|
| 앱 액센트 | 보라 | `#6C3AED` |
| 액센트 호버 | 연보라 | `#8B5CF6` |
| Critical 심각도 | 빨강 | `#ef4444` |
| High 심각도 | 인디고 | `#6366f1` |
| Medium/Low 심각도 | 회색 | `#cbd5e1` |
| 완료/통과 | 녹색 | `#22c55e` |
| 페이지 배경 | 밝은 회색 | `#f8f9fb` |
| 본문 텍스트 | 다크 네이비 | `#0f172a` |
| 파이프라인 라벨 (활성) | 차콜 | `#374151` |

### 타이포그래피

| 용도 | 폰트 | 비고 |
|------|------|------|
| 제목 (h1, 등급 등) | Outfit | Bold 700–800, 네거티브 트래킹 |
| 본문/라벨 | DM Sans | Regular 400–600 |
| 코드/수치 | DM Mono, JetBrains Mono | 모노스페이스 |

### CSS Custom Properties

테마 토큰은 `index.css`의 `:root`에 정의 (`--pf-*` 네임스페이스):

- `--pf-bg`: 페이지 배경
- `--pf-surface`: 카드 배경
- `--pf-border`: 테두리
- `--pf-text-1` ~ `--pf-text-5`: 텍스트 계층 (진함→연함)
- `--pf-accent`: 앱 액센트 색상
- `--pf-header-bg`: 헤더 배경 (반투명 블러)
- `--pf-error-*`: 에러 상태 색상

### 애니메이션

| 이름 | 용도 |
|------|------|
| `pf-spin` | 스피너 회전 |
| `pf-pulse` | 헤더 분석 중 배지 펄스 |
| `pf-icon-pulse` | 진행 중 StepIcon 박스 섀도 펄스 |
| `pf-radar-sweep` | 분석 중 레이더 회전 |
| `pf-indeterminate` | 병렬 단계 불확정 진행 바 |
| Framer Motion | 화면 전환, 카드 등장 애니메이션 |
