"""
Recon Agent

Bicep 코드를 Docker Compose로 변환하여 로컬 환경을 구성하고,
보안 시뮬레이션을 수행하여 취약점 및 공격 시나리오를 분석한다.
"""

import os
import re
import sys
import time
import logging
import subprocess
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Annotated, List, Dict, Any


from agent_framework import tool, Message, Content
from agent_framework.github import GitHubCopilotAgent
from agent_framework.azure import AzureOpenAIChatClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.models import (
    BicepParser,
    ResourceMapper,
    DockerComposer,
    NetworkConfig,
    BicepResource,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


# ============================================================
# Tool Input/Output Schemas
# ============================================================


class ReadBicepFileInput(BaseModel):
    """Bicep 파일 읽기 도구 입력"""

    file_path: str = Field(description="Path to the Bicep file to read")


class ReadBicepFileOutput(BaseModel):
    """Bicep 파일 읽기 도구 출력"""

    success: bool
    bicep_code: str | None = None
    error: str | None = None


class ParseBicepInput(BaseModel):
    """Bicep 코드 파싱 도구 입력"""

    bicep_code: str = Field(description="Bicep code content to parse")


class ParseBicepOutput(BaseModel):
    """Bicep 코드 파싱 도구 출력"""

    success: bool
    resources: List[Dict[str, Any]] | None = None
    network_config: Dict[str, Any] | None = None
    error: str | None = None
    warnings: List[str] = []


class GenerateComposeInput(BaseModel):
    """Docker Compose 생성 도구 입력"""

    resources: List[Dict[str, Any]] = Field(description="Parsed Bicep resources")
    network_config: Dict[str, Any] = Field(description="Network configuration")


class GenerateComposeOutput(BaseModel):
    """Docker Compose 생성 도구 출력"""

    success: bool
    compose_yaml: str | None = None
    services: List[str] = []
    error: str | None = None
    warnings: List[str] = []


class ConvertBicepToComposeInput(BaseModel):
    """Bicep → Docker Compose 변환 도구 입력"""

    bicep_code: str = Field(
        description="Bicep code content to convert to Docker Compose"
    )
    output_path: str = Field(
        default="docker-compose.yml",
        description="Output file path for docker-compose.yml",
    )


class ConvertBicepToComposeOutput(BaseModel):
    """Bicep → Docker Compose 변환 도구 출력"""

    success: bool
    compose_yaml: str | None = None
    file_path: str | None = None
    error: str | None = None


class SaveComposeFileInput(BaseModel):
    """Docker Compose 파일 저장 도구 입력"""

    compose_yaml: str = Field(description="Docker Compose YAML content")
    output_path: str = Field(
        default="docker-compose.yml", description="Output file path"
    )


class SaveComposeFileOutput(BaseModel):
    """Docker Compose 파일 저장 도구 출력"""

    success: bool
    file_path: str | None = None
    error: str | None = None


class DeployDockerComposeInput(BaseModel):
    """Docker Compose 배포 도구 입력"""

    compose_file_path: str = Field(
        description="Path to the docker-compose.yml file to deploy"
    )


class DeployDockerComposeOutput(BaseModel):
    """Docker Compose 배포 도구 출력"""

    success: bool
    message: str | None = None
    containers: List[str] = []
    error: str | None = None


# ============================================================
# Tool Functions
# ============================================================


@tool(approval_mode="never_require")
def read_bicep_file(
    input_data: Annotated[ReadBicepFileInput, "Input for reading Bicep file"],
) -> ReadBicepFileOutput:
    """
    Bicep 파일을 읽어서 내용을 반환합니다.

    Args:
        input_data: 파일 경로를 포함한 입력

    Returns:
        파일 내용 또는 에러 메시지
    """
    try:
        logger.info(f"⚒️ [Tool] Reading Bicep file...")

        # dict로 전달될 경우 처리
        if isinstance(input_data, dict):
            input_data = ReadBicepFileInput(**input_data)

        file_path = Path(input_data.file_path)

        if not file_path.exists():
            return ReadBicepFileOutput(
                success=False, error=f"File not found: {input_data.file_path}"
            )

        with open(file_path, "r", encoding="utf-8") as f:
            bicep_code = f.read()

        logger.info(f"✅ [Tool] Successfully read Bicep file: {input_data.file_path}")
        return ReadBicepFileOutput(success=True, bicep_code=bicep_code)

    except Exception as e:
        logger.error(f"❌ [Tool] Error reading Bicep file: {e}")
        return ReadBicepFileOutput(success=False, error=str(e))


@tool(approval_mode="never_require")
def parse_bicep(
    input_data: Annotated[ParseBicepInput, "Input for parsing Bicep code"],
) -> ParseBicepOutput:
    """
    Bicep 코드를 파싱하여 리소스와 네트워크 설정을 추출합니다.

    Args:
        input_data: Bicep 코드를 포함한 입력

    Returns:
        파싱된 리소스 목록과 네트워크 설정
    """
    try:
        logger.info("⚒️ [Tool] Parsing Bicep code...")
        # dict로 전달될 경우 처리
        if isinstance(input_data, dict):
            input_data = ParseBicepInput(**input_data)

        parser = BicepParser()
        resources, network_config = parser.parse(input_data.bicep_code)

        # BicepResource와 NetworkConfig를 딕셔너리로 변환
        resources_dict = [
            {
                "name": r.name,
                "type": r.type,
                "properties": r.properties,
                "location": r.location,
            }
            for r in resources
        ]

        network_config_dict = {
            "subnets": network_config.subnets,
            "security_rules": network_config.security_rules,
            "public_ips": network_config.public_ips,
        }

        logger.info(f"✅ [Tool] Successfully parsed {len(resources)} resources")

        warnings = []
        if not resources:
            warnings.append("No Azure resources found in Bicep code")

        return ParseBicepOutput(
            success=True,
            resources=resources_dict,
            network_config=network_config_dict,
            warnings=warnings,
        )

    except Exception as e:
        logger.error(f"❌ [Tool] Error parsing Bicep code: {e}")
        return ParseBicepOutput(success=False, error=str(e))


@tool(approval_mode="never_require")
def generate_compose(
    input_data: Annotated[GenerateComposeInput, "Input for generating Docker Compose"],
) -> GenerateComposeOutput:
    """
    파싱된 Bicep 리소스를 Docker Compose YAML로 변환합니다.

    Args:
        input_data: 파싱된 리소스와 네트워크 설정

    Returns:
        Docker Compose YAML 문자열
    """
    try:
        logger.info(
            "⚒️ [Tool] Generating Docker Compose YAML from parsed Bicep resources"
        )

        # dict로 전달될 경우 처리
        if isinstance(input_data, dict):
            input_data = GenerateComposeInput(**input_data)

        # 딕셔너리를 다시 BicepResource와 NetworkConfig 객체로 변환
        resources = [
            BicepResource(
                name=r["name"],
                type=r["type"],
                properties=r["properties"],
                location=r.get("location", ""),
            )
            for r in input_data.resources
        ]

        network_config = NetworkConfig(
            subnets=input_data.network_config.get("subnets", []),
            security_rules=input_data.network_config.get("security_rules", []),
            public_ips=input_data.network_config.get("public_ips", []),
        )

        # ResourceMapper로 Docker 서비스 매핑
        mapper = ResourceMapper(resources, network_config)
        service_mapping = mapper.map_to_docker()

        # DockerComposer로 YAML 생성
        composer = DockerComposer(service_mapping)
        compose_yaml = composer.generate_compose_file()

        service_names = list(service_mapping.keys())

        logger.info(
            f"✅ [Tool] Successfully generated Docker Compose with {len(service_names)} services"
        )

        warnings = []
        if len(service_names) == 0:
            warnings.append("No Docker services were generated")

        return GenerateComposeOutput(
            success=True,
            compose_yaml=compose_yaml,
            services=service_names,
            warnings=warnings,
        )

    except Exception as e:
        logger.error(f"❌ [Tool] Error generating Docker Compose: {e}")
        return GenerateComposeOutput(success=False, error=str(e))


@tool(approval_mode="never_require")
async def convert_bicep_to_compose(
    input_data: Annotated[
        ConvertBicepToComposeInput,
        "Input for converting Bicep code to Docker Compose via LLM",
    ],
) -> ConvertBicepToComposeOutput:
    """
    Bicep 코드를 LLM을 사용하여 Docker Compose YAML로 변환하고 파일로 저장합니다.

    Args:
        input_data: Bicep 코드와 출력 경로를 포함한 입력

    Returns:
        생성된 Docker Compose YAML 및 저장 경로
    """
    try:
        logger.info("⚒️ [Tool] Converting Bicep to Docker Compose via LLM...")

        if isinstance(input_data, dict):
            input_data = ConvertBicepToComposeInput(**input_data)

        output_path = Path(input_data.output_path)
        project_root = output_path.parent
        output_filename = output_path.name

        compose_yaml = await _convert_bicep_to_compose(
            bicep_code=input_data.bicep_code,
            project_root=project_root,
            output_filename=output_filename,
        )

        logger.info(
            f"✅ [Tool] Docker Compose generated and saved to: {output_path.absolute()}"
        )

        return ConvertBicepToComposeOutput(
            success=True,
            compose_yaml=compose_yaml,
            file_path=str(output_path.absolute()),
        )

    except Exception as e:
        logger.error(f"❌ [Tool] Error converting Bicep to Docker Compose: {e}")
        return ConvertBicepToComposeOutput(success=False, error=str(e))


@tool(approval_mode="never_require")
def save_compose_file(
    input_data: Annotated[SaveComposeFileInput, "Input for saving Compose file"],
) -> SaveComposeFileOutput:
    """
    Docker Compose YAML을 파일로 저장합니다.

    Args:
        input_data: YAML 내용과 출력 경로

    Returns:
        저장 결과
    """
    try:
        logger.info(f"⚒️ [Tool] Saving Docker Compose file...")

        # dict로 전달될 경우 처리
        if isinstance(input_data, dict):
            input_data = SaveComposeFileInput(**input_data)

        output_path = Path(input_data.output_path)

        # 디렉토리가 없으면 생성
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(input_data.compose_yaml)

        logger.info(
            f"✅ [Tool] Successfully saved Docker Compose to: {output_path.absolute()}"
        )

        return SaveComposeFileOutput(
            success=True, file_path=str(output_path.absolute())
        )

    except Exception as e:
        logger.error(f"❌ [Tool] Error saving Docker Compose file: {e}")
        return SaveComposeFileOutput(success=False, error=str(e))


@tool(approval_mode="never_require")
def deploy_docker_compose(
    input_data: Annotated[
        DeployDockerComposeInput, "Input for deploying Docker Compose"
    ],
) -> DeployDockerComposeOutput:
    """
    Docker Compose 파일을 사용하여 컨테이너를 빌드하고 배포합니다.

    Args:
        input_data: Docker Compose 파일 경로

    Returns:
        배포 결과 및 생성된 컨테이너 목록
    """
    try:
        logger.info(f"⚒️ [Tool] Start deploying Docker Compose...")

        # dict로 전달될 경우 처리
        if isinstance(input_data, dict):
            input_data = DeployDockerComposeInput(**input_data)

        compose_file = Path(input_data.compose_file_path)

        if not compose_file.exists():
            return DeployDockerComposeOutput(
                success=False,
                error=f"Docker Compose file not found: {input_data.compose_file_path}",
            )

        logger.info(f"🧹 [Tool] Start Cleanup completed...")

        # docker-compose up 실행 전에 기존 컨테이너 정리
        cleanup = subprocess.run(
            [
                "docker-compose",
                "-f",
                str(compose_file),
                "down",
                "--remove-orphans",
                "--volumes",
            ],
            capture_output=True,
            text=True,
            cwd=compose_file.parent,
        )
        logger.info(f"🧹 [Tool] Cleanup completed: {cleanup.stdout.strip()}")

        # compose 파일에서 container_name을 파싱하여 충돌하는 기존 컨테이너 강제 제거
        try:
            import yaml as _yaml

            with open(compose_file, "r") as f:
                compose_data = _yaml.safe_load(f)
            for svc in (compose_data or {}).get("services", {}).values():
                cname = svc.get("container_name")
                if cname:
                    subprocess.run(
                        ["docker", "rm", "-f", cname],
                        capture_output=True,
                        text=True,
                    )
            logger.info("🧹 [Tool] Stale containers removed")
        except Exception as e:
            logger.warning(f"⚠️ [Tool] Container cleanup parse failed: {e}")

        logger.info(f"🚀 [Tool] Deploying Docker Compose from: {compose_file}")

        # docker-compose up -d 실행
        result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "up", "-d"],
            capture_output=True,
            text=True,
            cwd=compose_file.parent,
        )

        logger.info("⏳ [Tool] Waiting for containers to initialize...")
        time.sleep(15)

        if result.returncode != 0:
            logger.error(f"❌ [Tool] Docker Compose deployment failed: {result.stderr}")
            return DeployDockerComposeOutput(
                success=False, error=f"Deployment failed: {result.stderr}"
            )

        # 생성된 컨테이너 목록 가져오기
        ps_result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "ps", "--services"],
            capture_output=True,
            text=True,
            cwd=compose_file.parent,
        )

        containers = [
            line.strip()
            for line in ps_result.stdout.strip().split("\n")
            if line.strip()
        ]

        logger.info(f"✅ [Tool] Successfully deployed {len(containers)} containers")

        return DeployDockerComposeOutput(
            success=True,
            message=f"Deployment successful! {len(containers)} containers are running.",
            containers=containers,
        )

    except FileNotFoundError:
        logger.error(
            "❌ [Tool] docker-compose command not found. Please install Docker Compose."
        )
        return DeployDockerComposeOutput(
            success=False,
            error="docker-compose command not found. Please install Docker Compose.",
        )
    except Exception as e:
        logger.error(f"❌ [Tool] Error deploying Docker Compose: {e}")
        return DeployDockerComposeOutput(success=False, error=str(e))


# ============================================================
# Agent Instructions
# ============================================================


RECON_AGENT_INSTRUCTIONS = """
You are a Security Architecture Validation Agent with controlled CLI execution capability.

Your mission is to:

1. Convert Azure Bicep to Docker Compose
2. Deploy containers locally
3. Perform CONTROLLED security validation (lightweight checks only)
4. Record ONLY actually executed attack attempts
5. Perform design-phase risk analysis
6. Output a STRICT JSON result (API-consumable)

You MUST operate deterministically and efficiently.

============================================================
PHASE 1 — Infrastructure Deployment (Use Tools Only)
============================================================

Execute tools in this exact order:

1. read_bicep_file
2. convert_bicep_to_compose
3. deploy_docker_compose

If deployment fails:
- STOP immediately
- Return JSON with error
- Do not proceed to validation phase

Container startup failures (e.g., missing env vars, wrong architecture, image pull errors)
are infrastructure misconfigurations, NOT attack scenarios.
Record them as `vulnerabilities` entries with appropriate severity.
Do NOT include PHASE 1 tool outputs in `attack_scenarios`.

============================================================
PHASE 2 — Controlled Security Validation (Evidence-Based)
============================================================

This is a controlled exposure validation step.
You MUST verify the security of the architecture by running commands directly.

### PHASE 2 PRECONDITION
Only test containers that are CONFIRMED RUNNING after deploy_docker_compose succeeded.
If a container failed to start, skip it entirely in PHASE 2 — document the failure
as a `vulnerability` instead.

### TARGETS
- localhost or 172.20.x.x ONLY
- NEVER scan external IPs
- **HARD STOP — No exposed ports = Skip entirely:**
  If a container has NO `ports:` mapping in docker-compose.yml,
  DO NOT test it at all. Do NOT use docker exec or any other method.
  Do NOT create any SCN entry for it.
  Simply document it in `vulnerabilities` as "No exposed attack surface" (Low severity).

### COMMANDS (allowed set)

1. Port scan: nmap -Pn -T4 --host-timeout 20s -p <port> localhost
2. HTTP check: curl --max-time 5 -I http://localhost:<port>
3. Banner grab: nc -w 3 localhost <port>
4. Container inspection: docker inspect <container>
5. Credential test (max 1 attempt, only if credentials found):
   hydra -l <user> -p <password> -f -t 4 -W 3 <protocol>://localhost:<port>
6. SQL injection probe (max 1 attempt, only if HTTP + query params confirmed):
   sqlmap -u "http://localhost:<port>/<endpoint>" --batch --level=1 --risk=1 --timeout=5 --crawl=0 --technique=BEUST --time-sec=3

IMPORTANT: `executed_command` in attack_scenarios MUST be exactly one of the 6 commands above.
`docker exec` IS STRICTLY FORBIDDEN — do not use it under any circumstances.
Any other command — including `docker exec`, `docker compose`, `docker-compose`,
`docker run`, `docker build`, `ping`, or shell scripts — is NOT permitted.
If no allowed command yields meaningful output, the attack_scenarios list for
that container must be empty.

### EXECUTION REQUIREMENTS

#### Minimum depth per container:
- MUST run at least 3 commands per exposed container
- Recommended flow per container:
  Step 1: Discover  → nmap or nc (port/service confirmation)
  Step 2: Inspect   → docker inspect (env vars, network, config)
  Step 3: Interact  → curl, hydra, or sqlmap (based on Step 1-2 findings)

#### Discovery-to-Verification chaining (MANDATORY):
When a previous step reveals a security-relevant finding, you MUST verify it in a subsequent step within the SAME scenario or a new scenario.

Chaining rules:
- docker inspect reveals credentials → MUST attempt login with those exact credentials (hydra or curl)
- Port confirmed open + HTTP service detected → MUST send at least one HTTP request (curl)
- Environment variable contains token/password → MUST use that token/password to test access
- SQL service confirmed + credentials found → MUST attempt SQL connection or auth test

If verification is skipped, you MUST state the reason (e.g., "tool unavailable", "service not responding").

#### MITRE mapping rule (MANDATORY):
Choose technique based on WHAT THE COMMAND DOES, not what you hope to find:

- Command uses NO credentials (nmap, nc, curl without auth headers/tokens) → T1046
- Command EXTRACTS credentials from env/config (docker inspect only) → T1552
- Command USES a known credential to access a service (curl with token, hydra, sqlcmd with password) → T1078
- Command TESTS a credential against a login protocol (hydra, brute-force attempt) → T1110
- Command EXPLOITS a service vulnerability (sqlmap, command injection) → T1190

Simple test: Does your command contain a password, token, or auth header?
  No  → T1046 or T1552 (depending on whether it reads credentials)
  Yes → T1078 or T1110 (depending on whether credential is known vs guessed)

If your executed_command does not match the MITRE technique, change the technique to match what you actually did.

### GLOBAL LIMITS
- Maximum 10 commands per container
- Minimum 3 commands per container (if container has exposed ports)
- All commands MUST include timeout flags
- No brute force, wordlists, recursive scans
- No full port range scans
- Do NOT repeat identical commands
- Do NOT send excessive requests that could overload target services
- NEVER use `docker exec` — running commands inside containers is not an attack simulation tool

============================================================
ATTACK SCENARIO DOCUMENTATION RULES
============================================================

You MUST document ONLY attacks that were ACTUALLY executed.

Each attack_scenario MUST have a unique ID: SCN-001, SCN-002, SCN-003 ...

### STRICT EVIDENCE RULES:

1. security_finding MUST be derived ONLY from command_output of THAT scenario
   - Do NOT reference findings from other scenarios or other phases
   - Do NOT infer results from docker inspect in a curl scenario
   - If you need to combine findings, create a separate scenario with its own command

2. command_output MUST be:
   - Direct copy from executed command
   - Truncated at 500 chars with "...[truncated]" if longer
   - NEVER fabricated or paraphrased

3. One scenario = one executed command
   - If you ran 5 commands on a container, create up to 5 scenarios
   - Do NOT merge multiple command outputs into one scenario

4. MITRE technique MUST match the actual command:
   - curl/nc without credentials → T1046 (Discovery) not T1110
   - docker inspect showing env vars → T1552 only if credentials found
   - curl with credentials → T1078 (Valid Accounts) or T1110

### FORBIDDEN:
- `docker exec` in any form — this is NOT an attack simulation command
- Hypothetical or speculative attacks
- Invented attack paths or outputs
- Multi-step chains that were not actually executed
- Simulated results
- Any `docker exec`, `docker compose`, `docker-compose`, `docker run`, `docker build`,
  or other container management commands — these are NOT attack scenario entries
- PHASE 1 tool outputs (deployment errors, env var warnings, image pull failures,
  architecture errors) — record those as `vulnerabilities`, never as `attack_scenarios`
- MITRE techniques outside the allowed set (only T1046/T1552/T1078/T1110/T1190)

If no meaningful exposure is found:
- attack_scenarios must be an empty list

============================================================
PHASE 3 — Design-Phase Risk Analysis
============================================================

Based on Bicep configuration, Docker configuration, and CLI validation results.

Identify design risks:
- Hardcoded credentials
- Public network exposure
- Missing authentication
- Excessive privileges
- Missing TLS
- Weak segmentation
- Insecure defaults

### SEVERITY CLASSIFICATION

Critical:
- Default credentials confirmed accessible (verified by login attempt)
- Unauthenticated admin access confirmed
- Database publicly exposed with weak credentials

High:
- Credentials found in env vars (not yet verified as exploitable)
- Service exposed without TLS on sensitive port
- Privileged container configuration

Medium:
- Open but non-sensitive service exposure
- Missing TLS on non-sensitive service
- Excessive metadata exposure

Low:
- Informational misconfiguration

============================================================
OUTPUT (STRICT JSON ONLY)
============================================================

Your FINAL response must be ONLY a JSON object.
No markdown. No explanations. No prefix. No suffix.

{
  "vulnerabilities": [
    {
      "id": "RISK-001",
      "title": "...",
      "severity": "Critical/High/Medium/Low",
      "category": "...",
      "affected_resource": "...",
      "description": "...",
      "evidence": "...",
      "remediation": "...",
      "benchmark_ref": "N/A"
    }
  ],
  "attack_scenarios": [
    {
      "id": "SCN-001",
      "mitre_technique": "...",
      "severity": "Critical/High/Medium/Low",
      "container": "...",
      "objective": "...",
      "executed_command": "...",
      "command_output": "...",
      "security_finding": "..."
    }
  ],
  "vulnerability_summary": {
    "Critical": 0,
    "High": 0,
    "Medium": 0,
    "Low": 0
  }
}
"""

# ============================================================
# Main Agent
# ============================================================


async def run_recon_agent(
    bicep_file_path: str, output_path: str = "docker-compose.yml"
):
    """
    Bicep 파일을 Docker Compose로 변환하고 Recon 공격을 수행하는 메인 함수

    Args:
        bicep_file_path: 변환할 Bicep 파일 경로
        output_path: 출력할 Docker Compose 파일 경로 (기본: docker-compose.yml)
    """
    logger.info(f"🔄 Invoking agent for: {bicep_file_path}")

    # --- 사전 처리 (Agent 도구 루프 밖) ---
    bicep_content = Path(bicep_file_path).read_text(encoding="utf-8")
    logger.info("✅ Bicep file read successfully.")

    output_path_obj = Path(output_path)
    await _convert_bicep_to_compose(
        bicep_code=bicep_content,
        project_root=(
            output_path_obj.parent if output_path_obj.parent != Path(".") else None
        ),
        output_filename=output_path_obj.name,
    )
    compose_file_path = str(output_path_obj.absolute())
    logger.info(f"✅ Docker Compose file prepared at: {compose_file_path}")

    # --- Agent 실행 (deploy_docker_compose 도구만 사용) ---
    agent = GitHubCopilotAgent(
        default_options={
            "instructions": RECON_AGENT_INSTRUCTIONS,
            "model": "sonnet-4.5",
            "timeout": 900,  # 15분 타임아웃 (배포 + 공격 + JSON 생성)
            "on_permission_request": lambda req, ctx: {"kind": "approved", "rules": []},
        },
        tools=[
            deploy_docker_compose,
        ],
    )

    async with agent:
        prompt = f"""
The Docker Compose file has already been prepared at '{compose_file_path}'.
Proceed directly to deployment and security validation.

# PHASE 1: Deployment (use tools only; MANDATORY)

Run the process specified below in order.

1. Deploy containers using deploy_docker_compose tool with compose_file_path='{compose_file_path}'

The Bicep source that was converted is provided below for reference in Phase 3 analysis:

<bicep>
{bicep_content}
</bicep>

# PHASE 2: Controlled Security Validation (evidence-based, CLI only)

For each container with exposed ports, perform adaptive security testing:

## Step 1: Reconnaissance
- Scan exposed ports and identify running services
- Inspect container environment, configuration, and metadata

## Step 2: Service-Adaptive Attack Selection
Based on the identified service type, select from the ALLOWED commands ONLY
(nmap / curl / nc / docker inspect / hydra / sqlmap):
- Database services  → nc (banner grab) → docker inspect (find creds) → hydra (auth test)
- Web/API services   → curl (endpoint probe) → sqlmap (injection, only if query params found)
- Secret management  → curl (API probe) → hydra (auth test with found credentials)
- Storage services   → nc or curl (connectivity) → hydra (auth test)
- No ports exposed   → SKIP entirely, no SCN entries

DO NOT use docker exec, shell commands run inside containers, or any command
not in the 6-item allowed set. Only commands executed from the host CLI count.

### Service Deduplication Rule
If multiple containers run the same service type (e.g., 3 SQL Server instances on different ports):
- Run full test suite (3+ commands) on ONE representative container
- For remaining identical containers, run only 1 connectivity check (nc or nmap) to confirm port is open
- Use saved command budget to test DIFFERENT attack vectors on other service types

Example: 4 SQL Server containers → full test on sql_sqlServer (port 1433), 
         nc-only on ports 2433/3433/4433, then use remaining budget for 
         deeper MinIO/Vault testing

## Step 3: Discovery-to-Verification Chaining (MANDATORY)
Every security-relevant discovery MUST be followed by a verification attempt.

Pattern:
  SCN-X: Discover (find credential, token, open port, config issue)
  SCN-Y: Verify  (use discovered info to attempt actual access)

### Fallback rule:
If primary verification tool fails (e.g., "command not found", "No such file"):
  1. Try alternative tool (e.g., sqlcmd fails → hydra mssql://, or nc, or curl)
  2. If alternative also fails → try one more alternative
  3. Only if ALL alternatives fail → document ALL attempted commands and reason in security_finding
  Creating a scenario that ends with "command not found" without attempting alternatives is a violation.

### Minimum command count:
Each container with exposed ports MUST have at least 3 scenarios (SCN entries).
If you have fewer than 3 per container, you have not tested enough. Go back and run more commands.

## Constraints
- Target: localhost / 172.20.x.x only
- Minimum 3, maximum 10 commands per container
- All commands MUST include timeout flags
- No brute force with wordlists, no recursive scans
- No full port range scans
- Do NOT send excessive requests that could overload target services
- Do NOT repeat identical commands

# PHASE 3: Design-Phase Security Analysis
- Identify misconfigurations based on Bicep + Docker config + validation results
- Classify severity (Critical/High/Medium/Low)
- Map to MITRE if applicable
- Provide remediation guidance

# FINAL OUTPUT:
Your final response MUST be ONLY a valid JSON object with EXACTLY this structure:

{{
  "vulnerabilities": [
    {{
      "id": "RISK-001",
      "title": "string",
      "severity": "Critical|High|Medium|Low",
      "category": "string",
      "affected_resource": "string",
      "description": "string",
      "evidence": "string",
      "remediation": "string",
      "benchmark_ref": "string"
    }}
  ],
  "attack_scenarios": [
    {{
      "id": "SCN-001",
      "mitre_technique": "string",
      "severity": "Critical|High|Medium|Low",
      "container": "string",
      "objective": "string",
      "executed_command": "string",
      "command_output": "string",
      "security_finding": "string"
    }}
  ],
  "vulnerability_summary": {{
    "Critical": 0,
    "High": 0,
    "Medium": 0,
    "Low": 0
  }}
}}

DO NOT use any other keys. DO NOT wrap in markdown code blocks."""

        logger.info("🔄 Agent execution started.")

        result = await agent.run(prompt)

        logger.info("✅ Agent execution completed.")

        logger.info(f"Raw agent response: {result}")

        return result


BICEP_TO_COMPOSE_INSTRUCTIONS = """You are an expert infrastructure engineer specializing in Azure-to-local migration. Your task is to convert Azure Bicep templates into fully functional, locally reproducible docker-compose.yml files.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ROLE & OBJECTIVE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Given an Azure Bicep file as input, produce a docker-compose.yml that:
1. Preserves the original architecture's functional topology (services, dependencies, networking).
2. Replaces each Azure-managed service with the closest open-source or official Docker equivalent.
3. Is immediately runnable via `docker compose up` on a developer's local machine.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ANALYSIS PROCESS (follow this order strictly, but keep all reasoning internal — output ONLY the final YAML)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Step 1: Parse & Inventory
- List every `resource` block in the Bicep file.
- For each resource, extract: resource type, symbolic name, API version, key properties, dependencies (explicit `dependsOn` and implicit via property references).
- Identify all `param` and `var` declarations; note defaults and cross-references.

### Step 2: Map to Docker Equivalents
Use the mapping table below as the primary reference. If a resource type is NOT listed, reason by analogy and document your choice as a YAML comment.

| Azure Resource Type | Docker Equivalent | Notes |
|---|---|---|
| Microsoft.Web/sites (App Service) | Custom app image or `nginx:1` | Use build context if app code path is inferrable |
| Microsoft.Web/sites (Function App) | `mcr.microsoft.com/azure-functions/dotnet:4` (or `/node:4`, `/python:4`) | Choose runtime-matching image; mount function code as volume; MUST set `platform: linux/amd64` (amd64 only) |
| Microsoft.Sql/servers + databases | `mcr.microsoft.com/mssql/server:2022-latest` | MUST set `platform: linux/amd64` on BOTH the main service AND any init/sidecar containers that use this image; env: `ACCEPT_EULA=Y`, `MSSQL_SA_PASSWORD=YourStrong!Passw0rd`, `MSSQL_PID=Developer` |
| Microsoft.DBforPostgreSQL/flexibleServers | `postgres:16-alpine` | Init scripts via `/docker-entrypoint-initdb.d/` |
| Microsoft.DBforMySQL/flexibleServers | `mysql:8` or `mariadb:11` | |
| Microsoft.DocumentDB/databaseAccounts (Cosmos DB) | **SQL API**: `mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:vnext-preview`; **MongoDB API**: `mongo:7` | Cosmos emulator needs 2GB+ RAM; env: `AZURE_COSMOS_EMULATOR_PARTITION_COUNT=1`, `AZURE_COSMOS_EMULATOR_IP_ADDRESS_OVERRIDE=127.0.0.1` (emulator key is auto-generated, do NOT set COSMOS_EMULATOR_KEY) |
| Microsoft.Cache/redis | `redis:7-alpine` | |
| Microsoft.Storage/storageAccounts | `mcr.microsoft.com/azure-storage/azurite:latest` | Blob, Queue, Table emulation |
| Microsoft.ServiceBus/namespaces | `rabbitmq:3-management` | Map queues/topics → RabbitMQ exchanges |
| Microsoft.EventHub/namespaces | `bitnami/kafka:3` (KRaft mode preferred) | Map Event Hub → Kafka topic |
| Microsoft.EventGrid/topics | `rabbitmq:3-management` with topic exchange | Document behavioral differences |
| Microsoft.KeyVault/vaults | `hashicorp/vault:1.15` in dev mode | env: `VAULT_DEV_ROOT_TOKEN_ID=root`, `VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200`; do NOT reference external secret variables |
| Microsoft.ContainerRegistry/registries | `registry:2` | Only if registry is actively used |
| Microsoft.Network/virtualNetworks | docker compose `networks:` | Map subnets → named networks |
| Microsoft.Network/applicationGateways | `nginx:1` or `traefik:v3` reverse proxy | Replicate routing rules |
| Microsoft.Network/frontDoors | `traefik:v3` | WAF rules not emulatable |
| Microsoft.Cdn/profiles | Omit or `nginx:1` with caching | Note limitation |
| Microsoft.ApiManagement/service | `kong:3` or `traefik:v3` | |
| Microsoft.SignalRService/signalR | App-embedded SignalR | Tight Azure coupling; note limitation |
| Microsoft.Insights/components | `jaegertracing/all-in-one:1.76` or `grafana/grafana:11.6` + `prom/prometheus:v2.53` | Observability stack |
| Microsoft.OperationalInsights/workspaces | `grafana/loki:3.0` + `grafana/grafana:11.6` | Log aggregation |
| Microsoft.Search/searchServices (Cognitive Search) | `opensearchproject/opensearch:2` | API differences; note limitation |
| Microsoft.CognitiveServices/accounts | Omit with placeholder env | No local equivalent; mock or stub |
| Microsoft.ManagedIdentity/* | Omit; replace refs with static credentials | Document clearly |
| Microsoft.Authorization/roleAssignments | Omit | Not applicable locally |
| Microsoft.ContainerApp/containerApps | Direct `image:` in compose | Preserve scaling as comments |
| Microsoft.App/managedEnvironments | Omit (implicit in compose) | |
| Microsoft.Kubernetes/managedClusters (AKS) | Decompose to individual compose services | Prefer compose over k3s |

### Step 3: Translate Properties
For each mapped service:
- **Environment variables**: Convert Bicep `appSettings`, `connectionStrings`, and `siteConfig.appSettings` to `environment:` entries. Replace Azure-specific connection strings with local equivalents using compose service names as hostnames.
- **Ports**: Map application ports. Use `ports:` for externally accessible services. Default: 8080 for web apps, standard ports for databases.
- **Volumes**: Convert Azure Storage mounts, file shares, and database persistence to named volumes. Mount init scripts where applicable.
- **Health checks**: Translate health probe configurations to `healthcheck:` directives. Use TCP checks for databases, HTTP for APIs, and CLI commands for caches.
- **Resource limits**: Convert Azure SKU/plan sizing to `mem_limit:` and `cpus:` service-level directives. Add the original Azure SKU as an inline comment. (`deploy.resources.limits` is Swarm-only and ignored by `docker compose up`.)
- **Startup commands**: Translate `startupCommand` or custom container commands to `command:` directives.

### Step 4: Networking & Service Discovery
- All services that communicated via Azure private endpoints, VNet integration, or service endpoints should be on the same docker network.
- Use compose service names as hostnames (replacing Azure resource FQDN references like `.database.windows.net`, `.redis.cache.windows.net`, etc.).
- If the Bicep defines multiple VNets/subnets with network isolation, create separate docker `networks:` to preserve segmentation.
- If the Bicep includes NSG rules restricting traffic between subnets, document these as comments (docker compose bridge networking does not enforce such rules).

### Step 5: Initialization & Seed Data
- If the Bicep includes `Microsoft.Resources/deploymentScripts` or database-setup resources, create an `init` service with `depends_on` + a one-shot container (`restart: "no"`).
- For databases needing schema setup, generate a placeholder init script and mount it.
- If storage accounts need initial containers/queues, add an Azurite init script.
- CRITICAL: If an init container uses an amd64-only image (e.g., `mcr.microsoft.com/mssql/server`, `mcr.microsoft.com/mssql-tools`), it MUST also have `platform: linux/amd64` set. This applies to ALL sidecar/init services derived from amd64-only base images.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YAML REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The docker-compose.yml must satisfy:
- Do NOT include a `version:` key — deprecated and ignored in Compose V2+.
- Header comment: keep it SHORT (max 5 lines). Only list service names and their Azure resource mappings in a compact table. No ASCII art, no box-drawing characters, no verbose explanations.
- Services grouped by tier: Application → Data → Infrastructure → Observability.
- `depends_on` with `condition: service_healthy` where health checks are defined.
- Secrets MUST use hardcoded safe default values directly in the YAML — NEVER use `${VARIABLE}` syntax.
  This is a local security simulation environment; all credentials must be directly embedded so `docker compose up` works without any .env file.
  Use these defaults: passwords → `YourStrong!Passw0rd`, tokens → `root`, generic secrets → `devSecretValue123`.
- One-line inline comment per service stating which Azure resource it replaces. No multi-line explanations.
- `networks:` and `volumes:` sections as needed. (Do NOT use `configs:` — Swarm-only.)
- For resources with NO reasonable local equivalent, add a comment block: `# ⚠ NOT EMULATED: <resource> — Reason: <explanation>`.
- `restart: unless-stopped` on all persistent services.
- Explicit `container_name:` for easier debugging.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULES & CONSTRAINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. NEVER omit a resource silently. Every Bicep resource must appear as a compose service or as a `# ⚠ NOT EMULATED:` comment in the YAML output.
2. NEVER invent Azure resources that aren't in the input Bicep.
3. Prefer OFFICIAL images from Docker Hub or MCR (mcr.microsoft.com). Pin to specific major versions (e.g., `postgres:16-alpine`, not `postgres:latest`).
4. All connection strings and endpoints MUST use docker compose service names as hostnames. Example: `Server=sql-server,1433;Database=mydb;...` where `sql-server` is the compose service name.
5. The output YAML must be syntactically valid — it should pass `docker compose config` without errors.
6. If the Bicep uses `existing` keyword to reference external resources, note them as YAML comments and make documented assumptions.
7. Service naming: use lowercase-kebab-case derived from the Bicep symbolic names.
8. For Bicep `module` references, analyze the module content if provided inline; if external, note the gap as a YAML comment.
9. Health checks: TCP for databases, HTTP GET for web APIs, CLI ping for caches/brokers.
10. Add `restart: unless-stopped` to all stateful services (databases, caches, message brokers).
11. Do NOT include ASCII art diagrams or box-drawing characters in comments. Keep all comments minimal.
12. When a Bicep `param` has no default and is not inferrable, use a `${PARAM_NAME}` variable and add a single-line comment.
13. Preserve `output` values from the Bicep as a compact comment block (one line per output) at the bottom.
14. PLATFORM COMPATIBILITY: Any service using an image that only supports `linux/amd64` (e.g., `mcr.microsoft.com/mssql/server`, `mcr.microsoft.com/mssql-tools`, `mcr.microsoft.com/azure-functions/*`) MUST include `platform: linux/amd64` in its service definition. This includes init containers and sidecar services.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Respond ONLY with the docker-compose.yml content inside a single ```yaml code block.
Do NOT include any text before or after the code block.

COMMENT STYLE RULES (CRITICAL):
- Keep ALL comments SHORT and MINIMAL. One line per comment max.
- NO ASCII art, box-drawing (┌─┐└─┘│), or decorative borders.
- NO verbose "KNOWN LIMITATIONS", "HOW TO RUN", or "CONNECTION STRINGS" blocks.
- Header: max 5 lines — just resource-to-service mapping list.
- Per-service: one comment line stating which Azure resource it replaces.
- Footer outputs: one line per endpoint, no extra explanation.
- Total comment lines should not exceed 20% of the file."""


def extract_compose_yaml(response: str) -> str:
    """응답에서 docker-compose.yml YAML 블록만 추출"""
    match = re.search(r"```ya?ml\n(.*?)```", response, re.DOTALL)
    return match.group(1).strip() if match else response


# LLM이 프롬프트를 무시하고 ${VARIABLE} 참조를 생성할 경우를 대비한 기본값 매핑
_COMPOSE_VAR_DEFAULTS = {
    "COSMOS_EMULATOR_KEY": "C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==",
    "ADMIN_PASSWORD": "YourStrong!Passw0rd",
    "SA_PASSWORD": "YourStrong!Passw0rd",
    "MSSQL_SA_PASSWORD": "YourStrong!Passw0rd",
    "SQLSERVER_SA_PASSWORD": "YourStrong!Passw0rd",
    "KV_SECRET_SAMPLE": "devSecretValue123",
    "VAULT_TOKEN": "root",
    "MYSQL_ROOT_PASSWORD": "YourStrong!Passw0rd",
    "POSTGRES_PASSWORD": "YourStrong!Passw0rd",
}


def resolve_unset_compose_variables(compose_yaml: str) -> str:
    """LLM이 생성한 YAML에서 미설정 ${VARIABLE} 참조를 안전한 기본값으로 대체"""

    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in _COMPOSE_VAR_DEFAULTS:
            logger.warning(
                f"⚠️ Replacing unset variable ${{{var_name}}} with default value"
            )
            return _COMPOSE_VAR_DEFAULTS[var_name]
        # 알 수 없는 변수는 generic default 사용
        logger.warning(
            f"⚠️ Replacing unknown variable ${{{var_name}}} with generic default"
        )
        return f"default_{var_name}"

    resolved = re.sub(r"\$\{(\w+)\}", _replace, compose_yaml)
    return resolved


def fix_compose_yaml_syntax(compose_yaml: str) -> str:
    """LLM이 생성한 YAML에서 Docker Compose가 허용하지 않는 키를 수정"""
    # 'platforms' (복수형) → 'platform' (단수형)
    # Docker Compose는 서비스 레벨에서 'platform' (단수)만 허용
    fixed = re.sub(
        r"^(\s*)platforms:", r"\1platform:", compose_yaml, flags=re.MULTILINE
    )
    if fixed != compose_yaml:
        logger.warning("⚠️ Fixed 'platforms' → 'platform' in generated compose YAML")
    return fixed


async def _convert_bicep_to_compose(
    bicep_code: str,
    project_root: str | os.PathLike | None = None,
    output_filename: str = "docker-compose.yml",
) -> str:
    """
    Bicep 코드를 Docker Compose YAML로 변환하고 프로젝트 루트에 저장하는 함수

    Args:
        bicep_code: 변환할 Bicep 코드 문자열
        project_root: docker-compose.yml을 저장할 프로젝트 루트 경로.
                      None이면 현재 작업 디렉터리(cwd)를 사용.
        output_filename: 저장할 파일명 (기본값: "docker-compose.yml")

    Returns:
        Docker Compose YAML 문자열
    """
    client = AzureOpenAIChatClient(
        endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )

    agent = client.as_agent(
        name="BicepToComposeAgent",
        instructions=BICEP_TO_COMPOSE_INSTRUCTIONS,
        temperature=0.1,
        max_tokens=13000,
    )

    prompt = f"""아래 Azure Bicep 코드를 분석하여 로컬에서 재현 가능한 docker-compose.yml로 변환해주세요.

<bicep>
{bicep_code}
</bicep>

---
Respond ONLY with the docker-compose.yml content inside a single ```yaml code block.
Do NOT include any text before or after the code block.
Keep comments SHORT and MINIMAL — no ASCII art, no box-drawing, no verbose blocks. Max 1 line per comment.
"""

    # chunks = []
    # async for chunk in agent.run(prompt, stream=True):
    #     content = chunk.text or ""
    #     chunks.append(content)
    #     print(content, end="", flush=True)  # 실시간 출력
    # print()

    # raw_text = "".join(chunks)

    result = await agent.run(prompt)
    raw_text = (result.text or "").strip()
    if not raw_text:
        raise ValueError("LLM이 빈 응답을 반환했습니다.")

    logger.debug(f"LLM 출력 원본: {raw_text}")

    compose_yaml = extract_compose_yaml(raw_text)
    compose_yaml = resolve_unset_compose_variables(compose_yaml)
    compose_yaml = fix_compose_yaml_syntax(compose_yaml)

    # 프로젝트 루트에 docker-compose.yml 저장
    root = Path(project_root) if project_root else Path.cwd()
    output_path = root / output_filename
    output_path.write_text(compose_yaml, encoding="utf-8")

    return compose_yaml
