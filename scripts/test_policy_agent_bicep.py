#!/usr/bin/env python3
"""
Policy Agent 수동 테스트: Bicep 파일을 넣어 보안 검토 결과를 확인합니다.

사용법 (works-on-my-machine 또는 agenthon에서):
  # bicep_example에서 랜덤으로 하나 골라 테스트 (테스트용)
  python works-on-my-machine/scripts/test_policy_agent_bicep.py
  python scripts/test_policy_agent_bicep.py

  # 지정한 Bicep 파일로 테스트
  python scripts/test_policy_agent_bicep.py bicep_example/bicep_sample_02_minimal_storage.bicep

파이프라인(Upload → Preprocess → BiCep)에서 나온 Bicep을 이 스크립트로 직접 넣어 Policy Agent만 테스트할 수 있습니다.
"""

import asyncio
import random
import sys
from pathlib import Path

# works-on-my-machine만 path에 추가 (이 폴더 안 코드만 사용)
_SCRIPT_DIR = Path(__file__).resolve().parent
_WOM = _SCRIPT_DIR.parent
_REPO = _WOM.parent
if str(_WOM) not in sys.path:
    sys.path.insert(0, str(_WOM))

try:
    import data.env  # noqa: F401  # .env 로드 (프로젝트 루트 + cwd)
except ImportError:
    pass

import os


def _check_env() -> bool:
    """Azure AI Foundry / OpenAI용 .env 적용 여부 확인. API 키 값은 출력하지 않음."""
    deployment = (
        os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
        or os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
        or os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT")
    )
    required = [
        ("AZURE_OPENAI_ENDPOINT", "Azure OpenAI 엔드포인트 (AI Foundry 리소스)"),
        ("AZURE_OPENAI_API_KEY", "API 키"),
    ]
    ok = True
    for key, desc in required:
        val = os.environ.get(key)
        if not (val and str(val).strip()):
            print(f"  [X] {key}: 비어 있음 — {desc}")
            ok = False
        else:
            print(f"  [OK] {key}: 설정됨 — {desc}")
    if deployment:
        print(f"  [OK] 배포 이름: {deployment} (AZURE_OPENAI_DEPLOYMENT_NAME 등)")
    else:
        print("  [X] 배포 이름 비어 있음 — AZURE_OPENAI_DEPLOYMENT_NAME 또는 AZURE_OPENAI_CHAT_DEPLOYMENT_NAME 설정")
        ok = False
    aaf = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    print(f"  [{'OK' if aaf else '-'}] AZURE_AI_PROJECT_ENDPOINT: {'설정됨 (AI Foundry)' if aaf else '미설정 (선택)'}")
    return ok


def _pick_random_bicep_from_example() -> Path | None:
    """bicep_example/ 아래 .bicep 파일 중 하나를 랜덤으로 반환 (works 우선)."""
    examples_dir = _WOM / "bicep_example"
    if not examples_dir.is_dir():
        examples_dir = _REPO / "bicep_example"
    if not examples_dir.is_dir():
        return None
    files = list(examples_dir.glob("*.bicep"))
    return random.choice(files) if files else None


async def main() -> None:
    print("--- .env 적용 여부 (Azure AI Foundry / OpenAI) ---")
    if not _check_env():
        print("\n.env에 필수 변수가 없습니다. 프로젝트 루트의 .env 파일을 확인하세요.")
        sys.exit(1)
    print()

    if len(sys.argv) >= 2:
        bicep_path = Path(sys.argv[1])
    else:
        # 인자 없음: bicep_example에서 랜덤 선택 (테스트용)
        bicep_path = _pick_random_bicep_from_example()
        if bicep_path is None:
            print("bicep_example/ 폴더에 .bicep 파일이 없거나 경로를 찾을 수 없습니다.")
            print("사용법: python test_policy_agent_bicep.py [bicep 파일 경로]")
            print("예:     python test_policy_agent_bicep.py bicep_example/bicep_sample_02_minimal_storage.bicep")
            sys.exit(1)
        print(f"[테스트] bicep_example에서 랜덤 선택: {bicep_path.name}\n")

    # bicep_path가 상대 경로면 여러 기준으로 찾기 (works 우선)
    if not bicep_path.is_absolute():
        for base in (_WOM, _REPO, Path.cwd()):
            candidate = base / bicep_path
            if candidate.exists():
                bicep_path = candidate
                break
    if not bicep_path.exists():
        print(f"파일을 찾을 수 없습니다: {bicep_path}")
        sys.exit(2)

    bicep_code = bicep_path.read_text(encoding="utf-8")
    print(f"[입력] {bicep_path} ({len(bicep_code)} chars)\n")

    from agents.policy_agent import review_bicep_only

    result = await review_bicep_only(bicep_code)

    is_error = result.get("status") == "error" or result.get("error")
    if is_error:
        print("--- 오류 ---")
        print(result.get("error", result.get("result_message", result.get("summary", "알 수 없는 오류"))))
        print("status:", result.get("status"))
        if result.get("error"):
            print("(LLM 호출 실패, RAG 실패 등 기능 오류로 검토를 수행하지 못했습니다.)")
        sys.exit(3)
    print("--- Policy Agent 검토 결과 ---")
    print(result.get("result_message", result.get("summary", "")))
    print("status:", result.get("status"))
    print("위반:", len(result.get("violations", [])))
    print("권장:", len(result.get("recommendations", [])))

    # 출력 필드: rule, severity, message, recommendation (API/UI와 동일)
    if result.get("violations"):
        print("\n[위반 사항] (rule, severity=manifest 기준)")
        for v in result["violations"]:
            rule = v.get("rule", "")
            sev = v.get("severity", "")
            msg = (v.get("message") or "")[:80]
            print(f"  - {rule} | severity={sev} | {msg}...")
    if result.get("recommendations"):
        print("\n[권장 사항] (rule, severity=manifest 기준)")
        for r in result["recommendations"][:5]:
            rule = r.get("rule", "")
            sev = r.get("severity", "")
            msg = (r.get("message") or "")[:80]
            print(f"  - {rule} | severity={sev} | {msg}...")
        if len(result["recommendations"]) > 5:
            print(f"  ... 외 {len(result['recommendations']) - 5}건")

    # severity 검증: manifest(active)의 severity와 결과가 일치하는지
    manifest_path = _REPO / "data" / "manifest.json"
    if manifest_path.exists():
        import json
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        expected_sev = {}
        for doc in manifest.get("documents") or []:
            if (doc.get("metadata") or {}).get("status") == "active":
                expected_sev[doc["id"]] = (doc.get("metadata") or {}).get("severity", "medium")
        all_items = (result.get("violations") or []) + (result.get("recommendations") or [])
        mismatches = []
        for item in all_items:
            rule = item.get("rule", "")
            out_sev = (item.get("severity") or "").lower()
            exp = expected_sev.get(rule, "").lower()
            if exp and out_sev != exp:
                mismatches.append((rule, out_sev, exp))
        if mismatches:
            print("\n[경고] severity 불일치 (출력 vs manifest):")
            for rule, out_sev, exp in mismatches:
                print(f"  {rule}: 출력={out_sev}, manifest={exp}")
        else:
            print("\n[OK] 모든 항목의 severity가 manifest와 일치합니다.")
    else:
        print("\n[skip] data/manifest.json 없음 — severity 검증 생략")


if __name__ == "__main__":
    asyncio.run(main())
