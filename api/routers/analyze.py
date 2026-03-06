import asyncio
import dataclasses
import json
import logging
import os
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from agents.policy_agent import review_bicep_only
from agents.recon_agent_wrapper import invoke_recon_agent_wrapper
from agents.reporting_agent import generate_report
from api.models.response import (
    AnalyzeResponse,
    PolicyResult,
    SecurityResult,
    StepStatus,
)
from api.common.services.bicep_transformer import transform_image_to_bicep

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


def _norm(v: dict) -> dict:
    return {
        "rule": v.get("rule") or v.get("rule_id") or "-",
        "severity": (v.get("severity") or "medium").lower(),
        "message": v.get("message") or "",
        "recommendation": v.get("recommendation") or "",
    }


async def _run_policy(bicep_code: str) -> tuple[PolicyResult | None, StepStatus]:
    raw = await review_bicep_only(bicep_code)
    api_status = (
        "passed"
        if (raw.get("status") == "normal" and not (raw.get("violations") or []))
        else "failed"
    )
    violations_ui = [_norm(v) for v in (raw.get("violations") or [])]
    recommendations_ui = [_norm(r) for r in (raw.get("recommendations") or [])]
    policy_result = PolicyResult(
        status=api_status,
        result_message=raw.get("result_message", ""),
        total_checks=raw.get("total_checks", 0),
        violations=violations_ui,
        recommendations=recommendations_ui,
        summary=raw.get("summary", ""),
    )
    if raw.get("status") == "error":
        step = StepStatus(
            step="Policy 검증", status="error", message=raw.get("error", "검증 실패")
        )
    else:
        msg = raw.get("result_message") or raw.get("summary", "")
        step = StepStatus(step="Policy 검증", status="completed", message=msg)
    return policy_result, step


async def _run_recon(bicep_code: str):
    """
    Agent를 사용하여 Recon 분석 수행

    Args:
        bicep_code: Bicep 코드
    """
    logger.info(f"🤖 Starting Agent...")
    result = await invoke_recon_agent_wrapper(bicep_code)

    vuln_count = len(result.vulnerabilities)
    attack_count = len(result.attack_scenarios)
    logger.info(
        f"✅ Analysis complete: {vuln_count} vulnerabilities, {attack_count} attack scenarios"
    )

    return result, StepStatus(
        step="Recon 분석",
        status="completed",
        message=f"취약점 {vuln_count}개, 공격 시나리오 {attack_count}개",
    )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_architecture(
    file: UploadFile = File(...),
):
    """
    아키텍처 파일을 분석합니다.

    파이프라인:
    1. 파일 검증
    2. 파일 전처리 → BiCep 변환
    3. Policy 검증 & Recon 분석 (병렬)
    4. PreFlight 통합 보고서 생성 (설계 의도 대비 재현 구조 분석)

    Args:
        file: 아키텍처 파일 (PDF/PNG/JPG)
    """
    task_id = uuid.uuid4().hex[:12]
    steps: list[StepStatus] = []

    try:
        # --- Step 1: 파일 검증 ---
        content = await file.read()
        _validate_file(file.filename, len(content))
        steps.append(
            StepStatus(
                step="파일 업로드",
                status="completed",
                message=f"{file.filename} ({len(content)} bytes)",
            )
        )

        # --- Step 2: BiCep 변환 ---
        bicep_code = await transform_image_to_bicep(content, file.filename)
        steps.append(
            StepStatus(
                step="BiCep 변환",
                status="completed",
                message=f"{len(bicep_code)} chars",
            )
        )

        # --- Step 3+4: Policy 검증 & Recon 분석 (병렬) ---
        (policy_result, policy_step), (result, recon_step) = await asyncio.gather(
            _run_policy(bicep_code),
            _run_recon(bicep_code),
        )
        steps.append(policy_step)
        steps.append(recon_step)

        # --- Step 5: PreFlight 통합 보고서 생성 ---
        # Policy 결과 + Recon 결과를 "설계 의도 관점"에서 통합 해설 보고서로 생성.
        # 단순 병합이 아니라 보안 통제의 유지/약화/제거 여부를 설계 수준에서 해설.
        policy_violations = policy_result.violations if policy_result else []
        policy_recommendations = policy_result.recommendations if policy_result else []
        recon_vuln_dicts = [
            {
                "id": v.id,
                "severity": v.severity,
                "category": v.category,
                "affected_resource": v.affected_resource,
                "title": v.title,
                "description": v.description,
                "remediation": v.remediation,
            }
            for v in result.vulnerabilities
        ]
        recon_attack_dicts = [dataclasses.asdict(s) for s in result.attack_scenarios]

        # 보고서 생성
        preflight = await generate_report(
            bicep_code=bicep_code,
            policy_violations=policy_violations,
            policy_recommendations=policy_recommendations,
            recon_vulnerabilities=recon_vuln_dicts,
            recon_attack_scenarios=recon_attack_dicts,
        )
        steps.append(
            StepStatus(
                step="PreFlight 통합 보고서",
                status="completed",
                message=(
                    f"취약점 {preflight['vulnerability_summary']}개 · "
                    f"체크리스트 {len(preflight['verification_checklist'])}항목"
                ),
            )
        )

        severity_counts: dict[str, int] = {
            "Critical": 0,
            "High": 0,
            "Medium": 0,
            "Low": 0,
        }
        for v in recon_vuln_dicts:
            sev = v.get("severity", "Medium")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        security = SecurityResult(
            final_report=preflight["final_report"],
            vulnerability_summary=preflight["vulnerability_summary"],
            severity_counts=severity_counts,
            verification_checklist=preflight["verification_checklist"],
            attack_scenarios=result.attack_scenarios,
        )

        # --- Step 6: 결과 종합 ---
        vuln_count = len(result.vulnerabilities)
        attack_count = len(result.attack_scenarios)
        steps.append(
            StepStatus(
                step="결과 종합",
                status="completed",
                message=f"취약점 {vuln_count}개 · 공격 {attack_count}개",
            )
        )

        return AnalyzeResponse(
            status="success",
            task_id=task_id,
            steps=steps,
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


async def _stream_generator(content: bytes, filename: str):
    def sse(type_: str, data: dict):
        return f"data: {json.dumps({'type': type_, 'data': data}, ensure_ascii=False)}\n\n"

    task_id = uuid.uuid4().hex[:12]

    try:
        # Step 1: 파일 업로드 완료
        yield sse("step", StepStatus(
            step="파일 업로드",
            status="completed",
            message=f"{filename} ({len(content)} bytes)",
        ).model_dump())

        # Step 2: BiCep 변환
        yield sse("step", StepStatus(step="BiCep 변환", status="in_progress", message="변환 중...").model_dump())
        bicep_code = await transform_image_to_bicep(content, filename)
        yield sse("step", StepStatus(
            step="BiCep 변환",
            status="completed",
            message=f"{len(bicep_code)} chars",
        ).model_dump())

        # Step 3+4: Policy 검증 & Recon 분석 병렬 실행
        queue: asyncio.Queue = asyncio.Queue()

        yield sse("step", StepStatus(step="Policy 검증", status="in_progress").model_dump())
        yield sse("step", StepStatus(step="Recon 분석", status="in_progress").model_dump())

        async def policy_task():
            result, step = await _run_policy(bicep_code)
            await queue.put(("policy", result, step))

        async def recon_task():
            result, step = await _run_recon(bicep_code)
            await queue.put(("recon", result, step))

        tasks = [asyncio.create_task(policy_task()), asyncio.create_task(recon_task())]

        results = {}
        for _ in range(2):
            name, result, step = await queue.get()
            results[name] = result
            yield sse("step", step.model_dump())

        await asyncio.gather(*tasks)

        # Step 5: 결과 종합
        yield sse("step", StepStatus(step="결과 종합", status="in_progress").model_dump())

        policy_result = results.get("policy")
        recon_result = results.get("recon")

        policy_violations = policy_result.violations if policy_result else []
        policy_recommendations = policy_result.recommendations if policy_result else []
        recon_vuln_dicts = [
            {
                "id": v.id,
                "severity": v.severity,
                "category": v.category,
                "affected_resource": v.affected_resource,
                "title": v.title,
                "description": v.description,
                "remediation": v.remediation,
            }
            for v in recon_result.vulnerabilities
        ] if recon_result else []
        recon_attack_dicts = [dataclasses.asdict(s) for s in recon_result.attack_scenarios] if recon_result else []

        preflight = await generate_report(
            bicep_code=bicep_code,
            policy_violations=policy_violations,
            policy_recommendations=policy_recommendations,
            recon_vulnerabilities=recon_vuln_dicts,
            recon_attack_scenarios=recon_attack_dicts,
        )

        vuln_count = len(recon_vuln_dicts)
        attack_count = len(recon_attack_dicts)

        yield sse("step", StepStatus(
            step="결과 종합",
            status="completed",
            message=f"취약점 {vuln_count}개 · 공격 {attack_count}개",
        ).model_dump())

        severity_counts: dict[str, int] = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for v in recon_vuln_dicts:
            sev = v.get("severity", "Medium")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        security = SecurityResult(
            final_report=preflight["final_report"],
            vulnerability_summary=preflight["vulnerability_summary"],
            severity_counts=severity_counts,
            verification_checklist=preflight["verification_checklist"],
            attack_scenarios=recon_result.attack_scenarios if recon_result else [],
        )

        final = AnalyzeResponse(
            status="success",
            task_id=task_id,
            steps=[],
            security=security,
        )
        yield sse("result", final.model_dump())

    except HTTPException as e:
        yield sse("error", {"message": e.detail})
    except Exception as e:
        logger.exception("스트리밍 분석 중 오류 발생")
        yield sse("error", {"message": str(e)})


@router.post("/analyze/stream")
async def analyze_architecture_stream(file: UploadFile = File(...)):
    content = await file.read()
    _validate_file(file.filename, len(content))
    return StreamingResponse(
        _stream_generator(content, file.filename),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
