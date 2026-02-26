#!/usr/bin/env python3
"""
Policy Agent 결과를 원본 형태(전체 dict) 그대로 확인하는 스크립트.

사용법 (works-on-my-machine 또는 agenthon 루트에서):
  conda activate agenthonms
  PYTHONPATH=/path/to/agenthon python works-on-my-machine/scripts/show_policy_agent_output.py [bicep파일경로]

  # 예: 샘플 Bicep으로 실행
  PYTHONPATH=. python works-on-my-machine/scripts/show_policy_agent_output.py
  PYTHONPATH=. python works-on-my-machine/scripts/show_policy_agent_output.py bicep_example/bicep_sample_02_minimal_storage.bicep
"""

import asyncio
import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_WOM = _SCRIPT_DIR.parent
_REPO = _WOM.parent
for p in (_REPO, _WOM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    import data.env  # noqa: F401
except ImportError:
    pass


async def main() -> None:
    if len(sys.argv) >= 2:
        bicep_path = Path(sys.argv[1])
    else:
        bicep_path = _REPO / "bicep_example" / "bicep_sample_02_minimal_storage.bicep"
    if not bicep_path.is_absolute():
        for base in (_REPO, _WOM, Path.cwd()):
            c = base / bicep_path
            if c.exists():
                bicep_path = c
                break
    if not bicep_path.exists():
        print(f"파일 없음: {bicep_path}", file=sys.stderr)
        sys.exit(1)

    from agents.policy_agent import review_bicep_only

    bicep_code = bicep_path.read_text(encoding="utf-8")
    print(f"# 입력: {bicep_path.name} ({len(bicep_code)} chars)\n", file=sys.stderr)

    result = await review_bicep_only(bicep_code)

    # policy_citations 등 길 수 있는 필드는 유지하되, UI에 전달되는 형태 확인용
    print("--- Policy Agent 반환값 (원본 형태) ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
