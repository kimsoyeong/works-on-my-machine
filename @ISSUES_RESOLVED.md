# JSON Output Refactoring - API Response 직접 반환

## 문제
- Agent가 JSON **파일**을 생성하고 Wrapper가 파일을 읽어서 API response로 변환
- 불필요한 파일 I/O 작업
- 사용자 요구: Agent가 생성한 JSON을 API response로 **직접** 반환

## 해결방법
1. **Agent 프롬프트 수정**: JSON을 stdout 또는 응답으로 직접 출력
2. **Wrapper 수정**: Agent의 응답에서 JSON 추출하여 파싱

## 구현 변경사항

### 1. Agent 프롬프트 수정 (`agents/new_agent_with_tools.py`)
**Phase 3 변경**:
```python
## Phase 3: JSON Response (CRITICAL - API depends on this!)
9. **MANDATORY - Your FINAL RESPONSE must be ONLY a JSON object**:
   - Do NOT include any text before or after the JSON
   - Do NOT wrap it in markdown code blocks
   - Just output the raw JSON object
   - Format: {"vulnerabilities": [...], "attack_scenarios": [...]}
```

**이유**: Agent가 최종 응답을 JSON으로 반환하도록 명시

### 2. Wrapper V2 생성 (`agents/new_agent_wrapper_v2.py`)
**주요 변경**:
- Agent의 `run()` 메서드가 반환한 **문자열**에서 JSON 추출
- 3가지 패턴 지원:
  1. Markdown 코드 블록: ` ```json ... ``` `
  2. JSON 객체 패턴: `{ ... "vulnerabilities" ... }`
  3. 전체 응답이 JSON인 경우

**코드**:
```python
# 응답에서 JSON 객체 추출
json_match = re.search(r'```json\s*\n(.*?)\n```', agent_response, re.DOTALL)
if json_match:
    json_str = json_match.group(1).strip()
else:
    # 마지막 { ... } 블록 찾기
    json_match = re.search(r'(\{[\s\S]*"vulnerabilities"[\s\S]*\})\s*$', agent_response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
```

### 3. API 통합 (`api/routers/analyze.py`)
```python
from agents.new_agent_wrapper_v2 import analyze_bicep  # V2 사용
```

## 장점
1. ✅ **파일 I/O 제거**: 더 이상 `security_analysis.json` 파일 생성/읽기 불필요
2. ✅ **간결한 흐름**: Agent 응답 → JSON 파싱 → API response
3. ✅ **유연성**: Markdown 코드 블록, 순수 JSON 등 다양한 형식 지원
4. ✅ **Fallback 유지**: JSON 파싱 실패 시 Markdown fallback

## 테스트 계획
1. Agent가 JSON을 올바른 형식으로 반환하는지 확인
2. Wrapper가 JSON을 정확히 추출/파싱하는지 검증
3. API endpoint에서 structured response 반환 확인

## 다음 단계
- API 테스트 실행
- Agent JSON 응답 형식 검증
- 필요시 Agent 프롬프트 미세 조정

---

# Frontend 렌더링 문제 해결

## 문제
Frontend에서 `/analyze` API 호출 후 응답을 받았지만 결과가 렌더링되지 않음

## 원인 분석

### 1. 파일 형식 검증 문제
- API가 `.bicep` 파일 형식을 허용하지 않음
- `ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}` (bicep 누락)

### 2. File Processor 미지원
- `api/common/mock_services/file_processor.py`가 `.bicep` 파일 처리 로직 없음
- Bicep 파일 업로드 시 에러 발생

### 3. Agent 프롬프트 f-string 충돌
- 프롬프트 내 `{output_path}`, `{"vulnerabilities": [...]}` 등이 Python f-string과 충돌
- `Invalid format specifier` 에러 발생

### 4. Wrapper가 AgentResponse 객체 처리 못함
- Agent의 `run()` 메서드가 `AgentResponse` 객체 반환
- Wrapper가 문자열로 처리하려다 `object of type 'AgentResponse' has no len()` 에러

### 5. Pydantic Validation 에러
- Agent가 `prerequisites`를 리스트로 생성: `['item1', 'item2']`
- API 모델은 문자열 기대: `"item1; item2"`
- `Input should be a valid string [type=string_type, input_value=[...], input_type=list]`

## 해결 방법

### 1. Bicep 파일 형식 허용 (`api/routers/analyze.py`)
```python
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bicep"}  # Bicep 추가
```

### 2. Bicep 파일 처리 로직 추가 (`api/common/mock_services/file_processor.py`)
```python
allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".bicep"}

# Bicep 파일인 경우 그대로 반환
if ext == ".bicep":
    await asyncio.sleep(0.1)
    return file_content.decode('utf-8')
```

### 3. Agent 프롬프트 f-string 충돌 수정 (`agents/new_agent_with_tools.py`)
```python
# Before
- `docker-compose -f {output_path} ps`
- Format: {"vulnerabilities": [...]}

# After
- `docker-compose -f OUTPUT_FILE ps`
- Format: {{"vulnerabilities": [...}}}  # 중괄호 이스케이프
```

### 4. AgentResponse 객체 처리 (`agents/new_agent_wrapper_v2.py`)
```python
agent_response = await convert_func(str(bicep_file), str(compose_file))

# AgentResponse 객체를 문자열로 변환
if hasattr(agent_response, 'message'):
    agent_response_text = agent_response.message
elif hasattr(agent_response, 'content'):
    agent_response_text = agent_response.content
else:
    agent_response_text = str(agent_response)
```

### 5. Prerequisites 자동 변환 (`agents/new_agent_wrapper_v2.py`)
```python
# prerequisites가 리스트인 경우 문자열로 변환
prerequisites = a.get("prerequisites", "None")
if isinstance(prerequisites, list):
    prerequisites = "; ".join(prerequisites)
```

## 테스트 결과

```bash
✅ Status: success
📊 Vulnerabilities: 10
⚡ Attack scenarios: 10

🚨 Sample Vulnerability:
   - ID: VULN-001
   - Title: Hardcoded Weak Credentials
   - Severity: CRITICAL

⚡ Sample Attack:
   - ID: ATTACK-001
   - Name: Credential Theft and Storage Takeover
   - Prerequisites: Network access to port 9000/9001; Knowledge of exposed environment variables
```

## 수정된 파일
1. `api/routers/analyze.py` - Bicep 파일 형식 허용
2. `api/common/mock_services/file_processor.py` - Bicep 파일 처리 로직
3. `agents/new_agent_with_tools.py` - f-string 충돌 수정
4. `agents/new_agent_wrapper_v2.py` - AgentResponse 처리 + prerequisites 변환

## 결과
✅ API가 정상적으로 취약점 및 공격 시나리오 반환
✅ Frontend에서 데이터 렌더링 가능한 형식으로 응답
✅ Pydantic validation 통과

---

# Agent 리포트 형식 통일 및 한국어 작성 명시

## 변경 사항

### 1. 두 Agent의 리포트 형식 통일
- `new_agent.py` (Zero-Tools Agent)
- `new_agent_with_tools.py` (With-Tools Agent)

### 2. 한국어 작성 명시적 지시
**이전:**
```
### 2. Markdown Report (write in Korean; for humans)
```

**이후:**
```
### 2. Markdown Report (MUST write in Korean; for humans)
**필수 포함 내용 (반드시 한국어로 작성):**
**중요**: Markdown 리포트는 반드시 한국어로 작성해야 합니다!
```

### 3. 표준화된 리포트 구조 제공

```markdown
# Red Team 보안 분석 리포트

## 📊 요약
- 배포된 컨테이너: X개
- 발견된 취약점: Y개 (Critical: A, High: B, Medium: C, Low: D)
- 공격 시나리오: Z개

## 🚀 Phase 1: 배포 결과
[컨테이너 목록 및 포트 정보]

## 🚨 Phase 2: Red Team 공격 결과
[수행된 공격 및 발견사항]

## 🔍 발견된 취약점
### VULN-001: [제목] (Critical/High/Medium/Low)
- **영향받는 리소스**: [리소스명]
- **설명**: [상세 설명]
- **증거**: [실제 테스트 결과]
- **개선방안**: [구체적 조치사항]

## ⚡ 공격 시나리오
### ATTACK-001: [공격명] (MITRE: T1XXX)
- **전제조건**: [필요한 접근 권한]
- **공격 단계**:
  1. [단계 1]
  2. [단계 2]
- **예상 영향**: [공격 성공 시 영향]
- **탐지 난이도**: Easy/Medium/Hard
- **발생 가능성**: High/Medium/Low

## 💡 개선 권장사항
1. **긴급 (Critical)**: [조치사항]
2. **높음 (High)**: [조치사항]
3. **중간 (Medium)**: [조치사항]

## 📝 컨테이너 관리
- 상태 확인: `docker-compose -f [파일] ps`
- 중지: `docker-compose -f [파일] down`
- 로그 확인: `docker-compose -f [파일] logs [서비스명]`
```

## 통일된 출력 형식

### JSON Output (API 통합용)
- 영어로 작성 (API 호환성)
- 표준화된 필드명
- Pydantic 스키마 준수

### Markdown Report (사람이 읽을 용도)
- **한국어로 작성** (명시적 지시)
- 동일한 구조 사용
- 이모지로 섹션 구분
- 우선순위별 개선방안 제시

## 수정된 파일
1. `agents/new_agent.py` - Zero-Tools Agent instruction 업데이트
2. `agents/new_agent_with_tools.py` - With-Tools Agent instruction 업데이트

## 기대 효과
✅ 두 Agent 모드 간 일관된 리포트 형식
✅ 한국어 리포트 작성 보장
✅ 사람이 읽기 쉬운 구조화된 리포트
✅ API와 Human-readable 출력 명확히 분리

---

# PreFlight Agent 통합 및 UI 개선 (2026-02-26)

## [FIX] PreFlight 통합 보고서 에이전트 구현

**증상**: Policy 결과와 Recon 결과를 단순 병합하는 방식으로 보안 의미가 불분명한 보고서 생성  
**원인**: 설계 의도 대비 재현 구조 분석 없이 취약점 목록만 나열  
**해결**: `agents/preflight_agent.py` 신규 구현 (MAF `AzureOpenAIChatClient` 기반)

- 6개 섹션 구조: Executive Summary → 원본 설계 의도 → 변환 구조 검토 → 보안 불일치 분석 → 잠재적 영향 → 배포 전 체크리스트 → Updated Bicep Code
- 단정 표현 금지, 조건부 표현 사용 (`If deployed without...`, `This may increase exposure to...`)
- `SecurityResult` 모델 변경: `{vulnerabilities[], attack_scenarios[], report}` → `{final_report, vulnerability_summary: int, severity_counts: dict, verification_checklist: list}`

---

## [FIX] `_run_policy() takes 1 positional argument but 2 were given`

**증상**: `POST /api/v1/analyze` 호출 시 500 오류  
**원인**: `skip_policy` 파라미터 제거 후 호출부에서 `_run_policy(bicep_code, False)` 잔존  
**해결**: `api/routers/analyze.py`에서 `_run_policy(bicep_code, False)` → `_run_policy(bicep_code)` 수정

---

## [FIX] `skip_policy` 모드 및 `zero-tools` docstring 제거

**증상**: 사용하지 않는 `skip_policy: bool` Form 파라미터와 관련 docstring이 API에 노출  
**해결**:
- `analyze_architecture()` 함수 시그니처에서 `skip_policy: bool = Form(False)` 제거
- `_run_policy()` 함수 시그니처 단순화
- docstring에서 `zero-tools` 모드 관련 설명 제거

---

## [FIX] `AnalyzeResponse`에서 `policy_result` 노출 제거

**증상**: API 응답에 내부 Policy Agent 원본 결과가 그대로 노출  
**해결**: `api/models/response.py`의 `AnalyzeResponse`에서 `policy: PolicyResult | None` 필드 제거  
**주의**: `PolicyResult` 클래스 자체는 `_run_policy()` 반환 타입으로 여전히 사용 중 → import 유지

---

## [FIX] Frontend 파이프라인에서 Preprocess 단계 제거

**증상**: `PipelineBar.tsx`에 존재하지 않는 `파일 전처리` 단계가 표시됨  
**해결**:
- `STEPS` 배열에서 `preprocessing` 노드 제거 (5노드 → 4노드 레이아웃)
- `stepMap`에서 `preprocessing`/`파일 전처리` 매핑 제거
- `redteam` 매핑 수정: `'RedTeam 분석'` → `'Recon 분석'` (백엔드 step명과 일치)
- SVG 좌표 및 연결선 재배치

---

## [FIX] 마지막 파이프라인 단계명 `Result` → `Reporting` 변경

**해결**: `PipelineBar.tsx` `STEPS` 배열에서 마지막 노드 label 수정

---

## [FIX] Policy 노드 색상 변경

**해결**: `PipelineBar.tsx`에서 Policy 노드 색상 `#8b5cf6` (보라) → `#f97316` (주황)

---

## [FIX] 앱 타이틀 변경

**해결**: `App.tsx`에서 `🛡️ Azure Security Analyzer` → `🔍 PreFlight`

---

## [FIX] `ResultSummary.tsx` - `Cannot read properties of undefined (reading 'length')`

**증상**: 분석 결과 렌더링 시 런타임 에러  
**원인**: `SecurityResult` 구조 변경 후 `security.vulnerabilities.length` 참조 잔존  
**해결**: `ResultSummary.tsx` 전면 재작성

- `security.severity_counts` (Critical/High/Medium/Low) 카드 표시
- `security.vulnerability_summary` (총 취약점 수) 표시
- Optional chaining으로 undefined 안전 처리

---

## [FIX] `ResultSummary.tsx` - `'return' outside of function` 파싱 오류

**증상**: Vite pre-transform 오류로 개발 서버 동작 불가  
**원인**: edit 과정에서 old_str 범위 미스로 기존 코드 잔존 + 새 코드 중복 삽입  
**해결**: 중복된 trailing 코드 제거

---

## [FIX] Security Report 렌더링 안 됨

**증상**: 분석 결과 탭에서 보안 보고서가 표시되지 않음  
**원인**: `ResultTabs.tsx`에서 `security?.report` 참조 유지 (`DetailModal.tsx`는 이후 미사용으로 삭제됨)
**해결**: `ResultTabs.tsx`에서 `security?.report` → `security?.final_report` 수정

---

## [FIX] `api.ts` TypeScript 타입 불일치

**증상**: Frontend 빌드 타입 에러  
**원인**: `SecurityResult` 인터페이스가 백엔드 모델 변경 전 구조 유지  
**해결**: `frontend/src/types/api.ts`의 `SecurityResult` 인터페이스 업데이트

```typescript
// Before
interface SecurityResult {
  vulnerabilities: VulnerabilityItem[];
  attack_scenarios: AttackScenarioItem[];
  vulnerability_summary: Record<string, number>;
  report: string;
}

// After
interface SecurityResult {
  final_report: string;
  vulnerability_summary: number;
  severity_counts: Record<string, number>;
  verification_checklist: string[];
}
```

---

## [IMPROVE] PreFlight 보고서 구조 개선

**변경**: Executive Summary에 주요 발견 항목 명시 및 Updated Bicep Code 섹션 추가

- Executive Summary: 숫자만 표시하던 테이블에 실제 취약점 제목 컬럼 추가
- Policy 위반 요약 테이블 추가 (규칙 ID, 심각도, 위반 내용)
- 섹션 6 신규: 🔧 Updated Bicep Code — 발견된 이슈를 반영한 개선 Bicep 코드 제시
- `max_tokens` 4096 → 6000으로 증가

## 핵심 변경사항

### 도구의 목적 재정의
**이전**: Red Team 침투 테스트 도구
**이후**: 설계 단계 보안 위험 분석 및 검증 우선순위 도구

### 보고서 컨셉 변경

| 항목 | 이전 (침투 테스트) | 이후 (설계 분석) |
|------|-----------------|---------------|
| 목적 | 실제 공격 수행 및 침투 | 설계상 위험 식별 및 조기 개선 |
| 초점 | 발견된 취약점 | 공격 가능성 평가 |
| 출력 | 공격 결과 리포트 | 보안 아키텍처 분석 보고서 |
| 대상 | 보안 담당자 | 아키텍트 + 개발자 + 보안 담당자 |
| 시점 | 배포 후 | 배포 전/설계 단계 |

## 새로운 보고서 구조

### 1. Executive Summary
- 즉시 조치 필요 항목 (Critical)
- 핵심 권장사항 Top 3
- 전체 위험 통계

### 2. 아키텍처 분석 결과
- 배포된 리소스 목록
- 네트워크 구성
- 서비스 간 관계

### 3. 보안 위험 평가 (RISK-XXX)
**이전**: VULN-001: 취약점 발견
**이후**: RISK-001: 설계상 보안 위험

**포함 내용**:
- 위험 설명 (설계상 문제점)
- 공격 가능성 (악용 방법)
- 비즈니스 영향 (예상 피해)
- 설계 개선방안:
  - 즉시: 배포 전 필수 조치
  - 단기: 1주일 내
  - 장기: 아키텍처 재설계
- 관련 기준 (CIS, OWASP, NIST)

### 4. 공격 가능성 시나리오 (SCENARIO-XXX)
**이전**: ATTACK-001: 공격 수행 결과
**이후**: SCENARIO-001: 예상 공격 시나리오

**포함 내용**:
- 공격 개요 및 목표
- 전제 조건
- 예상 공격 흐름 (다이어그램)
- 탐지 가능성 평가
- 실제 공격 사례 참조

### 5. 검증 우선순위 (NEW!)
**Phase 1: 긴급 검증 (P0 - 배포 전 필수)**
- 치명적 위험 제거
- 체크리스트 제공
- 검증 방법 및 예상 소요 시간

**Phase 2: 높은 우선순위 (P1 - 1주일 내)**
- 주요 공격 경로 차단

**Phase 3: 중간 우선순위 (P2 - 1개월 내)**
- 전체 보안 수준 향상

### 6. 설계 단계 개선사항 (NEW!)
**즉시 적용 가능 (배포 전)**:
- 문제되는 설정
- 권장 설정
- 수정된 Bicep 코드 예시

**아키텍처 재설계 고려사항**:
- Zero Trust 아키텍처 적용
- 심층 방어 전략

### 7. 위험 매트릭스 (NEW!)
```
   영향도
   ↑
High│ [HIGH]  │ [CRITICAL] │
Med │ [MED]   │ [HIGH]     │
Low │ [LOW]   │ [MED]      │
    └─────────┴────────────┴→ 발생가능성
```

### 8. 참고자료 (NEW!)
- CIS Benchmarks
- OWASP Top 10
- NIST Cybersecurity Framework
- Azure Security Baseline
- Azure Well-Architected Framework

## 용어 변경

| 이전 | 이후 |
|------|------|
| Red Team 공격 리포트 | 보안 아키텍처 분석 보고서 |
| 취약점 (Vulnerability) | 보안 위험 (Security Risk) |
| 공격 수행 (Attack Executed) | 공격 가능성 분석 (Attack Possibility) |
| 발견된 문제 (Issues Found) | 설계상 위험 (Design Risks) |
| 침투 테스트 결과 | 설계 단계 보안 평가 |

## 가치 제안 변경

**이전**: 
"배포된 시스템을 공격하여 취약점을 찾아냅니다"

**이후**: 
"설계 단계에서 보안 위험을 조기에 발견하고, 배포 전 개선하여 안전한 아키텍처를 구축합니다"

## 사용자 혜택

1. **조기 발견**: 배포 전에 보안 위험 식별
2. **비용 절감**: 배포 후 수정보다 설계 단계 수정이 저렴
3. **명확한 우선순위**: P0/P1/P2로 검증 계획 수립
4. **실행 가능한 가이드**: Bicep 코드 예시 제공
5. **컴플라이언스**: CIS, OWASP 기준 자동 매핑

## 수정된 파일
1. `agents/new_agent.py` - 보고서 템플릿 전면 개편
2. `agents/new_agent_with_tools.py` - 보고서 템플릿 전면 개편

## 결과
✅ 도구의 목적을 명확히 재정의
✅ 설계 단계에 최적화된 보고서 형식
✅ 검증 우선순위 및 실행 계획 제공
✅ 개발자와 아키텍트에게 유용한 정보 제공
✅ 컴플라이언스 및 Best Practice 자동 매핑

---

# 코드베이스 리팩토링 (2026-03-04)

## [REFACTOR] 파일명 및 모듈 구조 정리

### 파일 리네이밍
| 이전 | 이후 | 이유 |
|------|------|------|
| `agents/agent.py` | `agents/models.py` | 데이터 클래스/모델 정의 파일임을 명확히 |
| `agents/new_agent_with_tools.py` | `agents/recon_agent.py` | 역할 기반 명칭 |
| `agents/new_agent_wrapper_v2.py` | `agents/recon_agent_wrapper.py` | 역할 기반 명칭 |
| `agents/preflight_agent.py` | `agents/reporting_agent.py` | 역할 기반 명칭 |

### Deprecated 처리
- `agents/new_agent.py`, `agents/new_agent_wrapper.py` → `agents/deprecated/` 이동
- 두 파일 모두 활성 코드에서 임포트하지 않음을 확인 후 이동

---

## [REFACTOR] `AttackScenario` 클래스 개선 (`agents/models.py`)

**문제**: 실제 Azure 리소스 공격이 아닌 로컬 시뮬레이션임에도 속성명/주석이 실제 공격 수행을 암시, 중복 속성 존재

**변경**:
- `observation` + `security_interpretation` → `security_finding` 으로 통합
  - 둘 다 "시나리오 결과의 해석"으로 역할이 중복
- `raw_output` → `command_output` 으로 이름 변경
  - `executed_command`와 명확한 쌍을 이루도록
- 클래스 docstring 및 각 속성 주석 개선: 로컬 Docker 환경 시뮬레이션임을 명시
- `mitre_technique` 주석에 MITRE ATT&CK 프레임워크 설명 및 예시 추가

**연쇄 수정**:
- `agents/recon_agent.py`: 프롬프트 JSON 스키마의 필드명 업데이트
- `agents/recon_agent_wrapper.py`: `AttackScenario` 생성 시 필드명 업데이트

---

## [REFACTOR] `AttackScenarioItem` 중복 클래스 제거

**문제**: `api/models/response.py`의 `AttackScenarioItem`이 실제 API 응답에 연결되지 않은 사장된 코드

- `SecurityResult`는 `AttackScenario`(dataclass)를 사용 → `AttackScenarioItem`(Pydantic)은 미사용
- `new_agent_wrapper.py`(deprecated)가 존재하지 않는 필드로 `AttackScenario`를 생성 시도하는 버그 존재

**해결**:
- `api/models/response.py`: `AttackScenarioItem` 클래스 삭제
- `api/models/__init__.py`: export 삭제
- `frontend/src/types/api.ts`: `AttackScenarioItem` 인터페이스 삭제

---

## [REFACTOR] `VulnerabilityItem` 중복 정의 통합

**문제**: `agents/models.py`(dataclass)와 `api/models/response.py`(Pydantic BaseModel)에 동일 필드의 `VulnerabilityItem`이 두 개 존재

**해결**:
- `api/models/response.py`의 Pydantic 버전 삭제
- `api/models/__init__.py`에서 `agents.models`의 dataclass를 직접 임포트
- 단일 소스(`agents/models.py`)로 통합

---

## [FEAT] Recon 공격 시나리오를 통합 보고서(reporting_agent)에 포함

**문제**: `reporting_agent.py`가 recon 취약점(`recon_vulnerabilities`)만 전달받고 공격 시나리오(`attack_scenarios`)는 전달받지 못해 통합 보고서에서 누락

**해결**:
- `api/routers/analyze.py`: `dataclasses.asdict()`로 attack scenarios를 dict 변환 후 전달
- `agents/reporting_agent.py`:
  - `generate_report()` 파라미터에 `recon_attack_scenarios: list[dict]` 추가
  - 프롬프트 입력에 `RECON ATTACK SCENARIOS` 섹션 추가 (각 필드 설명 포함)
  - 보고서 템플릿에 `🎯 시뮬레이션 기반 검증 결과` 섹션 삽입 (섹션 3 직후)
  - fallback 보고서에도 동일 섹션 추가

---

## [REFACTOR] `reporting_agent.py` 프롬프트 이중화 제거

**문제**: `REPORTING_AGENT_INSTRUCTIONS`(system)과 `prompt`(user) 양쪽에 보고서 포맷 템플릿이 중복 존재하며 섹션 구조도 서로 달라 충돌

- Instructions: 7섹션 Korean 구조
- Prompt: 6섹션 + 공격 시나리오 섹션 (다른 구조)

**해결**:
- `REPORTING_AGENT_INSTRUCTIONS`: 역할 + 제약 + 언어 규칙 + JSON 출력 스펙만 유지 (~40줄로 축소)
- `prompt`: 입력 데이터 + 단일 포맷 템플릿 (공격 시나리오 섹션 포함)

---

## [REFACTOR] 내부 변수명 통일

### `agents/reporting_agent.py` (구 `preflight_agent.py`)
- `PREFLIGHT_AGENT_INSTRUCTIONS` → `REPORTING_AGENT_INSTRUCTIONS`
- `generate_preflight_report()` → `generate_report()`
- `PreFlightReportAgent` → `ReportingAgent`

### `agents/recon_agent.py` (구 `new_agent_with_tools.py`)
- `AGENT_INSTRUCTIONS` → `RECON_AGENT_INSTRUCTIONS`
- 파일 상단 docstring 업데이트
- CLI usage 메시지의 구 파일명 참조 수정

### `agents/recon_agent_wrapper.py` (구 `new_agent_wrapper_v2.py`)
- `invoke_recon_agent as with_tools_convert` → `invoke_recon_agent` (불필요한 alias 제거)
- 파일 상단 docstring 업데이트

---

## [FEAT] 프론트엔드 타입 동기화 (`frontend/src/types/api.ts`)

**문제**: 백엔드 `SecurityResult`에 `attack_scenarios` 필드가 추가됐으나 프론트엔드 타입에 미반영

**해결**:
- `AttackScenario` 인터페이스 추가 (백엔드 dataclass 필드와 일치)
- `SecurityResult`에 `attack_scenarios: AttackScenario[]` 추가

---

# 프론트엔드 UI 전면 리디자인 (2026-03-07)

## [FEAT] 디자인 시스템 구축

- 인라인 스타일 + CSS Custom Properties(`--pf-*`) 기반 테마 시스템
- 보라색 (`#6C3AED`) 앱 액센트, 페이지 배경 `#f8f9fb`
- 타이포그래피: Outfit (제목), DM Sans (본문), DM Mono/JetBrains Mono (코드)

## [FEAT] 화면 플로우 3단계 구현 (`MainContent.tsx`)

**idle → analyzing → completed** 화면 전환 (Framer Motion 애니메이션)

### Idle 화면
- 히어로 섹션: 레이더 로고 + "아키텍처 보안 검증" 타이틀
- `UploadCard`: Claude 스타일 채팅 입력 카드 (드래그&드롭, 이미지 미리보기, 스캔라인 오버레이)

### Analyzing 화면 (`AnalyzingProgress`)
- 레이더 sweep 애니메이션 히어로
- 5단계 수직 타임라인 (세로선 연결)
- `StepIcon`: 상태별 아이콘 + 단계별 고유 아이콘
  - 아키텍처 업로드: ↑ 업로드 화살표
  - IaC 템플릿 변환: `</>` 코드 브래킷
  - 보안 정책 검증 / 위협 시나리오 정찰: 🤖 로봇 (AI 에이전트)
  - 보고서 생성: 📄 문서
- 병렬 실행 그룹 박스 (보안 정책 검증 + 위협 시나리오 정찰)
- 전체 진행률 바 + 단계 라벨
- 업로드 완료 시 이미지 미리보기 토글

### Completed 화면
- 파이프라인 미니맵 → 결과 대시보드 → 상세 보고서 탭

## [FEAT] 파이프라인 미니맵 리디자인 (`PipelineBar.tsx`)

**이전**: SVG 이모지 노드 기반 레이아웃
**이후**: 미니멀 HTML 칩 레이아웃

- `StepChip`: 28×28px 아이콘 박스 + 라벨 (상태별 색상, 단계별 고유 아이콘)
- `Arrow`: SVG 화살표 커넥터 (40×10px)
- Fork/Merge SVG 분기·합류선 (병렬 단계용)
- 경과 시간: `position: absolute` 우측 배치, 파이프라인은 정중앙
- 둥근 카드 (`borderRadius: 14px`) 안에 배치

## [FEAT] 보안 대시보드 (`ResultSummary.tsx`)

5개 카드 그리드 (3열 × 2행):

| 카드 | 내용 |
|------|------|
| 보안 등급 (2행 span) | A~F 등급, 270° 아크 게이지 차트, 등급 기준 hover 팝오버 |
| 정책 위반 | 위반/권고 건수, 컬러 비율 바 |
| 발견 취약점 | Critical/High/Medium/Low 분포 바 |
| 위협 시나리오 | 침투 성공/부분/차단 분류 |
| 아키텍처 재현율 | 퍼센트 + 카테고리별 진행 바 |

- 재검증 시 이전 결과 대비 델타(↑↓) `DeltaPill` 표시
- 경고 배너: score < 60 또는 Critical/High 취약점 존재 시 자동 표시
- "상세 보기 >" 클릭 → 해당 보고서 서브탭으로 자동 스크롤

**보안 등급 산정**: 정책 준수 65점 + 취약점 35점 × 재현 신뢰도, 100점 정규화

## [FEAT] 상세 보고서 탭 (`ResultTabs.tsx`)

메인 탭: 📋 보고서 / ⚙ 개선된 Bicep

보고서 6개 서브탭:
- 정책 준수 검토: 위반/권고 테이블
- 보안 통제 검토: 통제 항목별 적용 여부 (✓/✗/◐)
- 취약점 우선순위: 심각도 필터 pill + 취약점 테이블
- 위협 시뮬레이션: 공격 결과 테이블 + 분석 결론 마크다운
- 아키텍처 재현: Docker 재현 테이블 + 재현 점수 상세
- 검증 체크리스트: 항목별 통과/수정필요 상태

Bicep 탭: 구문 하이라이팅 (react-syntax-highlighter/oneDark), 접기/펼치기, "개선된 Bicep으로 재검증" 버튼

## [FEAT] 헤더 상태 표시 (`App.tsx`)

- `analyzing` 상태: "에이전트 실행 중" 펄스 배지 + 경과 시간 + "분석 취소" 버튼
- `completed` 상태: "＋ 새 분석" 버튼
- Ambient 배경: 그라데이션 원형 + 도트 그리드 패턴

## [FEAT] Zustand 스토어 확장 (`store/app.ts`)

- `previousResult`: 재검증 시 이전 결과 저장 (델타 비교용)
- `elapsedSeconds`: 분석 완료 시 소요 시간 기록
- `reportSection`: 보고서 활성 서브탭 상태

## [FEAT] API 타입 확장 (`types/api.ts`)

- `PolicyViolation`, `VulnerabilityItem`, `ResourceReproduction` 인터페이스 추가
- `SecurityResult`: `reproduction_details`, `resource_reproduction`, `vulnerabilities`, `simulation_conclusion` 필드 추가
- `PolicySummary`: `violation_details`, `recommendation_details` 필드 추가

---

# 백엔드 API 응답 구조 고도화 (2026-03-07)

## [FEAT] 응답 모델 필드 확장 (`api/models/response.py`)

- `SecurityResult`에 프론트엔드 대시보드용 필드 추가:
  - `reproduction_details: dict` — 리소스/보안통제/네트워크 재현 세부 점수
  - `resource_reproduction: list[dict]` — 리소스별 Docker 재현 현황
  - `vulnerabilities: list[dict]` — 개별 취약점 상세 목록
  - `simulation_conclusion: str` — 공격 시뮬레이션 분석 결론
- `PolicySummary`에 상세 데이터 필드 추가:
  - `violation_details: list[dict]` — 위반 상세 목록
  - `recommendation_details: list[dict]` — 권고 상세 목록

## [FEAT] .bicep 파일 passthrough (`api/common/services/bicep_transformer.py`)

**문제**: 재검증 시 개선된 Bicep 코드를 다시 업로드하면 이미지→Bicep 변환을 시도
**해결**: `.bicep` 확장자 파일은 변환 건너뛰고 내용 그대로 반환

## [REFACTOR] 보고서 에이전트 개선 (`agents/reporting_agent.py`)

### 프롬프트 개선
- JSON 출력 형식 명세 추가 (`final_report` + `structured_data` 키)
- "위험 우선순위" → "취약점 우선순위" 용어 통일
- CVSS 등급 기준표를 섹션 5로 이동 (섹션 1 Executive Summary에서 제거)
- "Overall Architecture Reproduction Fidelity" → "전체 아키텍처 재현율"
- `max_tokens` 8000 → 16000 상향

### 파싱 개선
- `_parse_json_response`: `structured_data` 키 보장, top-level 필드 폴백
- `_extract_checklist_from_markdown`: 마크다운 테이블 형식 파싱 지원 추가
- `_fallback_report`에 `structured_data` 기본값 포함
- 불필요한 텍스트 길이 경고 로그 제거

## [FEAT] 보고서 데이터 추출 및 응답 빌더 (`api/routers/analyze.py`)

- `.bicep` 파일 업로드 허용 (`ALLOWED_EXTENSIONS`에 추가)
- 보고서 마크다운에서 구조화 데이터 추출하는 함수 신규:
  - `_extract_reproduction_details()`: 재현 세부 점수 (리소스/보안통제/네트워크)
  - `_extract_resource_reproduction()`: 리소스별 Docker 재현 테이블 파싱
  - `_extract_simulation_conclusion()`: 시뮬레이션 결과 해석 텍스트
- `_build_security_result()` 헬퍼: `structured_data` 우선, regex fallback
- `PolicySummary` 응답에 `violation_details`, `recommendation_details` 포함
- REST(`/analyze`)·SSE(`/analyze/stream`) 양쪽 엔드포인트에 동일 적용

---

# 기타 (2026-03-07)

## [CHORE] `.gitignore` 정리

- `node_modules/`, `.vite/` 추가 (프론트엔드 빌드 캐시)
- `.claude/`, `.github/`, `nginx-config/` 추가
- `ssl_certs/` 중복 제거

## [DOCS] `FRONTEND.md` 현행화

- 기술 스택: 실제 사용 라이브러리 반영 (Framer Motion, react-markdown 등)
- 디렉토리 구조, 컴포넌트 상세, 화면 플로우 ASCII 레이아웃
- 디자인 시스템: 컬러 팔레트, 타이포그래피, CSS 토큰, 애니메이션 목록
- API 통신: SSE 이벤트 타입, Zustand 상태 인터페이스
