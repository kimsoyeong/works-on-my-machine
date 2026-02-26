import asyncio
import logging
import os
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from agents.policy_agent import review_bicep_only as policy_agent_review
from agents.redteam_agent import RedTeamAgent  # 동료 코드 — 수정 금지
from api.models.response import (
    AnalyzeResponse,
    AttackScenarioItem,
    PolicyResult,
    SecurityResult,
    StepStatus,
    VulnerabilityItem,
)
from mock_services.bicep_transformer import mock_bicep_transform
from mock_services.file_processor import mock_file_preprocessing

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


def _validate_file(filename: str, size: int) -> None:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식: {ext}. 지원: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"파일 크기 초과: {size} bytes (최대 {MAX_FILE_SIZE} bytes)",
        )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_architecture(
    file: UploadFile = File(...),
    skip_policy: bool = Form(default=False),
):
    """
    아키텍처 파일을 분석합니다.

    파이프라인 (구조도와 동일):
    Upload → Preprocess → BiCep 변환 → [ Policy 갈래 | RedTeam 갈래 ] → Result
    - BiCep 변환기 출력(bicep_code)이 Policy Agent와 RedTeam Agent **공통 입력**입니다.
    - skip_policy=True 이면 Policy 갈래만 건너뜀 (동료가 RedTeam만 테스트할 때 사용).
    """
    task_id = uuid.uuid4().hex[:12]
    steps: list[StepStatus] = []

    try:
        # --- Step 1: 파일 검증 ---
        content = await file.read()
        _validate_file(file.filename, len(content))
        steps.append(StepStatus(step="파일 업로드", status="completed", message=f"{file.filename} ({len(content)} bytes)"))

        # --- Step 2: 전처리 + BiCep 변환 (순차) ---
        await mock_file_preprocessing(content, file.filename)
        steps.append(StepStatus(step="파일 전처리", status="completed"))

        # BiCep 변환기 출력 → Policy / RedTeam 두 갈래의 공통 입력 (가짜 bicep 없음)
        bicep_code = await mock_bicep_transform(content, file.filename)
        steps.append(StepStatus(step="BiCep 변환", status="completed", message=f"{len(bicep_code)} chars"))

        # --- 갈래: BiCep 출력을 Policy Agent / RedTeam Agent에 동시 입력 ---
        async def run_policy_branch() -> tuple[PolicyResult | None, StepStatus]:
            if skip_policy:
                return None, StepStatus(step="Policy 검증", status="completed", message="건너뜀 (Skip Policy Validation)")
            raw_policy = await policy_agent_review(bicep_code)
            api_status = "passed" if (
                raw_policy.get("status") == "normal" and not (raw_policy.get("violations") or [])
            ) else "failed"
            # UI 형식: 각 항목에 rule(규칙 ID) 필드 보장 (rule_id → rule)
            def _norm(v: dict) -> dict:
                return {
                    "rule": v.get("rule") or v.get("rule_id") or "-",
                    "severity": (v.get("severity") or "medium").lower(),
                    "message": v.get("message") or "",
                    "recommendation": v.get("recommendation") or "",
                }
            violations_ui = [_norm(v) for v in (raw_policy.get("violations") or [])]
            recommendations_ui = [_norm(r) for r in (raw_policy.get("recommendations") or [])]
            policy_result = PolicyResult(
                status=api_status,
                result_message=raw_policy.get("result_message", ""),
                total_checks=raw_policy.get("total_checks", 0),
                violations=violations_ui,
                recommendations=recommendations_ui,
                summary=raw_policy.get("summary", ""),
            )
            if raw_policy.get("status") == "error":
                step = StepStatus(step="Policy 검증", status="error", message=raw_policy.get("error", "검증 실패"))
            else:
                msg = raw_policy.get("result_message") or raw_policy.get("summary", "")
                step = StepStatus(step="Policy 검증", status="completed", message=msg)
            return policy_result, step

        async def run_redteam_branch():
            redteam_agent = RedTeamAgent()  # 동료 코드 — 수정 금지
            result = await redteam_agent.analyze(bicep_code)
            step = StepStatus(step="RedTeam 분석", status="completed", message=f"취약점 {len(result.vulnerabilities)}개")
            return result, step

        (policy_result, policy_step), (result, redteam_step) = await asyncio.gather(
            run_policy_branch(),
            run_redteam_branch(),
        )
        steps.append(policy_step)
        steps.append(redteam_step)

        security = SecurityResult(
            vulnerabilities=[
                VulnerabilityItem(
                    id=v.id,
                    severity=v.severity,
                    category=v.category,
                    affected_resource=v.affected_resource,
                    title=v.title,
                    description=v.description,
                    evidence=v.evidence,
                    remediation=v.remediation,
                    benchmark_ref=v.benchmark_ref,
                )
                for v in result.vulnerabilities
            ],
            attack_scenarios=[
                AttackScenarioItem(
                    id=a.id,
                    name=a.name,
                    mitre_technique=a.mitre_technique,
                    target_vulnerabilities=a.target_vulnerabilities,
                    severity=a.severity,
                    prerequisites=a.prerequisites,
                    attack_chain=a.attack_chain,
                    expected_impact=a.expected_impact,
                    detection_difficulty=a.detection_difficulty,
                    likelihood=a.likelihood,
                )
                for a in result.attack_scenarios
            ],
            vulnerability_summary=result.vulnerability_count,
            report=result.report,
        )

        # --- Step 5: 결과 종합 ---
        vuln_count = len(result.vulnerabilities)
        attack_count = len(result.attack_scenarios)
        steps.append(StepStatus(
            step="결과 종합",
            status="completed",
            message=f"취약점 {vuln_count}개 · 공격 {attack_count}개",
        ))

        return AnalyzeResponse(
            status="success",
            task_id=task_id,
            steps=steps,
            policy=policy_result,
            security=security,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("분석 중 오류 발생")
        steps.append(StepStatus(step="오류", status="error", message=str(e)))
        return AnalyzeResponse(
            status="error",
            task_id=task_id,
            steps=steps,
            error=str(e),
        )
