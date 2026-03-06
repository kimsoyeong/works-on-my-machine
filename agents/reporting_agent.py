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

4. Architecture Reproduction and Attack Simulation

This section integrates two analyses:

(A) Docker Reproduction:
Evaluate how accurately the local Docker environment
reproduces the original Azure IaC design.

- Resource reproduction
- Security control reproduction
- Network exposure reproduction

Calculate reproduction scores where possible.
Do NOT fabricate missing resources.

(B) Attack Simulation on Reproduced Environment:
Interpret Recon and attack simulation results
in the context of the reproduced Docker environment.

Focus on exposed services, unauthenticated access,
version disclosure, sensitive configuration exposure,
default credentials, unnecessary open ports.

(C) Result Interpretation:
Explain what the simulation results mean for
actual Azure deployment, considering Docker limitations.

------------------------------------------------

5. Risk Prioritization

All risks must be classified using three priority levels
based on the following quantitative criteria:

CRITICAL (CVSS 9.0–10.0)
- Remote exploitation without authentication
- Direct data breach or full system compromise
- Public exposure of secrets, credentials, or management interfaces
- Complete bypass of security controls

HIGH (CVSS 7.0–8.9)
- Exploitation requires limited preconditions
- Significant data exposure or privilege escalation
- Security controls weakened to the point of ineffectiveness
- Missing encryption or authentication on sensitive channels

MEDIUM (CVSS 4.0–6.9)
- Exploitation requires specific conditions or insider access
- Limited data exposure or partial control bypass
- Security best practices not followed but no direct exploit path
- Configuration drift from design intent without immediate risk

LOW (CVSS 0.1–3.9)
- Informational or defense-in-depth improvements
- Minor configuration deviations
- No direct exploitability

------------------------------------------------

6. Remediation Guidance

For each critical or high risk issue:

Provide a secure Bicep code improvement.

The remediation should:

- preserve the architecture intent
- enforce security best practices
- directly mitigate the identified risk

------------------------------------------------

7. No Hallucination Rule

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

# 🔍 PreFlight 통합 보안 보고서

---

# 1. 종합 요약

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
| Critical 위험 | X |
| 아키텍처 재현 정확도 | XX% |

## 위험 등급 판단 기준

본 보고서의 위험 등급은 CVSS(Common Vulnerability Scoring System) 기반으로 분류됩니다.

| 등급 | CVSS 범위 | 판단 기준 |
|------|-----------|----------|
| Critical | 9.0 – 10.0 | 인증 없이 원격 악용 가능, 데이터 유출·전체 시스템 장악, 시크릿/관리 인터페이스 공개 노출, 보안 통제 완전 우회 |
| High | 7.0 – 8.9 | 제한된 전제 조건 하에서 악용 가능, 권한 상승·민감 데이터 노출, 보안 통제가 무력화 수준으로 약화, 암호화·인증 누락 |
| Medium | 4.0 – 6.9 | 특정 조건 또는 내부 접근 필요, 제한적 데이터 노출·부분적 통제 우회, 보안 모범 사례 미준수(직접 공격 경로 없음), 설계 의도와의 구성 차이 |
| Low | 0.1 – 3.9 | 정보 수준·심층 방어 개선 사항, 경미한 구성 편차, 직접적 악용 불가 |

---

# 2. 보안 정책 준수 검토

보안 정책 준수 여부를 분석합니다.

| 정책 | 결과 | 설명 |
|------|------|------|

위반된 정책이 있다면 왜 문제가 되는지 설명합니다.

---

# 3. 설계 수준 보안 통제 검토

Bicep 설계에 정의된 보안 통제를 검토합니다.

| 보안 통제 | Bicep 설정 | 평가 |
|-----------|-----------|------|

예:

- TLS 최소 버전
- Storage public access
- Key Vault network ACL
- HTTPS enforcement

설계 의도가 유지되는지 평가합니다.

---

# 4. 아키텍처 재현 및 공격 시뮬레이션

이 섹션은 Azure Bicep 설계를 Docker Compose 기반 로컬 환경으로 재현한 뒤,
해당 환경에서 수행한 공격 시뮬레이션 결과를 통합 분석합니다.

## 4.1 Docker 환경 재현 현황

원본 Bicep 아키텍처를 로컬 Docker 환경으로 얼마나 정확히 재현했는지 평가합니다.

| 리소스 유형 | Bicep | Docker | 재현 상태 |
|------------|-------|--------|----------|

| 보안 통제 | Bicep 설정 | Docker 대응 | 평가 |
|-----------|-----------|------------|------|

| 네트워크 항목 | Bicep 설계 | Docker 구현 | 평가 |
|-------------|-----------|------------|------|

### 전체 재현 정확도

| 항목 | 점수 |
|------|------|
| 리소스 재현 | X / Y |
| 보안 통제 재현 | X / Y |
| 네트워크 재현 | X / Y |

Overall Architecture Reproduction Fidelity: XX %

---

## 4.2 공격 시뮬레이션 수행

위에서 재현된 Docker 환경에서 수행한 공격 시뮬레이션과 그 결과입니다.

| 공격 표면 | 수행한 공격 | 결과 | 위험도 |
|----------|-----------|------|--------|

각 공격에 대해:
- 어떤 재현된 환경(컨테이너)을 대상으로 했는지
- 어떤 공격을 수행했는지
- 그 결과가 어떠했는지
- 이 결과가 실제 Azure 배포 시 어떤 보안 위험을 의미하는지

를 설명합니다.

---

## 4.3 시뮬레이션 결과 해석

재현 환경의 한계와 실제 Azure 배포 환경과의 차이를 고려하여,
시뮬레이션 결과가 실제 운영 환경에서 어떤 의미를 갖는지 종합 해석합니다.

- 재현 환경에서 확인된 위험이 실제 Azure에서도 동일하게 적용되는지
- Docker 환경 한계로 인해 검증되지 못한 영역은 무엇인지
- 추가 검증이 필요한 항목은 무엇인지

---

# 5. 위험 우선순위

발견된 위험을 우선순위로 정리합니다.

| 위험 | 심각도 | 설명 |
|------|--------|------|

심각도:

CRITICAL
HIGH
MEDIUM

---

# 6. 보안 강화 권고사항

각 주요 위험에 대해 보안 개선 방법을 제안합니다.

Critical 또는 High 위험 항목별로 아래 형식으로 작성하십시오:

### [위험 항목 제목]
- **위험**: 어떤 보안 위험인지 설명
- **개선 방법**: 어떻게 수정해야 하는지 설명

Bicep 수정 예시:

```bicep
(해당 항목만 수정한 짧은 코드 snippet — 전체 코드 아님)
```

(각 Critical/High 항목에 대해 위 패턴을 반복할 것)

---

# 7. 보안 검증 체크리스트

| 항목 | 상태 |
|------|------|
| Storage Public Access 비활성화 | |
| TLS 1.2 적용 | |
| HTTPS 전용 | |
| 시크릿 미노출 | |
| 불필요한 포트 차단 | |

---

# Appendix: Complete Improved Bicep Code

아래는 원본 Bicep 코드에서 위 보고서에서 식별된 **모든 보안 이슈를 반영하여 개선한 전체 Bicep 코드**입니다.
원본 코드 구조를 유지하면서 모든 Policy 위반과 취약점을 수정한 완전한 코드를 작성하십시오.
placeholder 없이 실제 코드로 작성할 것. 이 코드는 다운로드용으로 제공됩니다.

```bicep
(원본 Bicep 코드에서 모든 보안 이슈를 수정한 완전한 코드)
```
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
            max_tokens=8000,
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
                item = re.sub(
                    r"^(\d+[\.\)]\s+|\-\s+|\*\s+|☐\s+|✅\s+)", "", stripped
                ).strip()
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

    checklist_lines = "\n".join(f"| {item} | |" for item in checklist)

    final_report = f"""# PreFlight 아키텍처 보안 평가 보고서

> 보안 분석 에이전트 응답 실패로 인해 자동 생성된 Fallback 보고서입니다.

---

# 1. 종합 요약

| 항목 | 결과 |
|-----|-----|
| Policy 위반 | {len(policy_violations)}건 |
| 발견된 취약점 | {vuln_count}건 |
| Critical 위험 | {severity_counts['Critical']}건 |
| High 위험 | {severity_counts['High']}건 |
| Medium 위험 | {severity_counts['Medium']}건 |
| Low 위험 | {severity_counts['Low']}건 |
| 공격 시뮬레이션 시나리오 | {len(recon_attack_scenarios)}건 |
| 아키텍처 재현 정확도 | 데이터 부족으로 산출 불가 |

## 위험 등급 판단 기준

본 보고서의 위험 등급은 CVSS(Common Vulnerability Scoring System) 기반으로 분류됩니다.

| 등급 | CVSS 범위 | 판단 기준 |
|------|-----------|----------|
| Critical | 9.0 – 10.0 | 인증 없이 원격 악용 가능, 데이터 유출·전체 시스템 장악, 시크릿/관리 인터페이스 공개 노출 |
| High | 7.0 – 8.9 | 제한된 전제 조건 하에서 악용 가능, 권한 상승·민감 데이터 노출, 보안 통제 무력화 |
| Medium | 4.0 – 6.9 | 특정 조건 또는 내부 접근 필요, 제한적 데이터 노출, 보안 모범 사례 미준수 |
| Low | 0.1 – 3.9 | 정보 수준·심층 방어 개선 사항, 경미한 구성 편차, 직접적 악용 불가 |

---

# 2. 보안 정책 준수 검토

| 정책 | 결과 | 설명 |
|------|------|------|
{policy_rows}

---

# 3. 설계 수준 보안 통제 검토

| 보안 통제 | Bicep 설정 | 평가 |
|-----------|-----------|------|
| TLS 최소 버전 | 입력 데이터 참조 필요 | 에이전트 응답 실패로 자동 분석 불가 |
| Storage public access | 입력 데이터 참조 필요 | 에이전트 응답 실패로 자동 분석 불가 |
| Key Vault network ACL | 입력 데이터 참조 필요 | 에이전트 응답 실패로 자동 분석 불가 |
| HTTPS enforcement | 입력 데이터 참조 필요 | 에이전트 응답 실패로 자동 분석 불가 |

> 제공된 입력 정보만으로는 해당 항목을 확정적으로 판단하기 어렵습니다.
> 원본 Bicep 코드를 직접 검토하여 보안 통제 상태를 확인하십시오.

---

# 4. 아키텍처 재현 및 공격 시뮬레이션

## 4.1 Docker 환경 재현 현황

| 리소스 유형 | Bicep | Docker | 재현 상태 |
|------------|-------|--------|----------|
| (에이전트 응답 실패) | - | - | 자동 분석 불가 |

| 보안 통제 | Bicep 설정 | Docker 대응 | 평가 |
|-----------|-----------|------------|------|
| (에이전트 응답 실패) | - | - | 자동 분석 불가 |

Overall Architecture Reproduction Fidelity: 데이터 부족으로 산출 불가

---

## 4.2 공격 시뮬레이션 수행

| 공격 표면 | 수행한 공격 | 결과 | 위험도 |
|----------|-----------|------|--------|
{attack_rows}

---

## 4.3 시뮬레이션 결과 해석

> 에이전트 응답 실패로 인해 자동 해석이 생성되지 않았습니다.

---

# 5. 위험 우선순위

| 위험 | 심각도 | 설명 |
|------|--------|------|
{risk_rows}

---

# 6. 보안 강화 권고사항

> 에이전트 응답 실패로 인해 자동 개선 코드가 생성되지 않았습니다.
> 위 위험 우선순위 항목과 Policy 위반 내용을 참고하여 원본 Bicep 코드를 수동으로 검토하십시오.

---

# 7. 보안 검증 체크리스트

| 항목 | 상태 |
|------|------|
{checklist_lines}
"""

    return {
        "final_report": final_report,
        "vulnerability_summary": vuln_count,
        "verification_checklist": checklist,
    }
