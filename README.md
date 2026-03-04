# ✈️ PreFlight

> **Azure 아키텍처 다이어그램을 배포 전 설계 단계에서 사내 보안 정책 준수 여부와 잠재적 공격 가능성을 AI가 자동 검토해, 리스크를 사전 식별하고 검증 우선순위를 제시하는 에이전트 시스템**

비행기가 이륙 전 반드시 체크리스트를 수행하듯, PreFlight는 시스템이 배포(이륙)되기 전에 보안을 점검합니다.

---

## 🔍 왜 PreFlight인가?

| 문제 | 설명 |
|------|------|
| 수작업 기반 설계 검토 | 보안 검토자가 draw.io 등 아키텍처 다이어그램을 육안으로 직접 검토하여 담당자 역량에 따라 검토 품질이 일관되지 않음 |
| 정책 업데이트 무알림 | 사내 보안 정책은 수시로 변경되지만 개발자에게 별도 알림이 없어, 바뀐 정책을 모른 채 설계가 진행됨 |
| 높은 정책 이해 장벽 | 업데이트된 정책을 직접 찾아봐도 법적·기술적 언어로 작성되어 설계에 적용하기 어려움 |
| 위협 분석 전문가 부재 | 보안 전문 인력 없이는 아키텍처 수준의 공격 가능성을 체계적으로 식별하기 어려움 |
| 배포 후 뒤늦은 문제 발견 | 검토에서 누락된 정책 위반·보안 취약점이 배포 후 드러나 재설계·재배포 비용 발생 |

---

## 🤖 에이전트 구성

### 📋 Policy Agent
Vector DB 기반 RAG를 활용해 사내 보안 정책(개발 정책, 개인정보보호, 기밀유지 등)과 아키텍처를 자동 대조합니다.

- 수시로 업데이트되는 사내 정책을 Vector DB로 관리 → 항상 최신 기준으로 자동 검토
- 위반 항목과 그 이유를 쉬운 자연어로 설명

### 🔎 Recon Agent
설계 단계에서 아키텍처의 잠재적 공격 벡터와 취약 지점을 탐지합니다.

> ⚠️ Recon Agent는 **실제 침투 테스트나 공격을 수행하지 않습니다.**
> 설계 도면을 공격자 시각으로 분석해 *공격 가능성*을 사전에 식별하고, 검증 우선순위를 제시하는 역할입니다.

- 잠재적 공격 벡터·노출 지점·인증 취약점 등 위협 시나리오 도출
- Critical / High / Medium / Low 위험도로 분류 및 우선순위 제시

---

## 🔄 주요 흐름

```
[사용자: 개발자/아키텍트]
        │
        │  아키텍처 다이어그램 이미지 업로드 (draw.io, PNG, PDF 등)
        ▼
┌─────────────────────────┐
│  LLM · Bicep 변환        │
│  이미지 → Bicep 코드 자동 생성  │
└───────────┬─────────────┘
            │
    ┌───────┴────────┐
    ▼                ▼
┌──────────────┐  ┌──────────────┐
│ Policy Agent │  │ Recon Agent  │
│              │  │              │
│ Vector DB    │  │ 공격 벡터      │
│ RAG 기반      │  │ 탐지·분류      │
│ 정책 위반      │  │ 위험도 우선     │
│ 자동 검토      │  │ 순위 제시      │
└──────┬───────┘  └──────┬───────┘
       └────────┬─────────┘
                ▼
   ┌─────────────────────────┐
   │  PreFlight 통합 보고서     │
   │  (설계 의도 대비 분석)       │
   │                         │
   │  • 원본 설계 의도 요약      │
   │  • 변환 구조 검토          │
   │  • 보안 불일치 분석         │
   │  • 잠재적 영향 해설         │
   │  • 배포 전 체크리스트       │
   └─────────────────────────┘
```

| 단계 | 주요 흐름 | 기대 효과 |
|------|-----------|-----------|
| 1 | 아키텍처 다이어그램 이미지 업로드 | 기존 설계 산출물 그대로 활용 가능 |
| 2 | LLM이 이미지를 분석해 Bicep 코드로 자동 변환 | 수동 코드 작성 없이 구조화된 분석 입력 생성 |
| 3 | Policy Agent — Vector DB 최신 정책 기반 위반 항목 자동 검토 (병렬) | 정책 업데이트 여부와 무관하게 항상 최신 기준 적용 |
| 4 | Recon Agent — 잠재적 공격 벡터·취약 지점 탐지 및 위협 시나리오 도출 (병렬) | 보안 전문가 없이도 설계 단계 위협 가시화 |
| 5 | PreFlight Agent — Policy + Recon 결과를 설계 의도 관점에서 통합 해설 보고서 생성 | 단순 목록이 아닌 "왜 위험한가"를 설계 맥락으로 설명 |

---

## ✨ 주요 기능

- **이미지 → Bicep 자동 변환**: LLM이 아키텍처 다이어그램을 분석해 Bicep 코드로 변환, 별도 코드 작성 불필요
- **최신 정책 자동 적용**: 수시로 업데이트되는 사내 보안 정책을 Vector DB로 관리, 항상 최신 기준으로 자동 검토
- **설계 단계 위협 탐지**: 공격 벡터와 취약 지점을 사전에 식별하고 위험도 우선순위 자동 분류
- **자연어 해설 포함 통합 보고서**: 정책 위반·위협 시나리오를 쉬운 언어로 설명, 검토 이력 자동 문서화

---

## 🗂️ 프로젝트 구조

```
works-on-my-machine/
├── agents/
│   ├── policy_agent.py          # Policy Agent (RAG + LLM 기반 정책 검증)
│   ├── preflight_agent.py       # PreFlight Agent (통합 보안 보고서 생성)
│   ├── new_agent_wrapper_v2.py  # Recon Agent wrapper (JSON 파싱)
│   └── new_agent_with_tools.py  # Recon Agent (MAF 기반, with-tools 모드)
├── api/
│   ├── main.py                  # FastAPI 애플리케이션
│   ├── routers/analyze.py       # 분석 파이프라인 오케스트레이션
│   ├── models/response.py       # 응답 모델 (SecurityResult 등)
│   └── common/services/         # Bicep 변환 (Vision LLM)
├── frontend/                    # React 프론트엔드 (Vite + TypeScript)
├── data/                        # 사내 보안 정책 문서 및 Vector DB
├── samples/                     # 샘플 Bicep 파일
└── docs/                        # 상세 문서
```

---

## 🚀 빠른 시작

### 요구사항
- Python 3.10 이상
- Docker & Docker Compose

### 설치

```bash
git clone <repository-url>
cd works-on-my-machine
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt --pre
```

### 실행

```bash
# API 서버
uvicorn api.main:app --reload

# 오류 발생 시,
# {가상환경명}/bin/activate api.main:app --reload

# React 프론트엔드
cd frontend && npm install && npm run dev
```

---

## 📚 문서

| 문서 | 설명 |
|------|------|
| [DESIGN.md](docs/DESIGN.md) | 시스템 아키텍처 설계 |
| [WORKFLOW.md](docs/WORKFLOW.md) | 에이전트 워크플로우 상세 |
| [API.md](docs/API.md) | API 엔드포인트 명세 |
| [AGENT_GUIDE.md](docs/AGENT_GUIDE.md) | 에이전트 사용 가이드 |

---

> 이름의 유래: `works-on-my-machine` → 배포 전에 먼저 확인했더라면? **PreFlight**가 그 답입니다.
