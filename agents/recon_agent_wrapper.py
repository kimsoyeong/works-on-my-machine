"""
Recon Agent Wrapper: Recon Agent의 JSON 응답을 AnalysisResult로 변환하여 API response로 반환
"""

import re
import json
import logging
import tempfile
from pathlib import Path

from agents.models import AnalysisResult, VulnerabilityItem, AttackScenario
from agents.recon_agent import run_recon_agent

logger = logging.getLogger(__name__)


# ============================================================
# JSON 파싱 함수 (기존 유지)
# ============================================================


def parse_json_to_analysis_result(json_data: dict, bicep_code: str) -> AnalysisResult:
    """
    Recon Agent가 출력한 JSON 데이터를 AnalysisResult로 변환

    Args:
        json_data: Recon Agent가 출력한 JSON 데이터
        bicep_code: 원본 Bicep 코드

    Returns:
        AnalysisResult: API 호환 형식
    """
    vulnerabilities = []
    for v in json_data.get("vulnerabilities", []):
        vulnerabilities.append(
            VulnerabilityItem(
                id=v.get("id", "UNKNOWN"),
                severity=v.get("severity", "Medium"),
                category=v.get("category", "Unknown"),
                affected_resource=v.get("affected_resource", "Unknown"),
                title=v.get("title", "Unknown Vulnerability"),
                description=v.get("description", "No description"),
                evidence=v.get("evidence", "No evidence"),
                remediation=v.get("remediation", "No remediation"),
                benchmark_ref=v.get("benchmark_ref", "N/A"),
            )
        )

    attack_scenarios = []
    for a in json_data.get("attack_scenarios", []):

        attack_scenarios.append(
            AttackScenario(
                id=a.get("id", "UNKNOWN"),
                mitre_technique=a.get("mitre_technique", "N/A"),
                severity=a.get("severity", "Medium"),
                container=a.get("container", "Unknown Container"),
                objective=a.get("objective", ""),
                executed_command=a.get("executed_command", ""),
                command_output=a.get("command_output", ""),
                security_finding=a.get("security_finding", ""),
            )
        )

    # Architecture summary 생성
    vulnerability_summary = json_data.get(
        "vulnerability_summary", {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    )
    architecture_summary = {
        "bicep_resources": len(bicep_code.split("resource ")),
        "total_vulnerabilities": len(vulnerabilities),
        "total_attack_scenarios": len(attack_scenarios),
        "vulnerability_summary": vulnerability_summary,
        "data_source": "JSON (parsed from agent response)",
    }

    return AnalysisResult(
        architecture_summary=architecture_summary,
        vulnerabilities=vulnerabilities,
        attack_scenarios=attack_scenarios,
        raw_results=json_data,
    )


# ============================================================
# Main Wrapper Function
# ============================================================


async def invoke_recon_agent_wrapper(bicep_code: str) -> AnalysisResult:
    """
    Bicep 코드를 분석하고 보안 취약점을 찾아 반환

    Args:
        bicep_code: Bicep 코드 문자열

    Returns:
        AnalysisResult: 구조화된 분석 결과
    """
    logger.info("🔄 Starting Recon Agent Wrapper")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # 1. Bicep 코드를 임시 파일로 저장
        bicep_file = tmpdir_path / "input.bicep"
        bicep_file.write_text(bicep_code)
        logger.info(f"📝 Saved Bicep code to {bicep_file}")

        # 2. Docker Compose 출력 경로 설정
        compose_file = tmpdir_path / "docker-compose.yml"

        # 3. Agent 실행
        agent_response = None
        agent_response_text = ""
        try:
            logger.info("🤖 Running agent...")
            agent_response = await run_recon_agent(str(bicep_file), str(compose_file))

            # AgentResponse 객체를 문자열로 변환
            if hasattr(agent_response, "message"):
                agent_response_text = agent_response.message
            elif hasattr(agent_response, "content"):
                agent_response_text = agent_response.content
            else:
                agent_response_text = str(agent_response)

            logger.info("✅ Agent completed successfully")
            logger.debug(f"Agent response length: {len(agent_response_text)} chars")

        except Exception as e:
            logger.error(f"❌ Agent execution failed: {e}", exc_info=True)
            return AnalysisResult(
                architecture_summary={"error": str(e)},
                vulnerabilities=[],
                attack_scenarios=[],
                raw_results={"error": str(e)},
            )

        # 4. Agent 응답을 JSON으로 파싱 시도
        # Agent가 마지막 응답으로 JSON을 반환했을 것으로 기대
        try:
            # 응답에서 JSON 객체 추출 (```json ... ``` 마크다운 코드 블록 포함 가능)
            json_match = re.search(
                r"```json\s*\n(.*?)\n```", agent_response_text, re.DOTALL
            )
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                # 마크다운 없이 바로 JSON인 경우
                # 마지막 { ... } 블록 찾기
                json_match = re.search(
                    r'(\{[\s\S]*"vulnerabilities"[\s\S]*\})\s*$',
                    agent_response_text,
                    re.DOTALL,
                )
                if json_match:
                    json_str = json_match.group(1).strip()
                else:
                    # 전체 응답이 JSON인지 시도
                    json_str = agent_response_text.strip()

            json_data = json.loads(json_str)
            logger.info(f"✅ Parsed JSON from agent response successfully")
            logger.info(
                f"   - Vulnerabilities: {len(json_data.get('vulnerabilities', []))}"
            )
            logger.info(
                f"   - Attack scenarios: {len(json_data.get('attack_scenarios', []))}"
            )
            return parse_json_to_analysis_result(json_data, bicep_code)

        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"⚠️ JSON parsing failed: {e}")
            logger.warning(f"Agent raw response: {agent_response_text}...")

        # 5. JSON 파싱 실패 시 빈 결과 반환
        logger.error(
            "❌ Could not extract JSON from agent response. Returning empty result."
        )
        return AnalysisResult(
            architecture_summary={
                "bicep_resources": len(bicep_code.split("resource ")),
                "error": "JSON parsing failed",
                "data_source": "fallback (empty)",
            },
            vulnerabilities=[],
            attack_scenarios=[],
            raw_results={"raw_response": agent_response_text[:1000]},
        )


# ============================================================
# Test Function
# ============================================================


async def test_wrapper():
    """Wrapper V2 테스트"""
    bicep_code = """
resource storage 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: 'teststorage'
  location: 'eastus'
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
  }
}
"""

    print("🧪 Testing new_agent_wrapper V2...")
    result = await invoke_recon_agent_wrapper(bicep_code)

    print(f"\n✅ Analysis complete!")
    print(f"   - Vulnerabilities: {len(result.vulnerabilities)}")
    print(f"   - Attack scenarios: {len(result.attack_scenarios)}")
    print(f"   - Data source: {result.architecture_summary.get('data_source')}")
