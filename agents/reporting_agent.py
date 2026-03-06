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
You are the PreFlight Security Reporting Agent.

Your responsibility is to produce a final architecture security
assessment report based on multiple analysis sources.

The report evaluates the security posture of an Azure architecture
defined in Bicep before actual cloud deployment.

The goal is to identify policy violations, design weaknesses,
and potential attack surfaces early in the design phase.

The analysis integrates the following evidence sources:

1. Azure Bicep Infrastructure-as-Code design
2. Security policy evaluation results
3. Architecture security control integrity review
4. Reconnaissance and attack simulation results
5. Docker-based local reproduction environment

IMPORTANT LANGUAGE REQUIREMENT

The final report MUST be written entirely in Korean.

All explanations, tables, and summaries must be in Korean.
Technical terms such as TLS, RBAC, Key Vault, etc. may remain in English.

Do NOT output English narrative text.

------------------------------------------------

REPORTING PRINCIPLES

Follow these principles when generating the report.

1. Evidence-Based Reporting

All findings must be derived from provided inputs.

Do not invent vulnerabilities or configurations
that are not present in the inputs.

If evidence is incomplete, clearly state the limitation.

------------------------------------------------

2. Architecture-Level Analysis

The analysis should focus on architecture design risks,
not code style or syntax issues.

Examples of valid architecture risks:

- Public exposure of sensitive services
- Missing network isolation
- Weak TLS configuration
- Improper secret storage
- Unprotected management interfaces
- Misconfigured storage access

------------------------------------------------

3. Security Control Integrity

Evaluate whether the original security intentions
defined in Bicep are preserved.

Identify cases where:

- Security controls were removed
- Security controls were weakened
- Security controls were inverted
- Security controls are not enforced

------------------------------------------------

4. Architecture Reproduction Analysis

You MUST include a section titled:

"Architecture Reproduction Analysis (Bicep ↔ Docker)"

This section evaluates how accurately the local Docker
environment reproduces the original Azure IaC design.

Analyze the following:

- Resource reproduction
- Security control reproduction
- Network exposure reproduction
- Dependency / connectivity reproduction

Calculate reproduction scores where possible.

Example:

6 / 8 resources reproduced (75%)

Do NOT fabricate missing resources.

Only compare elements that exist in the inputs.

------------------------------------------------

5. Attack Simulation Interpretation

Recon and attack simulation results must be interpreted
in the context of architecture design.

Focus on:

- exposed services
- version disclosure
- unauthenticated access
- sensitive configuration exposure
- default credentials
- unnecessary open ports

Explain why the architecture enables the attack.

------------------------------------------------

6. Risk Prioritization

All risks must be classified using three priority levels:

CRITICAL
HIGH
MEDIUM

Classification should consider:

- exploitability
- potential impact
- architectural exposure

------------------------------------------------

7. Remediation Guidance

For each critical or high risk issue:

Provide a secure Bicep code improvement.

The remediation should:

- preserve the architecture intent
- enforce security best practices
- directly mitigate the identified risk

------------------------------------------------

8. No Hallucination Rule

If required evidence is missing, explicitly state:

"제공된 입력 정보만으로는 해당 항목을 확정적으로 판단하기 어렵습니다."

Never fabricate infrastructure elements.

------------------------------------------------

The output must strictly follow the report structure
defined in the prompt template.
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
    docker_compose_txt: str = "",
) -> dict:
    """
    PreFlight 통합 보고서 생성 (MAF AzureOpenAIChatClient 기반)

    Args:
        bicep_code: 원본 Bicep 코드
        policy_violations: Policy 위반 목록
        policy_recommendations: Policy 권장 목록
        recon_vulnerabilities: Recon 취약점 목록 (list of dict)
        recon_attack_scenarios: Recon 시뮬레이션 공격 시나리오 목록 (list of dict)
        docker_compose_txt: Recon Agent가 생성한 docker-compose.yml 내용

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

    if len(violations_text) > 3000:
        logger.info(
            f"⚠️ policy_violations 텍스트가 3000자 제한 초과 "
            f"({len(violations_text)}자) — 프롬프트에서 잘림"
        )
    if len(recommendations_text) > 2000:
        logger.info(
            f"⚠️ policy_recommendations 텍스트가 2000자 제한 초과 "
            f"({len(recommendations_text)}자) — 프롬프트에서 잘림"
        )
    if len(vuln_text) > 3000:
        logger.info(
            f"⚠️ recon_vulnerabilities 텍스트가 3000자 제한 초과 "
            f"({len(vuln_text)}자) — 프롬프트에서 잘림"
        )

    #     prompt = f"""
    # 다음 입력 데이터를 분석하여 PreFlight 통합 보안 보고서를 생성하십시오.

    # ========== ORIGINAL BICEP CODE ==========
    # {bicep_code}

    # ========== POLICY VIOLATIONS ({len(policy_violations)}) ==========
    # {violations_text[:3000]}

    # ========== POLICY RECOMMENDATIONS ({len(policy_recommendations)}) ==========
    # {recommendations_text[:2000]}

    # ========== RECON VULNERABILITIES ({vuln_count}) ==========
    # {vuln_text[:3000]}

    # ========== RECON ATTACK SCENARIOS ({attack_count}) ==========
    # Each entry represents a simulated attack scenario run against a local Docker container
    # that replicates an Azure resource. Fields:
    # - id: scenario identifier (SCN-XXX)
    # - mitre_technique: MITRE ATT&CK technique ID
    # - severity: risk level if scenario succeeds
    # - container: target container name
    # - objective: attack goal
    # - executed_command: command used in simulation
    # - command_output: output from the command
    # - security_finding: combined observation and security interpretation

    # {attack_text}

    # ============================================================
    # REPORT FORMAT (STRICT TEMPLATE)
    # ============================================================

    # 아래 형식을 엄수하여 PreFlight 통합 보안 보고서를 작성하시오. placeholder 금지 — 모든 섹션을 실제 분석 내용으로 채울 것.

    # # 🔍 PreFlight 통합 보안 보고서

    # ## 📊 Executive Summary

    # ### 심각도별 발견 현황

    # | 등급 | 건수 | 주요 발견 항목 |
    # |------|------|----------------|
    # | 🚨 Critical | {severity_counts['Critical']} | (Critical 취약점 제목들을 콤마로 나열, 없으면 "-") |
    # | ⚠️ High     | {severity_counts['High']}     | (High 취약점 제목들을 콤마로 나열, 없으면 "-") |
    # | 🔷 Medium   | {severity_counts['Medium']}   | (Medium 취약점 제목들을 콤마로 나열, 없으면 "-") |
    # | 🟢 Low      | {severity_counts['Low']}      | (Low 취약점 제목들을 콤마로 나열, 없으면 "-") |

    # ### Policy 위반 요약

    # | # | 규칙 ID | 심각도 | 위반 내용 (요약) |
    # |---|---------|--------|-----------------|
    # (policy_violations 각 항목 — rule, severity, message 요약 1줄씩 실제 내용으로 채울 것)

    # ### 핵심 보안 이슈

    # 가장 중요한 보안 위험을 2~4줄로 구체적으로 요약. 어떤 리소스에서 어떤 설정 문제가 있는지 언급할 것.

    # ---

    # ## 1. 🛡️ Security Control Integrity Review

    # 원본 **Azure Bicep 아키텍처의 보안 설계 의도**와
    # 변환된 **Docker Compose 구조에서 해당 보안 통제가 유지되는지**를 비교 평가합니다.

    # | 보안 통제 항목 | Bicep 설정값 / 의도 | Docker Compose 상태 | 위험도 | 평가 |
    # |----------------|---------------------|--------------------|--------|------|
    # | Key Vault networkAcls defaultAction | (실제 값 또는 미설정) | 유지 / 약화 / 미적용 | 🚨 / ⚠️ / 🔷 / 🟢 | (구체적 분석) |
    # | Storage allowBlobPublicAccess | (실제 값 또는 미설정) | 유지 / 약화 / 미적용 | 🚨 / ⚠️ / 🔷 / 🟢 | (구체적 분석) |
    # | TLS 최소 버전 | (실제 값 또는 미설정) | 유지 / 약화 / 미적용 | 🚨 / ⚠️ / 🔷 / 🟢 | (구체적 분석) |
    # | HTTPS Only | (실제 값 또는 미설정) | 유지 / 약화 / 미적용 | 🚨 / ⚠️ / 🔷 / 🟢 | (구체적 분석) |
    # | Private Endpoint | (사용 여부) | 유지 / 약화 / 미적용 | 🚨 / ⚠️ / 🔷 / 🟢 | (구체적 분석) |
    # | Private DNS Zone | (사용 여부) | 유지 / 약화 / 미적용 | 🚨 / ⚠️ / 🔷 / 🟢 | (구체적 분석) |
    # | Soft Delete + Purge Protection | (활성화 여부) | 유지 / 약화 / 미적용 | 🚨 / ⚠️ / 🔷 / 🟢 | (구체적 분석) |

    # ### Risk Legend

    # - 🚨 **Critical** — 원본 설계의 핵심 보안 통제가 완전히 제거됨
    # - ⚠️ **High** — 통제가 약화되어 공격 가능성 증가
    # - 🔷 **Medium** — 일부 기능은 유지되지만 완전하지 않음
    # - 🟢 **Low / Preserved** — 원본 보안 설계가 대부분 유지됨

    # (각 행을 실제 변환 결과 분석으로 채울 것)

    # ---

    # ## 2. ⚠️ Design-Level Security Mismatch Analysis

    # 설계 수준 보안 불일치를 항목별로 분석합니다.
    # **⚠️ 모든 항목은 반드시 조건부 표현으로 작성할 것.**

    # ### MSM-001: [불일치 제목 — 실제 분석 기반]
    # - **영향 영역**: 네트워크 격리 / 접근 제어 / 암호화 / 기타
    # - **원본 의도**: 원본 설계에서 의도한 통제 내용
    # - **변환 후 상태**: 변환 이후 통제 상태
    # - **불일치 설명**: If deployed without equivalent controls, this may increase exposure to...
    # - **위험 등급**: 🚨 Critical / ⚠️ High / 🔷 Medium / 🟢 Low

    # (policy violations와 recon vulnerabilities 기반으로 실제 불일치 항목 반복 작성)

    # ---

    # ## 3. 🎯 시뮬레이션 기반 검증 결과

    # 로컬 Docker 환경에서 수행된 공격 시나리오 시뮬레이션 결과입니다.
    # 실제 Azure 리소스에 대한 공격이 아닌, 동등한 구성을 로컬에 재현하여 설계 취약점을 확인한 결과입니다.

    # | ID | MITRE 기법 | 대상 컨테이너 | 위험도 | 목표 | 보안 발견 사항 |
    # |----|-----------|--------------|--------|------|----------------|
    # (recon_attack_scenarios의 각 항목을 한 행씩 채울 것. 시나리오가 없으면 "| - | - | - | - | - | 시뮬레이션 결과 없음 |" 한 행 작성)

    # 시나리오가 있는 경우, 각 항목에 대해 아래 형식으로 상세 서술할 것:

    # ### SCN-XXX: [objective 내용]
    # - **MITRE**: (mitre_technique)
    # - **대상**: (container)
    # - **위험도**: 🚨/⚠️/🔷/🟢
    # - **보안 발견**: (security_finding — 조건부 표현 사용)

    # ---

    # ## 4. 💥 Potential Security Impact

    # 잠재적 보안 영향을 조건부로 설명합니다.

    # ### P0 — 즉시 검토 필요
    # - (Critical/High 항목 기반, If deployed without... 형식으로 구체적 작성)

    # ### P1 — 단기 검토 권고
    # - (Medium 항목 기반, In the absence of... 형식으로 구체적 작성)

    # ### P2 — 구조적 개선 권고
    # - (설계 구조 개선이 필요한 항목, Could potentially allow... 형식으로 작성)

    # ---

    # ## 5. ✅ Recommended Verification Checklist

    # 배포 전 반드시 확인해야 할 항목입니다.

    # 1. (구체적 확인 항목 — 실제 발견 이슈 기반)
    # 2. (구체적 확인 항목)
    # 3. ...
    # (최소 7개, 개발자가 직접 점검 가능하도록 구체적으로 작성)

    # ---

    # ## 6. 🔧 Updated Bicep Code

    # 아래는 위에서 식별된 **Policy 위반 및 취약점을 반영하여 개선한 Bicep 코드**입니다.

    # ### 주요 변경 사항

    # | # | 변경 항목 | 변경 내용 |
    # |---|-----------|-----------|
    # | 1 | (변경 항목명) | (원본 → 개선 내용 요약) |
    # | 2 | (변경 항목명) | (원본 → 개선 내용 요약) |
    # (실제 변경된 항목들 작성)

    # ### 개선된 Bicep 코드

    # ```bicep
    # (원본 Bicep 코드에서 모든 보안 이슈를 수정한 완전한 코드 — placeholder 없이 실제 코드 작성)
    # ```

    # > ⚠️ 위 코드는 설계 의도 기반 개선 제안입니다. 실제 배포 전 인프라 환경에 맞게 검토 및 수정하여 사용하십시오.

    # ---

    # Return ONLY valid JSON (no markdown code fence, no extra text):
    # {{
    #   "final_report": "...(full Markdown report in Korean)...",
    #   "vulnerability_summary": {vuln_count},
    #   "verification_checklist": ["항목 1", "항목 2", ...]
    # }}
    # """

    REPORTING_AGENT_PROMPT = """
You must generate a comprehensive PreFlight security report.

The report evaluates an Azure architecture BEFORE deployment.

Use the following inputs as evidence.

================================================
BICEP ARCHITECTURE
================================================

{bicep_code}

================================================
DOCKER COMPOSE REPRODUCTION ENVIRONMENT
================================================

{docker_compose_txt}

================================================
SECURITY POLICY ANALYSIS RESULT
================================================

{policy_result}

================================================
RECONNAISSANCE / ATTACK SIMULATION RESULT
================================================

{recon_result}

================================================
REPORT FORMAT
================================================

# PreFlight 아키텍처 보안 평가 보고서

---

# 1. Executive Summary

이 섹션은 전체 보안 평가 결과를 요약합니다.

포함해야 할 내용:

- 전체 아키텍처 보안 수준
- 주요 위험 요약
- 가장 중요한 보안 문제
- 아키텍처 재현 정확도 요약

예시 항목:

| 항목 | 결과 |
|-----|-----|
| Policy 위반 | X |
| 발견된 취약점 | X |
| Critical Risk | X |
| Architecture Reproduction Fidelity | XX% |

---

# 2. Policy Compliance Review

보안 정책 준수 여부를 분석합니다.

| Policy | Result | 설명 |
|------|------|------|

위반된 정책이 있다면 왜 문제가 되는지 설명합니다.

---

# 3. Design-Level Security Control Review

Bicep 설계에 정의된 보안 통제를 검토합니다.

| Security Control | Bicep 설정 | 평가 |
|---|---|---|

예:

- TLS 최소 버전
- Storage public access
- Key Vault network ACL
- HTTPS enforcement

설계 의도가 유지되는지 평가합니다.

---

# 4. Architecture Reproduction Analysis (Bicep ↔ Docker)

이 섹션은 Azure Bicep 설계와
Docker Compose 기반 로컬 환경 간의
아키텍처 재현 정확도를 분석합니다.

목적:

- 로컬 테스트 환경이 IaC 설계를 얼마나 정확히 재현하는지 평가
- 보안 테스트 환경에서 누락된 설계 요소 식별

---

## Resource Reproduction

| Resource Type | Bicep | Docker | 상태 |
|---|---|---|---|

### Resource Reproduction Score

재현된 리소스 / 전체 리소스

---

## Security Control Reproduction

| Security Control | Bicep 설정 | Docker 대응 | 평가 |
|---|---|---|---|

### Security Reproduction Score

재현된 통제 / 전체 통제

---

## Network Exposure Reproduction

| 항목 | Bicep 설계 | Docker 구현 | 평가 |
|---|---|---|---|

---

## Overall Reproduction Fidelity

| Category | Score |
|---|---|
| Resource Reproduction | X / Y |
| Security Control Reproduction | X / Y |
| Network Reproduction | X / Y |

Overall Architecture Reproduction Fidelity:

XX %

---

# 5. Attack Simulation Findings

Recon 및 공격 시뮬레이션 결과를 분석합니다.

| Attack Surface | 발견 내용 | 위험 |
|---|---|---|

예:

- 공개된 서비스
- 인증 없는 접근
- 버전 정보 노출
- 환경변수 내 secret 노출

각 항목에 대해 설명합니다.

---

# 6. Risk Prioritization

발견된 위험을 우선순위로 정리합니다.

| Risk | Severity | 설명 |
|---|---|---|

Severity:

CRITICAL
HIGH
MEDIUM

---

# 7. Security Hardening Recommendations

각 주요 위험에 대해 보안 개선 방법을 제안합니다.

---

## Example Secure Bicep Fix

```bicep
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {{
  name: 'securestorage'
  location: resourceGroup().location
  properties: {{
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }}
}}
```

설명:

해당 설정은 공개 Blob 접근을 차단하고
최소 TLS 버전을 강제합니다.

---

# 8. Security Validation Checklist

| 항목 | 상태 |
|---|---|
| Storage Public Access Disabled | |
| TLS 1.2 Enforced | |
| HTTPS Only | |
| Secrets not exposed | |
| Unnecessary ports closed | |

---

END OF REPORT
"""

    # Policy 결과 구성
    policy_result = f"""
    Policy Violations:
    {violations_text[:3000]}

    Policy Recommendations:
    {recommendations_text[:2000]}
    """

    # Recon 결과 구성
    recon_result = f"""
    Vulnerabilities:
    {vuln_text[:3000]}

    Attack Scenarios:
    {attack_text}
    """

    # Reporting Agent Prompt 생성
    report_prompt = REPORTING_AGENT_PROMPT.format(
        bicep_code=bicep_code,
        policy_result=policy_result,
        recon_result=recon_result,
        docker_compose_txt=docker_compose_txt,
    )

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
        result = await agent.run(report_prompt)
        agent_response_text = (result.text or "").strip()
        logger.info("✅ Reporting agent 실행 완료")
    except Exception as e:
        logger.error(f"❌ Reporting agent 실행 실패: {e}", exc_info=True)
        return _fallback_report(
            policy_violations, recon_vulnerabilities, recon_attack_scenarios, vuln_count
        )

    if not agent_response_text:
        logger.warning("⚠️ Reporting agent: 빈 응답, fallback 사용")
        return _fallback_report(
            policy_violations, recon_vulnerabilities, recon_attack_scenarios, vuln_count
        )

    # JSON 파싱 시도 (LLM이 JSON을 반환한 경우)
    parsed = _parse_json_response(agent_response_text)
    if parsed:
        logger.info(
            f"✅ PreFlight report JSON 파싱 완료: "
            f"vuln_summary={parsed.get('vulnerability_summary')}, "
            f"checklist={len(parsed.get('verification_checklist', []))}개 항목"
        )
        return parsed

    # JSON 파싱 실패 → 응답 전체를 마크다운 보고서로 사용
    logger.info("ℹ️ Reporting agent: 마크다운 응답 → final_report로 직접 사용")
    checklist = _extract_checklist_from_markdown(agent_response_text)
    return {
        "final_report": agent_response_text,
        "vulnerability_summary": vuln_count,
        "verification_checklist": checklist,
    }


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def _extract_checklist_from_markdown(text: str) -> list[str]:
    """마크다운 보고서에서 Verification Checklist 항목 추출"""
    # "Checklist" 섹션 이후의 번호 목록 또는 체크 목록 추출
    checklist = []
    in_checklist = False
    for line in text.split("\n"):
        lower = line.lower()
        if "checklist" in lower and ("#" in line or "---" in lower):
            in_checklist = True
            continue
        if in_checklist:
            # 다음 섹션 시작 시 종료
            if line.startswith("#") or line.startswith("---"):
                break
            # 번호 목록 또는 체크 목록
            stripped = line.strip()
            if re.match(r"^(\d+[\.\)]\s+|\-\s+|\*\s+|☐\s+|✅\s+)", stripped):
                item = re.sub(r"^(\d+[\.\)]\s+|\-\s+|\*\s+|☐\s+|✅\s+)", "", stripped).strip()
                if item and "|" not in item:
                    checklist.append(item)
    return checklist


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
    """Agent 실패 시 기본 보고서 생성 (REPORTING_AGENT_PROMPT 포맷과 동일 구조)"""

    # ── severity 집계 ──
    severity_counts: dict[str, int] = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for v in recon_vulnerabilities:
        sev = v.get("severity", "Medium")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    # ── Policy 위반 테이블 행 ──
    policy_rows = (
        "\n".join(
            f"| {v.get('rule', '-')} | {v.get('severity', '-')} | {v.get('message', '')[:80]} |"
            for v in policy_violations
        )
        or "| - | - | 위반 없음 |"
    )

    # ── 취약점 리스크 테이블 행 ──
    risk_rows = (
        "\n".join(
            f"| {v.get('title', v.get('description', '-'))[:60]} | {v.get('severity', 'Medium')} "
            f"| {v.get('description', '-')[:80]} |"
            for v in recon_vulnerabilities
        )
        or "| - | - | 발견된 위험 없음 |"
    )

    # ── 공격 시뮬레이션 테이블 행 ──
    attack_rows = (
        "\n".join(
            f"| {s.get('objective', '-')[:50]} "
            f"| {s.get('security_finding', '-')[:80]} "
            f"| {s.get('severity', '-')} |"
            for s in recon_attack_scenarios
        )
        or "| - | - | 시뮬레이션 결과 없음 |"
    )

    # ── 체크리스트 (취약점 기반 동적 생성) ──
    checklist: list[str] = []
    for v in recon_vulnerabilities:
        title = v.get("title", v.get("description", ""))
        if title:
            checklist.append(f"{title} 조치 확인")
    if not checklist:
        checklist = [
            "보안 정책 위반 항목 조치 확인",
            "네트워크 격리 설정 확인",
            "TLS / HTTPS 설정 확인",
            "인증 및 접근 제어 설정 확인",
            "불필요한 포트 차단 확인",
        ]

    checklist_lines = "\n".join(
        f"| {item} | |" for item in checklist
    )

    final_report = f"""# PreFlight 아키텍처 보안 평가 보고서

> 보안 분석 에이전트 응답 실패로 인해 자동 생성된 Fallback 보고서입니다.

---

# 1. Executive Summary

| 항목 | 결과 |
|-----|-----|
| Policy 위반 | {len(policy_violations)}건 |
| 발견된 취약점 | {vuln_count}건 |
| Critical Risk | {severity_counts['Critical']}건 |
| High Risk | {severity_counts['High']}건 |
| Medium Risk | {severity_counts['Medium']}건 |
| Low Risk | {severity_counts['Low']}건 |
| 공격 시뮬레이션 시나리오 | {len(recon_attack_scenarios)}건 |
| Architecture Reproduction Fidelity | 데이터 부족으로 산출 불가 |

---

# 2. Policy Compliance Review

| Policy | Result | 설명 |
|------|------|------|
{policy_rows}

---

# 3. Design-Level Security Control Review

| Security Control | Bicep 설정 | 평가 |
|---|---|---|
| TLS 최소 버전 | 입력 데이터 참조 필요 | 에이전트 응답 실패로 자동 분석 불가 |
| Storage public access | 입력 데이터 참조 필요 | 에이전트 응답 실패로 자동 분석 불가 |
| Key Vault network ACL | 입력 데이터 참조 필요 | 에이전트 응답 실패로 자동 분석 불가 |
| HTTPS enforcement | 입력 데이터 참조 필요 | 에이전트 응답 실패로 자동 분석 불가 |

> 제공된 입력 정보만으로는 해당 항목을 확정적으로 판단하기 어렵습니다.
> 원본 Bicep 코드를 직접 검토하여 보안 통제 상태를 확인하십시오.

---

# 4. Architecture Reproduction Analysis (Bicep ↔ Docker)

## Resource Reproduction

| Resource Type | Bicep | Docker | 상태 |
|---|---|---|---|
| (에이전트 응답 실패) | - | - | 자동 분석 불가 |

### Resource Reproduction Score

데이터 부족으로 산출 불가

---

## Security Control Reproduction

| Security Control | Bicep 설정 | Docker 대응 | 평가 |
|---|---|---|---|
| (에이전트 응답 실패) | - | - | 자동 분석 불가 |

### Security Reproduction Score

데이터 부족으로 산출 불가

---

## Network Exposure Reproduction

| 항목 | Bicep 설계 | Docker 구현 | 평가 |
|---|---|---|---|
| (에이전트 응답 실패) | - | - | 자동 분석 불가 |

---

## Overall Reproduction Fidelity

| Category | Score |
|---|---|
| Resource Reproduction | - |
| Security Control Reproduction | - |
| Network Reproduction | - |

Overall Architecture Reproduction Fidelity: 데이터 부족으로 산출 불가

---

# 5. Attack Simulation Findings

| Attack Surface | 발견 내용 | 위험 |
|---|---|---|
{attack_rows}

---

# 6. Risk Prioritization

| Risk | Severity | 설명 |
|---|---|---|
{risk_rows}

---

# 7. Security Hardening Recommendations

> 에이전트 응답 실패로 인해 자동 개선 코드가 생성되지 않았습니다.
> 위 Risk Prioritization 항목과 Policy 위반 내용을 참고하여 원본 Bicep 코드를 수동으로 검토하십시오.

---

# 8. Security Validation Checklist

| 항목 | 상태 |
|---|---|
{checklist_lines}

---

END OF REPORT
"""

    return {
        "final_report": final_report,
        "vulnerability_summary": vuln_count,
        "verification_checklist": checklist,
    }
