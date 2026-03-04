"""
PreFlight 통합 보안 보고서 Agent

Policy 검증 결과 + Recon 분석 결과를 "설계 의도 관점"에서
통합 해설 보고서로 생성한다.

Microsoft Agent Framework(AzureOpenAIChatClient) 기반.
"""

import json
import logging
import os
import re

from agent_framework.azure import AzureOpenAIChatClient

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Agent Instructions
# ─────────────────────────────────────────────────────────────

REPORTING_AGENT_INSTRUCTIONS = """
You are a PreFlight Architecture Security Integrity Agent.

MISSION:
원본 Azure Bicep 아키텍처와 변환/재구성된 구조 간의
보안 통제 무결성(Control Integrity)을 설계 관점에서 분석한다.
Policy 위반과 Recon 결과를 통합하여 설계 의도 보존 여부를 평가한다.

IMPORTANT CONSTRAINTS:
- 실제 침투 테스트를 수행하지 않는다.
- 실제 공격 성공 여부를 단정하지 않는다.
- 설계 수준(Control Design Level) 분석만 수행한다.
- 모든 위험 서술은 반드시 조건부 표현을 사용한다.
- 단정형 공격 표현(“침투 가능”, “공격 성공”, “익스플로잇 가능”) 금지.

CONDITIONAL LANGUAGE RULE:
위험 문장은 다음 형식 중 하나를 반드시 포함해야 한다:
- “If deployed without equivalent controls...”
- “In the absence of...”
- “This may increase exposure to...”
- “Could potentially allow...”

LANGUAGE: 한국어. 조건부 위험 문장 내부에서만 영어 허용.

OUTPUT: 반드시 유효한 JSON만 반환한다. 마크다운 코드펜스나 추가 설명 금지.

JSON FORMAT:
{
  "final_report": "<전체 한국어 Markdown 보고서>",
  "vulnerability_summary": <int>,
  "verification_checklist": ["항목1", "항목2", ...]
}

INTERNAL RULES (DO NOT PRINT):
- placeholder 금지 — 모든 섹션을 실제 분석 내용으로 채울 것
- vulnerability_summary = recon_vulnerabilities 총 개수
- verification_checklist = 섹션 5의 항목을 문자열 배열로만 추출
- JSON 외 텍스트 출력 금지
- 조건부 문장 규칙 위반 시 보고서 전체를 무효로 간주
"""

# ─────────────────────────────────────────────────────────────
# Main Agent Function
# ─────────────────────────────────────────────────────────────


async def generate_report(
    bicep_code: str,
    policy_violations: list[dict],
    policy_recommendations: list[dict],
    recon_vulnerabilities: list[dict],
    recon_attack_scenarios: list[dict],
    recon_report: str,
) -> dict:
    """
    PreFlight 통합 보고서 생성 (MAF AzureOpenAIChatClient 기반)

    Args:
        bicep_code: 원본 Bicep 코드
        policy_violations: Policy 위반 목록
        policy_recommendations: Policy 권장 목록
        recon_vulnerabilities: Recon 취약점 목록 (list of dict)
        recon_attack_scenarios: Recon 시뮬레이션 공격 시나리오 목록 (list of dict)
        recon_report: Recon 에이전트가 생성한 보고서 텍스트

    Returns:
        {
            "final_report": str,        # 통합 해설 보고서 (Markdown)
            "vulnerability_summary": int,
            "verification_checklist": list[str],
        }
    """
    vuln_count = len(recon_vulnerabilities)
    attack_count = len(recon_attack_scenarios)

    # severity 분포 사전 계산 (프롬프트에 명시적으로 제공)
    severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for v in recon_vulnerabilities:
        sev = v.get("severity", "Medium")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    violations_text = json.dumps(policy_violations, ensure_ascii=False, indent=2)
    recommendations_text = json.dumps(
        policy_recommendations, ensure_ascii=False, indent=2
    )
    vuln_text = json.dumps(recon_vulnerabilities, ensure_ascii=False, indent=2)
    attack_text = json.dumps(recon_attack_scenarios, ensure_ascii=False, indent=2)

    prompt = f"""
다음 입력 데이터를 분석하여 PreFlight 통합 보안 보고서를 생성하십시오.

========== ORIGINAL BICEP CODE ==========
{bicep_code[:8000]}

========== POLICY VIOLATIONS ({len(policy_violations)}) ==========
{violations_text[:3000]}

========== POLICY RECOMMENDATIONS ({len(policy_recommendations)}) ==========
{recommendations_text[:2000]}

========== RECON VULNERABILITIES ({vuln_count}) ==========
{vuln_text[:3000]}

========== RECON ATTACK SCENARIOS ({attack_count}) ==========
Each entry represents a simulated attack scenario run against a local Docker container
that replicates an Azure resource. Fields:
- id: scenario identifier (SCN-XXX)
- mitre_technique: MITRE ATT&CK technique ID
- severity: risk level if scenario succeeds
- container: target container name
- objective: attack goal
- executed_command: command used in simulation
- command_output: output from the command
- security_finding: combined observation and security interpretation
{attack_text[:3000]}

========== PREVIOUS RECON REPORT (excerpt) ==========
{recon_report[:2000]}


============================================================
REPORT FORMAT (STRICT TEMPLATE)
============================================================

아래 형식을 엄수하여 PreFlight 통합 보안 보고서를 작성하시오. placeholder 금지 — 모든 섹션을 실제 분석 내용으로 채울 것.

# 🔍 PreFlight 통합 보안 보고서

## 📊 Executive Summary

### 심각도별 발견 현황

| 등급 | 건수 | 주요 발견 항목 |
|------|------|----------------|
| 🔴 Critical | {severity_counts['Critical']} | (Critical 취약점 제목들을 콤마로 나열, 없으면 "-") |
| 🔶 High     | {severity_counts['High']}     | (High 취약점 제목들을 콤마로 나열, 없으면 "-") |
| 🔷 Medium   | {severity_counts['Medium']}   | (Medium 취약점 제목들을 콤마로 나열, 없으면 "-") |
| 🟢 Low      | {severity_counts['Low']}      | (Low 취약점 제목들을 콤마로 나열, 없으면 "-") |

### Policy 위반 요약

| # | 규칙 ID | 심각도 | 위반 내용 (요약) |
|---|---------|--------|-----------------|
(policy_violations 각 항목 — rule, severity, message 요약 1줄씩 실제 내용으로 채울 것)

### 핵심 보안 이슈

가장 중요한 보안 위험을 2~4줄로 구체적으로 요약. 어떤 리소스에서 어떤 설정 문제가 있는지 언급할 것.

---

## 1. 🏛️ Original Architecture Security Intent

원본 Bicep 코드에서 의도된 보안 설계를 항목별로 평가합니다.

| 보안 통제 항목 | Bicep 설정값 / 의도 | 평가 |
|----------------|---------------------|------|
| Key Vault networkAcls defaultAction | (실제 값 또는 미설정) | ✅/⚠️/❌ |
| Storage allowBlobPublicAccess | (실제 값 또는 미설정) | ✅/⚠️/❌ |
| TLS 최소 버전 | (실제 값 또는 미설정) | ✅/⚠️/❌ |
| HTTPS Only | (실제 값 또는 미설정) | ✅/⚠️/❌ |
| Private Endpoint | (사용 여부) | ✅/⚠️/❌ |
| Private DNS Zone | (사용 여부) | ✅/⚠️/❌ |
| Soft Delete + Purge Protection | (활성화 여부) | ✅/⚠️/❌ |

(각 행의 설정값과 평가를 실제 Bicep 코드 분석 결과로 채울 것)

---

## 2. 🔄 Reconstructed / Transformed Structure Review

변환 과정(Bicep → Docker Compose 등)에서 각 보안 통제의 유지 여부를 평가합니다.

| 원본 보안 통제 | 변환 후 상태 | 위험도 | 비고 |
|----------------|-------------|--------|------|
| Key Vault networkAcls | 유지/약화/미적용 | 🔴/🔶/🔷/🟢 | (구체적 이유) |
| Storage 공용 접근 차단 | 유지/약화/미적용 | 🔴/🔶/🔷/🟢 | (구체적 이유) |
| TLS 1.2 강제 | 유지/약화/미적용 | 🔴/🔶/🔷/🟢 | (구체적 이유) |
| HTTPS Only | 유지/약화/미적용 | 🔴/🔶/🔷/🟢 | (구체적 이유) |
| Private Endpoint | 유지/약화/미적용 | 🔴/🔶/🔷/🟢 | (구체적 이유) |
| Soft Delete / Purge Protection | 유지/약화/미적용 | 🔴/🔶/🔷/🟢 | (구체적 이유) |

(각 행을 실제 변환 결과 분석으로 채울 것)

---

## 3. ⚠️ Design-Level Security Mismatch Analysis

설계 수준 보안 불일치를 항목별로 분석합니다.
**⚠️ 모든 항목은 반드시 조건부 표현으로 작성할 것.**

### MSM-001: [불일치 제목 — 실제 분석 기반]
- **영향 영역**: 네트워크 격리 / 접근 제어 / 암호화 / 기타
- **원본 의도**: 원본 설계에서 의도한 통제 내용
- **변환 후 상태**: 변환 이후 통제 상태
- **불일치 설명**: If deployed without equivalent controls, this may increase exposure to...
- **위험 등급**: 🔴 Critical / 🔶 High / 🔷 Medium / 🟢 Low

(policy violations와 recon vulnerabilities 기반으로 실제 불일치 항목 반복 작성)

---

## 🎯 시뮬레이션 기반 검증 결과

로컬 Docker 환경에서 수행된 공격 시나리오 시뮬레이션 결과입니다.
실제 Azure 리소스에 대한 공격이 아닌, 동등한 구성을 로컬에 재현하여 설계 취약점을 확인한 결과입니다.

| ID | MITRE 기법 | 대상 컨테이너 | 위험도 | 목표 | 보안 발견 사항 |
|----|-----------|--------------|--------|------|----------------|
(recon_attack_scenarios의 각 항목을 한 행씩 채울 것. 시나리오가 없으면 "| - | - | - | - | - | 시뮬레이션 결과 없음 |" 한 행 작성)

시나리오가 있는 경우, 각 항목에 대해 아래 형식으로 상세 서술할 것:

### SCN-XXX: [objective 내용]
- **MITRE**: (mitre_technique)
- **대상**: (container)
- **위험도**: 🔴/🔶/🔷/🟢
- **보안 발견**: (security_finding — 조건부 표현 사용)

---

## 4. 💥 Potential Security Impact

잠재적 보안 영향을 조건부로 설명합니다.

### P0 — 즉시 검토 필요
- (Critical/High 항목 기반, If deployed without... 형식으로 구체적 작성)

### P1 — 단기 검토 권고
- (Medium 항목 기반, In the absence of... 형식으로 구체적 작성)

### P2 — 구조적 개선 권고
- (설계 구조 개선이 필요한 항목, Could potentially allow... 형식으로 작성)

---

## 5. ✅ Recommended Verification Checklist

배포 전 반드시 확인해야 할 항목입니다.

1. (구체적 확인 항목 — 실제 발견 이슈 기반)
2. (구체적 확인 항목)
3. ...
(최소 7개, 개발자가 직접 점검 가능하도록 구체적으로 작성)

---

## 6. 🔧 Updated Bicep Code

아래는 위에서 식별된 **Policy 위반 및 취약점을 반영하여 개선한 Bicep 코드**입니다.

### 주요 변경 사항

| # | 변경 항목 | 변경 내용 |
|---|-----------|-----------|
| 1 | (변경 항목명) | (원본 → 개선 내용 요약) |
| 2 | (변경 항목명) | (원본 → 개선 내용 요약) |
(실제 변경된 항목들 작성)

### 개선된 Bicep 코드

```bicep
(원본 Bicep 코드에서 모든 보안 이슈를 수정한 완전한 코드 — placeholder 없이 실제 코드 작성)
```

> ⚠️ 위 코드는 설계 의도 기반 개선 제안입니다. 실제 배포 전 인프라 환경에 맞게 검토 및 수정하여 사용하십시오.

---

Return ONLY valid JSON (no markdown code fence, no extra text):
{{
  "final_report": "...(full Markdown report in Korean)...",
  "vulnerability_summary": {vuln_count},
  "verification_checklist": ["항목 1", "항목 2", ...]
}}
"""

    try:
        client = AzureOpenAIChatClient(
            endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        )
        agent = client.as_agent(
            name="ReportingAgent",
            instructions=REPORTING_AGENT_INSTRUCTIONS,
            temperature=0.3,
            max_tokens=6000,
        )
    except Exception as e:
        logger.error(f"❌ Reporting agent 초기화 실패: {e}", exc_info=True)
        return _fallback_report(
            policy_violations, recon_vulnerabilities, recon_attack_scenarios, vuln_count
        )

    try:
        result = await agent.run(prompt)
        agent_response_text = (result.text or "").strip()
        logger.info("✅ Reporting agent 실행 완료")
    except Exception as e:
        logger.error(f"❌ Reporting agent 실행 실패: {e}", exc_info=True)
        return _fallback_report(
            policy_violations, recon_vulnerabilities, recon_attack_scenarios, vuln_count
        )

    parsed = _parse_json_response(agent_response_text)
    if parsed:
        logger.info(
            f"✅ PreFlight report 파싱 완료: "
            f"vuln_summary={parsed.get('vulnerability_summary')}, "
            f"checklist={len(parsed.get('verification_checklist', []))}개 항목"
        )
        return parsed

    logger.warning("⚠️ Reporting agent: JSON 파싱 실패, fallback 사용")
    return _fallback_report(
        policy_violations, recon_vulnerabilities, recon_attack_scenarios, vuln_count
    )


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def _parse_json_response(text: str) -> dict | None:
    """Agent 응답 텍스트에서 JSON 파싱 시도"""
    # ```json ... ``` 블록
    m = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # final_report 키를 포함하는 JSON 객체
    m = re.search(r'(\{[\s\S]*"final_report"[\s\S]*\})\s*$', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 전체 텍스트가 JSON인 경우
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _fallback_report(
    policy_violations: list[dict],
    recon_vulnerabilities: list[dict],
    recon_attack_scenarios: list[dict],
    vuln_count: int,
) -> dict:
    """Agent 실패 시 기본 보고서 생성"""
    violation_rows = (
        "\n".join(
            f"| {i+1} | {v.get('rule', '-')} | {v.get('severity', '-')} | {v.get('message', '')[:60]} |"
            for i, v in enumerate(policy_violations)
        )
        or "| - | - | - | 위반 없음 |"
    )

    vuln_lines = (
        "\n".join(
            f"- [{v.get('severity', 'Medium')}] {v.get('title', v.get('description', ''))}"
            for v in recon_vulnerabilities
        )
        or "- 발견된 취약점 없음"
    )

    attack_table_rows = (
        "\n".join(
            f"| {s.get('id', '-')} | {s.get('mitre_technique', '-')} "
            f"| {s.get('container', '-')} | {s.get('severity', '-')} "
            f"| {s.get('objective', '-')[:60]} | {s.get('security_finding', '-')[:80]} |"
            for s in recon_attack_scenarios
        )
        or "| - | - | - | - | - | 시뮬레이션 결과 없음 |"
    )

    severity_counts: dict[str, int] = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for v in recon_vulnerabilities:
        sev = v.get("severity", "Medium")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    critical_titles = (
        ", ".join(
            v.get("title", "")
            for v in recon_vulnerabilities
            if v.get("severity") == "Critical"
        )
        or "-"
    )
    high_titles = (
        ", ".join(
            v.get("title", "")
            for v in recon_vulnerabilities
            if v.get("severity") == "High"
        )
        or "-"
    )
    medium_titles = (
        ", ".join(
            v.get("title", "")
            for v in recon_vulnerabilities
            if v.get("severity") == "Medium"
        )
        or "-"
    )

    checklist = [
        "Key Vault 접근 정책 및 networkAcls defaultAction=Deny 설정 확인",
        "Storage 계정 allowBlobPublicAccess=false 확인",
        "TLS 최소 버전 1.2 강제 설정 확인",
        "HTTPS Only 설정 확인",
        "Private Endpoint 또는 동급 네트워크 격리 구성 확인",
        "Private DNS Zone 연결 구성 확인",
        "Soft Delete 및 Purge Protection 활성화 확인",
        "인증 및 권한 부여 메커니즘 배포 전 검증",
        "배포 환경의 네트워크 NSG/방화벽 규칙 검토",
    ]

    final_report = f"""# 🔍 PreFlight 통합 보안 보고서

## 📊 Executive Summary

### 심각도별 발견 현황

| 등급 | 건수 | 주요 발견 항목 |
|------|------|----------------|
| 🔴 Critical | {severity_counts['Critical']} | {critical_titles} |
| 🔶 High     | {severity_counts['High']}     | {high_titles} |
| 🔷 Medium   | {severity_counts['Medium']}   | {medium_titles} |
| 🟢 Low      | {severity_counts['Low']}      | - |

### Policy 위반 요약

| # | 규칙 ID | 심각도 | 위반 내용 |
|---|---------|--------|-----------|
{violation_rows}

### 핵심 보안 이슈

보안 분석 에이전트 응답 실패로 인해 자동 요약이 생성되지 않았습니다.
아래 취약점 목록과 정책 위반 항목을 직접 확인하십시오.

---

## 1. 🏛️ Original Architecture Security Intent

원본 Bicep 코드 기반 보안 설계 의도를 분석합니다.

| 보안 통제 항목 | Bicep 설정값 / 의도 | 평가 |
|----------------|---------------------|------|
| Key Vault networkAcls defaultAction | Deny | ⚠️ 확인 필요 |
| Storage allowBlobPublicAccess | false | ⚠️ 확인 필요 |
| TLS 최소 버전 | TLS1_2 | ⚠️ 확인 필요 |
| HTTPS Only | true | ⚠️ 확인 필요 |
| Private Endpoint | 사용 여부 미확인 | ⚠️ 확인 필요 |
| Private DNS Zone | 사용 여부 미확인 | ⚠️ 확인 필요 |
| Soft Delete + Purge Protection | 활성화 여부 미확인 | ⚠️ 확인 필요 |

---

## 2. 🔄 Reconstructed / Transformed Structure Review

Bicep → Docker Compose 변환 과정에서 보안 통제 유지 여부를 검토합니다.

| 원본 보안 통제 | 변환 후 상태 | 위험도 | 비고 |
|----------------|-------------|--------|------|
| Key Vault networkAcls | 미확인 | 🔶 | Docker 네트워크 정책으로 대응 필요 |
| Storage 공용 접근 차단 | 미확인 | 🔶 | 컨테이너 볼륨 권한 설정으로 대응 필요 |
| TLS 1.2 강제 | 미확인 | 🔶 | 컨테이너 서비스 TLS 설정으로 대응 필요 |
| Private Endpoint | 미확인 | 🔴 | 내부 Docker 네트워크로 대응 필요 |
| Soft Delete / Purge Protection | 미적용 | 🔷 | 클라우드 전용 기능 — 대응 구조 부재 가능성 |

---

## 3. ⚠️ Design-Level Security Mismatch Analysis

**Policy 위반 항목:**
{vuln_lines}

If deployed without equivalent network isolation controls, the following design-level gaps may apply.
In the absence of Private Endpoint equivalent configurations, public exposure potential may increase.
This may increase exposure to unauthorized network access if whitelist-based access controls are not replicated.

---

## 🎯 시뮬레이션 기반 검증 결과

로컬 Docker 환경에서 수행된 공격 시나리오 시뮬레이션 결과입니다.
실제 Azure 리소스에 대한 공격이 아닌, 동등한 구성을 로컬에 재현하여 설계 취약점을 확인한 결과입니다.

| ID | MITRE 기법 | 대상 컨테이너 | 위험도 | 목표 | 보안 발견 사항 |
|----|-----------|--------------|--------|------|----------------|
{attack_table_rows}

---

## 4. 💥 Potential Security Impact

### P0 — 즉시 검토 필요
- If deployed without equivalent access control mechanisms, this may increase exposure to unauthorized data access.

### P1 — 단기 검토 권고
- In the absence of TLS enforcement, encrypted transport cannot be guaranteed.

### P2 — 구조적 개선 권고
- Could potentially allow unintended lateral movement if network segmentation is not replicated.

---

## 5. ✅ Recommended Verification Checklist

1. Key Vault 접근 정책 및 networkAcls defaultAction=Deny 설정 확인
2. Storage 계정 allowBlobPublicAccess=false 확인
3. TLS 최소 버전 1.2 강제 설정 확인
4. HTTPS Only 설정 확인
5. Private Endpoint 또는 동급 네트워크 격리 구성 확인
6. Private DNS Zone 연결 구성 확인
7. Soft Delete 및 Purge Protection 활성화 확인
8. 인증 및 권한 부여 메커니즘 배포 전 검증
9. 배포 환경의 네트워크 NSG/방화벽 규칙 검토

---

## 6. 🔧 Updated Bicep Code

> ⚠️ 에이전트 응답 실패로 인해 자동 개선 코드가 생성되지 않았습니다.
> 위 체크리스트를 참고하여 원본 Bicep 코드를 수동으로 검토하십시오.

---
"""

    return {
        "final_report": final_report,
        "vulnerability_summary": vuln_count,
        "verification_checklist": checklist,
    }
