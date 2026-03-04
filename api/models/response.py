from pydantic import BaseModel, Field
from agents.models import AttackScenario


class HealthResponse(BaseModel):
    status: str = "healthy"


class StepStatus(BaseModel):
    step: str
    status: str  # pending / in_progress / completed / error
    message: str = ""


class PolicyResult(BaseModel):
    status: str
    result_message: str = ""  # 예: "정책 검증완료. 위반 N개, 권장 M개."
    total_checks: int = 0
    violations: list[dict] = []
    recommendations: list[dict] = []
    summary: str = ""



class SecurityResult(BaseModel):
    final_report: str = ""  # 통합 해설 보고서 (Markdown)
    vulnerability_summary: int = 0
    severity_counts: dict = {}  # {"Critical": X, "High": Y, "Medium": Z, "Low": W}
    verification_checklist: list[str] = []
    attack_scenarios: list[AttackScenario] = []


class AnalyzeResponse(BaseModel):
    status: str  # success / error
    task_id: str = ""
    steps: list[StepStatus] = []
    security: SecurityResult | None = None
    error: str | None = None
