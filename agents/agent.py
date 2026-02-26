"""
로컬 환경 구현 및 자동 공격 수행 Agent

Bicep 코드를 분석하여 Docker Compose로 로컬 환경을 구축하고,
실제 보안 공격을 수행하는 독립적인 Agent입니다.

GitHub Copilot SDK를 사용하여 동적 공격 전략을 수립합니다.
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import docker
import yaml

# GitHub Copilot SDK (선택적 import - 없으면 fallback)
try:
    from copilot import CopilotClient
    from copilot.tools import define_tool
    from pydantic import BaseModel, Field

    COPILOT_AVAILABLE = True
except ImportError:
    COPILOT_AVAILABLE = False
    logging.warning("GitHub Copilot SDK not available. Using fallback strategy engine.")

logger = logging.getLogger(__name__)


# ============================================================
# 데이터 구조
# ============================================================


@dataclass
class VulnerabilityItem:
    """취약점 항목 (API 호환)"""

    id: str
    severity: str  # Critical / High / Medium / Low
    category: str
    affected_resource: str
    title: str
    description: str
    evidence: str
    remediation: str
    benchmark_ref: str = ""


@dataclass
class AttackScenario:
    """공격 시나리오 (API 호환)"""

    id: str
    name: str
    mitre_technique: str
    target_vulnerabilities: List[str]
    severity: str
    prerequisites: str
    attack_chain: List[str]
    expected_impact: str
    detection_difficulty: str
    likelihood: str


@dataclass
class AnalysisResult:
    """Recon 분석 전체 결과 (API 호환)"""

    architecture_summary: dict
    vulnerabilities: List[VulnerabilityItem]
    attack_scenarios: List[AttackScenario]
    report: str
    raw_results: dict = field(default_factory=dict)

    @property
    def vulnerability_count(self) -> dict:
        counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for v in self.vulnerabilities:
            counts[v.severity] = counts.get(v.severity, 0) + 1
        return counts


@dataclass
class BicepResource:
    """Bicep 리소스 정의"""

    name: str
    type: str
    properties: Dict[str, Any]
    location: str = ""
    depends_on: List[str] = field(default_factory=list)


@dataclass
class NetworkConfig:
    """네트워크 구성"""

    subnets: List[Dict[str, str]] = field(default_factory=list)
    security_rules: List[Dict[str, Any]] = field(default_factory=list)
    public_ips: List[str] = field(default_factory=list)


@dataclass
class AttackResult:
    """공격 결과"""

    tool: str
    target: str
    success: bool
    findings: List[str]
    raw_output: str
    timestamp: str


@dataclass
class DeploymentInfo:
    """배포 정보"""

    compose_file: str
    containers: List[Dict[str, str]]
    networks: List[str]
    volumes: List[str]


# ============================================================
# Phase 1: Bicep 파서
# ============================================================


class BicepParser:
    """Bicep 코드 파싱 및 리소스 추출"""

    # Azure 리소스 타입 패턴
    RESOURCE_PATTERN = re.compile(
        r"resource\s+(\w+)\s+'([^']+)'(?:\s*=\s*\{([\s\S]*?)\n\})", re.MULTILINE
    )

    # 리소스 타입별 주요 속성
    RESOURCE_TYPES = {
        "Microsoft.Compute/virtualMachines": "vm",
        "Microsoft.Network/networkSecurityGroups": "nsg",
        "Microsoft.Network/publicIPAddresses": "publicip",
        "Microsoft.Network/virtualNetworks": "vnet",
        "Microsoft.Storage/storageAccounts": "storage",
        "Microsoft.Sql/servers": "sql",
        "Microsoft.Sql/servers/databases": "database",
        "Microsoft.Web/sites": "webapp",
        "Microsoft.KeyVault/vaults": "keyvault",
        "Microsoft.Network/networkInterfaces": "nic",
        "Microsoft.Web/serverfarms": "appserviceplan",
    }

    def __init__(self):
        self.resources: List[BicepResource] = []
        self.network_config = NetworkConfig()

    def parse(self, bicep_code: str) -> Tuple[List[BicepResource], NetworkConfig]:
        """Bicep 코드 파싱"""
        logger.info("Bicep 코드 파싱 시작")

        # 리소스 추출
        matches = self.RESOURCE_PATTERN.finditer(bicep_code)
        for match in matches:
            resource_name = match.group(1)
            resource_type = match.group(2)
            resource_body = match.group(3)

            # 리소스 타입 정규화
            normalized_type = self._normalize_resource_type(resource_type)

            # 속성 추출
            properties = self._extract_properties(resource_body)

            resource = BicepResource(
                name=resource_name, type=normalized_type, properties=properties
            )
            self.resources.append(resource)

            # 네트워크 설정 추출
            if normalized_type == "nsg":
                self._extract_nsg_rules(resource_body)
            elif normalized_type == "vnet":
                self._extract_subnets(resource_body)
            elif normalized_type == "publicip":
                self.network_config.public_ips.append(resource_name)

        logger.info(
            f"파싱 완료: {len(self.resources)}개 리소스, "
            f"{len(self.network_config.security_rules)}개 NSG 규칙"
        )

        return self.resources, self.network_config

    def _normalize_resource_type(self, resource_type: str) -> str:
        """리소스 타입 정규화"""
        for full_type, short_name in self.RESOURCE_TYPES.items():
            if full_type in resource_type:
                return short_name
        return resource_type

    def _extract_properties(self, body: str) -> Dict[str, Any]:
        """리소스 속성 추출 (간단한 키-값 파싱)"""
        properties = {}

        # adminUsername, adminPassword 등
        for line in body.split("\n"):
            line = line.strip()
            if ":" in line and not line.startswith("//"):
                key_value = line.split(":", 1)
                if len(key_value) == 2:
                    key = key_value[0].strip()
                    value = key_value[1].strip().rstrip(",")
                    properties[key] = value

        return properties

    def _extract_nsg_rules(self, body: str):
        """NSG 보안 규칙 추출"""
        # securityRules 배열 찾기
        rules_match = re.search(r"securityRules:\s*\[([\s\S]*?)\]", body)
        if not rules_match:
            return

        rules_text = rules_match.group(1)

        # 각 규칙 파싱
        rule_blocks = re.finditer(r"\{([\s\S]*?)\}(?:\s*,|\s*\])", rules_text)
        for rule_block in rule_blocks:
            rule_text = rule_block.group(1)
            rule = {}

            # 규칙 속성 추출
            for key in [
                "name",
                "priority",
                "direction",
                "access",
                "protocol",
                "sourcePortRange",
                "destinationPortRange",
                "sourceAddressPrefix",
                "destinationAddressPrefix",
            ]:
                pattern = rf"{key}:\s*'?([^'\n,]+)'?"
                match = re.search(pattern, rule_text)
                if match:
                    rule[key] = match.group(1).strip("'")

            if rule:
                self.network_config.security_rules.append(rule)

    def _extract_subnets(self, body: str):
        """서브넷 추출"""
        subnets_match = re.search(r"subnets:\s*\[([\s\S]*?)\]", body)
        if not subnets_match:
            return

        subnets_text = subnets_match.group(1)
        subnet_blocks = re.finditer(r"\{([\s\S]*?)\}", subnets_text)

        for subnet_block in subnet_blocks:
            subnet_text = subnet_block.group(1)
            subnet = {}

            name_match = re.search(r"name:\s*'([^']+)'", subnet_text)
            prefix_match = re.search(r"addressPrefix:\s*'([^']+)'", subnet_text)

            if name_match and prefix_match:
                subnet["name"] = name_match.group(1)
                subnet["prefix"] = prefix_match.group(1)
                self.network_config.subnets.append(subnet)


# ============================================================
# Phase 1: 리소스 매퍼
# ============================================================


class ResourceMapper:
    """Azure 리소스를 Docker 이미지로 매핑"""

    # 리소스 타입별 Docker 이미지 매핑
    RESOURCE_TO_DOCKER = {
        "vm": {
            "image": "ubuntu:22.04",
            "command": "tail -f /dev/null",  # 컨테이너 유지
            "expose": [22, 80, 443, 3389],
        },
        "sql": {
            "image": "mcr.microsoft.com/mssql/server:2022-latest",
            "environment": {
                "ACCEPT_EULA": "Y",
                "MSSQL_SA_PASSWORD": "YourStrong!Passw0rd",  # SQL Server 비밀번호 정책 준수
                "MSSQL_PID": "Developer",
            },
            "expose": [1433],
        },
        "storage": {
            "image": "minio/minio:latest",
            "command": 'server /data --console-address ":9001"',
            "environment": {
                "MINIO_ROOT_USER": "admin",
                "MINIO_ROOT_PASSWORD": "password123",
            },
            "expose": [9000, 9001],
        },
        "webapp": {"image": "nginx:alpine", "expose": [80, 443]},
        "keyvault": {
            "image": "hashicorp/vault:latest",  # vault:latest → hashicorp/vault:latest
            "environment": {
                "VAULT_DEV_ROOT_TOKEN_ID": "root",
                "VAULT_DEV_LISTEN_ADDRESS": "0.0.0.0:8200",
            },
            "expose": [8200],
        },
    }

    def __init__(self, resources: List[BicepResource], network_config: NetworkConfig):
        self.resources = resources
        self.network_config = network_config
        self.service_mapping: Dict[str, Dict] = {}

    def map_to_docker(self) -> Dict[str, Dict]:
        """리소스를 Docker 서비스로 매핑"""
        logger.info("Azure 리소스를 Docker 서비스로 매핑 중")

        # 포트 충돌 방지
        used_host_ports = set()

        for resource in self.resources:
            if resource.type in self.RESOURCE_TO_DOCKER:
                service_name = f"{resource.type}_{resource.name}"
                docker_config = self.RESOURCE_TO_DOCKER[resource.type].copy()

                # NSG 규칙을 포트 매핑으로 변환
                ports = self._get_exposed_ports(resource.type)

                service = {
                    "image": docker_config.get("image"),
                    "container_name": service_name,
                    "networks": ["attack_network"],
                    "restart": "unless-stopped",
                }

                if "command" in docker_config:
                    service["command"] = docker_config["command"]

                if "environment" in docker_config:
                    service["environment"] = docker_config["environment"]

                # 포트 노출 - 충돌 방지
                if ports:
                    port_mappings = []
                    for container_port in ports:
                        host_port = container_port
                        # 이미 사용 중인 포트면 다른 포트 찾기
                        while host_port in used_host_ports:
                            host_port += 1000  # 1000씩 증가 (1433 -> 2433)
                        used_host_ports.add(host_port)
                        port_mappings.append(f"{host_port}:{container_port}")
                    service["ports"] = port_mappings

                self.service_mapping[service_name] = service

        logger.info(f"매핑 완료: {len(self.service_mapping)}개 서비스")
        return self.service_mapping

    def _get_exposed_ports(self, resource_type: str) -> List[int]:
        """NSG 규칙에서 노출된 포트 추출"""
        exposed_ports = set()

        for rule in self.network_config.security_rules:
            if (
                rule.get("direction") == "Inbound"
                and rule.get("access") == "Allow"
                and rule.get("sourceAddressPrefix") == "*"
            ):

                port_range = rule.get("destinationPortRange", "")
                if port_range and port_range != "*":
                    try:
                        port = int(port_range)
                        exposed_ports.add(port)
                    except ValueError:
                        pass

        # 리소스 타입 기본 포트도 추가
        if resource_type in self.RESOURCE_TO_DOCKER:
            default_ports = self.RESOURCE_TO_DOCKER[resource_type].get("expose", [])
            exposed_ports.update(default_ports)

        return sorted(list(exposed_ports))


# ============================================================
# Phase 1: Docker Compose 생성기
# ============================================================


class DockerComposer:
    """Docker Compose 파일 생성"""

    def __init__(self, service_mapping: Dict[str, Dict]):
        self.service_mapping = service_mapping

    def generate_compose_file(self) -> str:
        """docker-compose.yml 생성"""
        logger.info("Docker Compose 파일 생성 중")

        compose = {
            "version": "3.8",
            "services": self.service_mapping,
            "networks": {
                "attack_network": {
                    "driver": "bridge",
                    "ipam": {"config": [{"subnet": "172.20.0.0/16"}]},
                }
            },
        }

        yaml_content = yaml.dump(compose, default_flow_style=False, sort_keys=False)
        logger.info("Docker Compose 파일 생성 완료")
        return yaml_content


# ============================================================
# Phase 1: 로컬 배포자
# ============================================================


class LocalDeployer:
    """Docker Compose 배포 및 관리"""

    def __init__(self):
        try:
            self.docker_client = docker.from_env()
            logger.info("Docker 연결 성공")
        except Exception as e:
            logger.error(f"Docker 연결 실패: {e}")
            raise RuntimeError(
                "Docker가 실행 중이지 않습니다. Docker를 시작한 후 다시 시도하세요."
            )

        self.compose_file_path: Optional[Path] = None
        self.deployment_info: Optional[DeploymentInfo] = None
        self.deployment_failed = False  # 배포 실패 플래그

    def _validate_and_fix_compose_file(self, compose_path: Path) -> bool:
        """
        Docker Compose 파일 검증 및 자동 수정

        Returns:
            bool: 수정 여부
        """
        logger.info("🔍 Docker Compose 파일 검증 및 수정 중...")

        try:
            with open(compose_path, "r") as f:
                compose_data = yaml.safe_load(f)

            fixed = False

            # 1. 포트 충돌 검증 및 수정
            used_ports = set()
            for service_name, service_config in compose_data.get(
                "services", {}
            ).items():
                if "ports" in service_config:
                    new_ports = []
                    for port_mapping in service_config["ports"]:
                        if isinstance(port_mapping, str) and ":" in port_mapping:
                            host_port = int(port_mapping.split(":")[0])
                            container_port = port_mapping.split(":")[1]

                            original_host_port = host_port
                            while host_port in used_ports:
                                host_port += 1000
                                fixed = True

                            if original_host_port != host_port:
                                logger.warning(
                                    f"  ⚠️  포트 충돌 수정: {service_name} {original_host_port} → {host_port}"
                                )

                            used_ports.add(host_port)
                            new_ports.append(f"{host_port}:{container_port}")
                        else:
                            new_ports.append(port_mapping)

                    service_config["ports"] = new_ports

            # 2. 이미지명 검증 및 수정
            image_fixes = {
                "vault:latest": "hashicorp/vault:latest",
                "vault": "hashicorp/vault:latest",
            }

            for service_name, service_config in compose_data.get(
                "services", {}
            ).items():
                if "image" in service_config:
                    original_image = service_config["image"]
                    if original_image in image_fixes:
                        service_config["image"] = image_fixes[original_image]
                        logger.warning(
                            f"  ⚠️  이미지명 수정: {service_name} {original_image} → {service_config['image']}"
                        )
                        fixed = True

            # 3. SQL Server 환경변수 검증 및 수정
            for service_name, service_config in compose_data.get(
                "services", {}
            ).items():
                if "mssql" in service_config.get("image", "").lower():
                    env = service_config.get("environment", {})
                    if isinstance(env, dict):
                        # SA_PASSWORD를 MSSQL_SA_PASSWORD로 변경
                        if "SA_PASSWORD" in env and "MSSQL_SA_PASSWORD" not in env:
                            env["MSSQL_SA_PASSWORD"] = env.pop("SA_PASSWORD")
                            logger.warning(
                                f"  ⚠️  SQL Server 환경변수 수정: {service_name} SA_PASSWORD → MSSQL_SA_PASSWORD"
                            )
                            fixed = True

                        # 비밀번호 강도 검증
                        password = env.get("MSSQL_SA_PASSWORD", "")
                        if (
                            len(password) < 8
                            or not any(c.isupper() for c in password)
                            or not any(c.islower() for c in password)
                            or not any(c.isdigit() for c in password)
                        ):
                            env["MSSQL_SA_PASSWORD"] = "YourStrong!Passw0rd"
                            logger.warning(
                                f"  ⚠️  SQL Server 비밀번호 강화: {service_name}"
                            )
                            fixed = True

            # 수정 사항이 있으면 파일 다시 저장
            if fixed:
                with open(compose_path, "w") as f:
                    yaml.dump(
                        compose_data, f, default_flow_style=False, sort_keys=False
                    )
                logger.info(f"✅ Compose 파일 수정 완료: {compose_path}")
                return True
            else:
                logger.info("✅ 검증 완료: 수정할 사항 없음")
                return False

        except Exception as e:
            logger.error(f"❌ Compose 파일 검증 실패: {e}")
            return False

    def deploy(self, compose_yaml: str) -> DeploymentInfo:
        """Docker Compose로 배포"""
        logger.info("로컬 환경 배포 시작")

        # 임시 파일에 compose 저장
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(compose_yaml)
            self.compose_file_path = Path(f.name)

        logger.info(f"Compose 파일 경로: {self.compose_file_path}")

        # 최대 2회 시도 (초기 시도 + 1회 재시도)
        max_attempts = 2

        for attempt in range(1, max_attempts + 1):
            try:
                # 2회차 시도 전에 파일 검증 및 수정
                if attempt == 2:
                    logger.warning(
                        "⚠️  첫 배포 실패, Compose 파일 검증 후 재시도합니다..."
                    )
                    self._validate_and_fix_compose_file(self.compose_file_path)

                # docker-compose up -d
                logger.info(f"[시도 {attempt}/{max_attempts}] 컨테이너 시작 중...")
                logger.info(
                    "⏱️  이미지 다운로드 및 컨테이너 생성 중 (첫 실행 시 최대 10분 소요)"
                )

                result = subprocess.run(
                    ["docker-compose", "-f", str(self.compose_file_path), "up", "-d"],
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10분 타임아웃 (이미지 다운로드 시간 포함)
                )

                if result.returncode != 0:
                    logger.error(
                        f"❌ 이미지 다운로드 및 컨테이너 생성 실패 (returncode={result.returncode})"
                    )
                    logger.error(f"Stderr: {result.stderr[:1000]}")

                    # 마지막 시도였으면 실패 처리
                    if attempt == max_attempts:
                        logger.error("❌ 모든 배포 시도 실패. 시뮬레이션을 중단합니다.")
                        self.deployment_failed = True
                        return DeploymentInfo(
                            compose_file=str(self.compose_file_path),
                            containers=[],
                            networks=[],
                            volumes=[],
                        )
                    else:
                        # docker-compose up 실패 시 yml 검증 후 재시도
                        logger.warning("⚠️  Docker Compose 파일 검증 및 수정 중...")
                        self._validate_and_fix_compose_file(self.compose_file_path)
                        time.sleep(2)
                        continue

                # 배포 명령 성공!
                logger.info("✅ 이미지 다운로드 및 컨테이너 생성 완료")

                # 컨테이너 상태 반복 확인 (최대 10분)
                logger.info("⏱️  컨테이너 상태 확인 중... (최대 10분 대기)")
                max_wait_seconds = 600  # 10분
                check_interval = 10  # 10초마다 체크
                elapsed = 0
                containers = []

                while elapsed < max_wait_seconds:
                    containers = self._get_running_containers()

                    if containers:
                        logger.info(
                            f"✅ {len(containers)}개 컨테이너 감지됨 (대기 시간: {elapsed}초)"
                        )
                        break

                    # 컨테이너 상태 로그
                    if elapsed % 30 == 0:  # 30초마다 상태 출력
                        ps_result = subprocess.run(
                            [
                                "docker-compose",
                                "-f",
                                str(self.compose_file_path),
                                "ps",
                                "-a",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        logger.info(
                            f"컨테이너 초기화 중... ({elapsed}/{max_wait_seconds}초)"
                        )
                        if elapsed == 0:
                            logger.debug(f"상태:\n{ps_result.stdout[:500]}")

                    time.sleep(check_interval)
                    elapsed += check_interval

                # 10분 초과 시
                if not containers:
                    logger.warning(f"⚠️  10분 동안 컨테이너 시작 확인 안 됨")

                    # 마지막 시도였으면 실패 처리
                    if attempt == max_attempts:
                        logger.error("❌ 컨테이너 시작 실패. 시뮬레이션을 중단합니다.")
                        self.deployment_failed = True
                        return DeploymentInfo(
                            compose_file=str(self.compose_file_path),
                            containers=[],
                            networks=[],
                            volumes=[],
                        )
                    else:
                        # 10분 초과 시 컨테이너 정리부터 재시도
                        logger.info(f"재시도 준비 중... ({attempt + 1}/{max_attempts})")
                        time.sleep(2)
                        continue

                # 성공! 네트워크 정보 수집
                networks = self._get_networks()

                self.deployment_info = DeploymentInfo(
                    compose_file=str(self.compose_file_path),
                    containers=containers,
                    networks=networks if networks else ["attack_network"],
                    volumes=[],
                )

                logger.info(f"✅ 배포 완료: {len(containers)}개 컨테이너 실행 중")
                return self.deployment_info

            except subprocess.TimeoutExpired:
                logger.error("❌ Docker Compose 배포 타임아웃 (10분 초과)")
                if attempt == max_attempts:
                    self.deployment_failed = True
                    return DeploymentInfo(
                        compose_file=str(self.compose_file_path),
                        containers=[],
                        networks=[],
                        volumes=[],
                    )
                else:
                    logger.info(f"타임아웃 후 재시도... ({attempt + 1}/{max_attempts})")
                    time.sleep(2)
                    continue

            except Exception as e:
                logger.error(f"배포 중 예외 발생: {e}", exc_info=True)
                if attempt == max_attempts:
                    self.deployment_failed = True
                    return DeploymentInfo(
                        compose_file=str(self.compose_file_path),
                        containers=[],
                        networks=[],
                        volumes=[],
                    )
                else:
                    logger.info(f"예외 후 재시도... ({attempt + 1}/{max_attempts})")
                    time.sleep(2)
                    continue

        # 여기 도달하면 모든 시도 실패
        logger.error("❌ 모든 배포 시도 실패")
        self.deployment_failed = True
        return DeploymentInfo(
            compose_file=str(self.compose_file_path) if self.compose_file_path else "",
            containers=[],
            networks=[],
            volumes=[],
        )

    def _get_running_containers(self) -> List[Dict[str, str]]:
        """실행 중인 컨테이너 정보 (subprocess 기반)"""
        try:
            # docker-compose ps -q로 컨테이너 ID 목록 가져오기
            result = subprocess.run(
                ["docker-compose", "-f", str(self.compose_file_path), "ps", "-q"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.warning(f"docker-compose ps 실패: {result.stderr}")
                return []

            container_ids = result.stdout.strip().split("\n")
            container_ids = [cid for cid in container_ids if cid]  # 빈 문자열 제거

            if not container_ids:
                return []

            # 각 컨테이너의 상세 정보 가져오기
            containers = []
            for container_id in container_ids:
                try:
                    inspect_result = subprocess.run(
                        ["docker", "inspect", container_id],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )

                    if inspect_result.returncode != 0:
                        continue

                    import json

                    container_data = json.loads(inspect_result.stdout)[0]

                    # 상태가 running인지 확인
                    state = container_data.get("State", {})
                    if state.get("Status") != "running":
                        continue

                    # 네트워크 정보 찾기
                    networks = container_data.get("NetworkSettings", {}).get(
                        "Networks", {}
                    )
                    ip_address = "N/A"
                    for network_name, network_info in networks.items():
                        if "attack_network" in network_name:
                            ip_address = network_info.get("IPAddress", "N/A")
                            break

                    # 이미지 이름
                    image = container_data.get("Config", {}).get("Image", "unknown")

                    containers.append(
                        {
                            "id": container_id[:12],
                            "name": container_data.get("Name", "").lstrip("/"),
                            "image": image,
                            "ip": ip_address,
                            "status": state.get("Status", "unknown"),
                        }
                    )

                except Exception as e:
                    logger.debug(f"컨테이너 {container_id} 정보 수집 실패: {e}")
                    continue

            return containers

        except Exception as e:
            logger.error(f"컨테이너 목록 조회 실패: {e}")
            return []

    def _get_networks(self) -> List[str]:
        """네트워크 목록"""
        networks = []
        for network in self.docker_client.networks.list():
            if "attack" in network.name:
                networks.append(network.name)
        return networks

    def cleanup(self):
        """배포 환경 정리 - 모든 컨테이너 제거"""
        logger.info("🧹 모든 실행 중인 컨테이너 정리 중...")
        try:
            # 실행 중인 모든 컨테이너 중지
            subprocess.run(
                "docker stop $(docker ps -q) 2>/dev/null || true",
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # 모든 컨테이너 제거
            subprocess.run(
                "docker rm $(docker ps -aq) 2>/dev/null || true",
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # compose 파일 관련 리소스 정리
            if self.compose_file_path and self.compose_file_path.exists():
                subprocess.run(
                    ["docker-compose", "-f", str(self.compose_file_path), "down", "-v"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.compose_file_path.unlink()

            logger.info("✅ 정리 완료")
        except Exception as e:
            logger.warning(f"정리 중 오류: {e}")


# ============================================================
# Agent Loop Tool 파라미터 정의 (Pydantic)
# ============================================================

if COPILOT_AVAILABLE:

    class NmapScanParams(BaseModel):
        target: str = Field(
            description="Target IP address or hostname to scan (e.g., '172.18.0.2')"
        )
        port_range: str = Field(
            default="1-1000",
            description="Port range to scan (e.g., '1-1000', '22,80,443')",
        )

    class HydraAttackParams(BaseModel):
        target: str = Field(
            description="Target IP address or hostname with SSH service"
        )
        username: str = Field(
            default="root",
            description="Username to test. Common values: 'root', 'admin', 'ubuntu'",
        )
        password_list: str = Field(
            default="password,123456,admin,root",
            description="Comma-separated password list",
        )

    class SQLMapAttackParams(BaseModel):
        target_url: str = Field(
            description="Target URL with parameter to test (e.g., 'http://172.18.0.2/login?user=test')"
        )
        level: int = Field(
            default=1,
            ge=1,
            le=5,
            description="Test level (1-5). Higher = more thorough but slower",
        )

    class MetasploitExploitParams(BaseModel):
        target: str = Field(description="Target IP address or hostname")
        exploit_module: str = Field(
            default="scanner/portscan/tcp", description="Metasploit module to use"
        )

    class SQLServerAttackParams(BaseModel):
        target: str = Field(
            description="SQL Server target IP address or hostname"
        )
        port: int = Field(
            default=1433,
            description="SQL Server port (default: 1433)"
        )

    class RDPAttackParams(BaseModel):
        target: str = Field(
            description="RDP target IP address or hostname"
        )
        port: int = Field(
            default=3389,
            description="RDP port (default: 3389)"
        )

    class StorageScanParams(BaseModel):
        target: str = Field(
            description="Storage server IP address or hostname"
        )
        port: int = Field(
            default=9000,
            description="Storage HTTP port (MinIO=9000, Azurite=10000, Azure=443)"
        )


