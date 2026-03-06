"""
로컬 환경 구현 및 자동 공격 수행 Agent

Bicep 코드를 분석하여 Docker Compose로 로컬 환경을 구축하고,
실제 보안 공격을 수행하는 독립적인 Agent입니다.

GitHub Copilot SDK를 사용하여 동적 공격 전략을 수립합니다.
"""

import logging
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

import docker
import yaml

# GitHub Copilot SDK (선택적 import - 없으면 fallback)
try:
    from copilot.tools import define_tool
    from copilot import CopilotClient

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
    """
    Bicep 정적 분석 기반의 가상 공격 시나리오.

    실제 공격을 수행하는 것이 아니라, 탐지된 설정 취약점이 어떤 공격으로 이어질 수 있는지 로컬에 재현/배포한 컨테이너들에서 시뮬레이션한 결과다.
    """

    id: str  # 시나리오 식별자. 예: "SCN-001"

    mitre_technique: str
    # MITRE ATT&CK 프레임워크 기법 ID.
    # 탐지된 취약점이 실제 공격자 관점에서 어떤 기법으로 분류되는지 나타낸다.
    # 예: "T1190" (공개 애플리케이션 익스플로잇), "T1552" (자격증명 노출)

    severity: str  # 이 시나리오가 실현될 경우의 위험도. Critical / High / Medium / Low

    container: str  # 공격 대상 리소스 (Docker 컨테이너 이름). 예: "vm_webapp_1"
    objective: str  # 이 시나리오의 공격 목표. 예: "인증 우회를 통한 관리자 권한 획득"

    executed_command: str
    # 이 시나리오를 재현할 수 있는 예시 명령어 (실제 공격이 아닌 로컬에서의 시뮬레이션).
    # 예: "curl -X POST http://webapp:80/login -d 'username=admin&password='"

    command_output: str
    # 위 명령어 실행의 출력 (시뮬레이션된 로그/응답).

    security_finding: str
    # 이 시나리오가 성공할 경우의 관찰 결과와 보안적 의미를 통합한 분석.
    # 예: "인증 없이 관리자 세션 획득 가능 → 권한 상승 및 횡적 이동으로 이어질 수 있음"


@dataclass
class AnalysisResult:
    """Recon 분석 전체 결과 (API 호환)"""

    architecture_summary: dict
    vulnerabilities: List[VulnerabilityItem]
    attack_scenarios: List[AttackScenario]
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
        "Microsoft.Network/privateEndpoints": "privateendpoint",
    }

    def __init__(self):
        self.resources: List[BicepResource] = []
        self.network_config = NetworkConfig()

    def parse(self, bicep_code: str) -> Tuple[List[BicepResource], NetworkConfig]:
        """Bicep 코드 파싱"""

        logger.info("Bicep 코드 파싱 시작")

        # 🔥 반드시 초기화 (누적 방지)
        self.resources = []
        self.network_config = NetworkConfig()

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
                name=resource_name,
                type=normalized_type,
                properties=properties,
            )

            self.resources.append(resource)

            # -----------------------------
            # 네트워크 설정 추출
            # -----------------------------

            if normalized_type == "nsg":
                self._extract_nsg_rules(resource_body)

            elif normalized_type == "vnet":
                self._extract_subnets(resource_body)

            elif normalized_type == "publicip":
                self.network_config.public_ips.append(resource_name)

            elif normalized_type == "sql":
                if "publicNetworkAccess" in properties:
                    self.network_config.security_rules.append(
                        {
                            "type": "sql_public_access",
                            "value": properties.get("publicNetworkAccess"),
                        }
                    )

            elif normalized_type == "storage":
                if "allowBlobPublicAccess" in properties:
                    self.network_config.security_rules.append(
                        {
                            "type": "blob_public",
                            "value": properties.get("allowBlobPublicAccess"),
                        }
                    )

            elif normalized_type == "keyvault":
                if "networkAcls" in resource_body:
                    if "defaultAction: 'Allow'" in resource_body:
                        self.network_config.security_rules.append(
                            {
                                "type": "kv_public_access",
                                "value": "Allow",
                            }
                        )

            elif normalized_type == "webapp":
                if "publicNetworkAccess" in properties:
                    self.network_config.security_rules.append(
                        {
                            "type": "webapp_public_access",
                            "value": properties.get("publicNetworkAccess"),
                        }
                    )

            # private endpoint 처리
            elif normalized_type == "privateendpoint":
                target_match = re.search(
                    r"privateLinkServiceId:\s*([A-Za-z0-9_]+)\.id", resource_body
                )

                if target_match:
                    target_resource = target_match.group(1)

                    self.network_config.security_rules.append(
                        {
                            "type": "private_endpoint",
                            "resource": target_resource,
                        }
                    )

        logger.info(
            f"파싱 완료: {len(self.resources)}개 리소스, "
            f"{len(self.network_config.security_rules)}개 네트워크 규칙"
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

    def map_to_docker(self) -> dict:
        """
        Azure 네트워크 구조를 최대한 재현하는 Docker Compose 생성
        """

        services = {}
        networks = {}
        used_host_ports = set()

        # --------------------------------
        # 1️⃣ Docker network 생성
        # --------------------------------
        private_endpoint_targets = {
            r.get("resource")
            for r in self.network_config.security_rules
            if r.get("type") == "private_endpoint"
        }

        networks = {
            "public_net": {"driver": "bridge"},
            "private_net": {"driver": "bridge"},
        }

        # --------------------------------
        # 2️⃣ 리소스 매핑
        # --------------------------------
        for resource in self.resources:

            resource_type = resource.type.lower()

            if resource_type not in self.RESOURCE_TO_DOCKER:
                continue

            docker_meta = self.RESOURCE_TO_DOCKER[resource_type]
            service_name = resource.name.replace("-", "_")

            service = {
                "image": docker_meta["image"],
                "container_name": service_name,
                "restart": "unless-stopped",
            }

            # 환경변수
            if "environment" in docker_meta:
                service["environment"] = docker_meta["environment"]

            # command
            if "command" in docker_meta:
                service["command"] = docker_meta["command"]

            # --------------------------------
            # 3️⃣ 네트워크(Subnet) 연결
            # --------------------------------
            # if self.network_config.subnets:
            #     # 현재는 단순히 첫 subnet에 연결
            #     service["networks"] = [self.network_config.subnets[0]["name"]]
            # else:
            #     service["networks"] = ["default_net"]
            if resource.name in private_endpoint_targets:
                service["networks"] = ["private_net"]
            else:
                service["networks"] = ["public_net"]

            # --------------------------------
            # 4️⃣ Public 노출 여부 확인
            # --------------------------------
            is_public = self._is_publicly_exposed(resource_type)

            nsg_blocks = self._nsg_blocks_public_access(resource_type)

            # --------------------------------
            # 5️⃣ 포트 매핑
            # --------------------------------
            port_mappings = []

            if is_public and not nsg_blocks:

                exposed_ports = self._get_exposed_ports(resource_type)

                for container_port in exposed_ports:

                    host_port = container_port
                    while host_port in used_host_ports:
                        host_port += 1000

                    used_host_ports.add(host_port)

                    port_mappings.append(f"0.0.0.0:{host_port}:{container_port}")

            if port_mappings:
                service["ports"] = port_mappings

            services[service_name] = service

        return {
            "version": "3.9",
            "services": services,
            "networks": networks,
        }

    def _nsg_blocks_public_access(self, resource_type: str):

        default_ports = self.RESOURCE_TO_DOCKER.get(resource_type, {}).get("expose", [])

        for rule in self.network_config.security_rules:

            if (
                rule.get("direction") == "Inbound"
                and rule.get("access") == "Deny"
                and rule.get("sourceAddressPrefix") in ["*", "0.0.0.0/0"]
            ):

                denied_port = rule.get("destinationPortRange")

                # None 방어
                if not denied_port:
                    continue

                # 모든 포트 차단: 외부 접근 불가
                if denied_port == "*":
                    return True

                # 숫자 포트: 특정 포트 차단
                if denied_port.isdigit():
                    if int(denied_port) in default_ports:
                        return True

            return False

    def _is_publicly_exposed(self, resource_type: str) -> bool:

        sql_public = None
        storage_public = None
        kv_public = None
        webapp_public = None

        for rule in self.network_config.security_rules:

            if rule.get("type") == "sql_public_access":
                sql_public = rule.get("value")

            if rule.get("type") == "blob_public":
                storage_public = rule.get("value")

            if rule.get("type") == "kv_public_access":
                kv_public = rule.get("value")

            if rule.get("type") == "webapp_public_access":
                webapp_public = rule.get("value")

        # SQL
        if resource_type == "sql":
            if sql_public is not None:
                return sql_public == "Enabled"
            return True

        # Storage
        if resource_type == "storage":
            if storage_public is not None:
                return str(storage_public).lower() == "true"
            return False

        # KeyVault
        if resource_type == "keyvault":
            if kv_public is not None:
                return True
            return False

        # WebApp
        if resource_type in ["webapp", "appservice"]:
            if webapp_public is not None:
                return webapp_public == "Enabled"
            return True

        return False

    def _get_exposed_ports(self, resource_type: str) -> List[int]:
        """
        NSG Inbound Allow 규칙 기반 포트 계산
        """

        exposed_ports = set()

        for rule in self.network_config.security_rules:

            if rule.get("direction") != "Inbound":
                continue

            if rule.get("access") != "Allow":
                continue

            port_range = rule.get("destinationPortRange")
            port_ranges = rule.get("destinationPortRanges")

            # -----------------------------
            # Case 1: destinationPortRange
            # -----------------------------
            if port_range:

                if port_range == "*":
                    default_ports = self.RESOURCE_TO_DOCKER.get(resource_type, {}).get(
                        "expose", []
                    )
                    exposed_ports.update(default_ports)

                elif port_range.isdigit():
                    exposed_ports.add(int(port_range))

                elif "-" in port_range:
                    try:
                        start, end = port_range.split("-")
                        start = int(start)
                        end = int(end)

                        for p in range(start, end + 1):
                            exposed_ports.add(p)

                    except Exception:
                        pass

                elif "," in port_range:
                    parts = port_range.split(",")

                    for p in parts:
                        p = p.strip()
                        if p.isdigit():
                            exposed_ports.add(int(p))

            # -----------------------------
            # Case 2: destinationPortRanges
            # -----------------------------
            if port_ranges and isinstance(port_ranges, list):

                for p in port_ranges:
                    if isinstance(p, str) and p.isdigit():
                        exposed_ports.add(int(p))

        # -----------------------------
        # NSG 규칙이 없으면 기본 포트
        # -----------------------------
        if not exposed_ports:

            default_ports = self.RESOURCE_TO_DOCKER.get(resource_type, {}).get(
                "expose", []
            )

            exposed_ports.update(default_ports)

        return sorted(list(exposed_ports))


# ============================================================
# Phase 1: Docker Compose 생성기
# ============================================================


class DockerComposer:
    """Docker Compose 파일 생성"""

    def __init__(self, compose_dict: Dict[str, Any]):
        self.compose_dict = compose_dict

    def generate_compose_file(self) -> str:
        logger.info("Docker Compose 파일 생성 중")

        yaml_content = yaml.dump(
            self.compose_dict,
            default_flow_style=False,
            sort_keys=False,
        )

        logger.info("Docker Compose 파일 생성 완료")
        return yaml_content


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
        target: str = Field(description="SQL Server target IP address or hostname")
        port: int = Field(default=1433, description="SQL Server port (default: 1433)")

    class RDPAttackParams(BaseModel):
        target: str = Field(description="RDP target IP address or hostname")
        port: int = Field(default=3389, description="RDP port (default: 3389)")

    class StorageScanParams(BaseModel):
        target: str = Field(description="Storage server IP address or hostname")
        port: int = Field(
            default=9000,
            description="Storage HTTP port (MinIO=9000, Azurite=10000, Azure=443)",
        )
