"""
Policy Agent: 설계(Bicep) 보안 검토

입력: Bicep 코드만 받음. (이미지→Bicep 변환은 파이프라인 Upload → Preprocess → BiCep 단계에서 수행하고,
그 출력을 본 에이전트의 입력으로 연결한다.)
처리: 사용자 Bicep 기준으로 CAT-006(필수) + 관련 카테고리 RAG 검색 → 사내 정책·참조 Bicep과 비교.
결과: 정책 검증완료, 위반 N개, 권장 M개 등 검토 결과 반환.

LLM: Azure OpenAI (AsyncAzureOpenAI). env: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT_NAME 또는 AZURE_OPENAI_CHAT_DEPLOYMENT, AZURE_OPENAI_API_KEY

---
반환 형식 (review_bicep_only / handle_design_review 공통):

{
  "status": "critical" | "warning" | "normal" | "error",   # 위반 있음=critical, 권장만=warning, 둘 다 없음=normal
  "result_message": "정책 검증완료. 위반 N개, 권장 M개.",
  "total_checks": int,
  "violations": [
    { "rule": "NET-001", "severity": "high", "message": "...", "recommendation": "..." }
  ],
  "recommendations": [
    { "rule": "STG-001", "severity": "medium", "message": "...", "recommendation": "..." }
  ],
  "summary": "한 줄 요약 (한국어)",
  "policy_citations": ["..."]   # 내부용, UI에는 미전달
}
# 오류 시 추가: "error": "오류 메시지"
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# works-on-my-machine 폴더를 기준으로 data 패키지 로드 (parent = agents, parent.parent = works-on-my-machine)
_WORKS_ROOT = Path(__file__).resolve().parent.parent
if str(_WORKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKS_ROOT))

# .env 로드 (works-on-my-machine/.env 또는 루트 .env, data.rag 등에서 API 키 사용)
try:
    import data.env  # noqa: F401
except ImportError:
    pass

# ---------------------------------------------------------------------------
# LLM: Azure OpenAI (AsyncAzureOpenAI 직접 사용)
# ---------------------------------------------------------------------------

async def _call_llm_json(system: str, user: str, model: str | None = None) -> dict | None:
    """Azure OpenAI chat completion 호출 후 응답 텍스트에서 JSON 파싱해 반환."""
    from openai import AsyncAzureOpenAI

    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    deployment_name = (
        os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
        or os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
        or os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT")
    )
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    if not (endpoint and deployment_name and api_key):
        return None

    client = AsyncAzureOpenAI(
        api_key=api_key,
        api_version=api_version,
        azure_endpoint=endpoint.rstrip("/"),
    )
    try:
        resp = await client.chat.completions.create(
            model=model or deployment_name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
    except Exception as e:
        raise RuntimeError(f"LLM 호출 실패: {e!s}") from e
    text = (resp.choices[0].message.content or "").strip()
    for raw in (text, text.replace("```json", "").replace("```", "").strip()):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue
    return None


# ---------------------------------------------------------------------------
# 데이터 경로 (works-on-my-machine/data)
# ---------------------------------------------------------------------------

def _get_data_dir() -> Path:
    return _WORKS_ROOT / "data"


def _load_policy_rules_from_manifest() -> tuple[set[str], dict[str, str]]:
    """
    data/manifest.json에서 허용 rule_id 목록과 rule_id별 severity 로드.
    허용 = status가 active인 문서만. severity는 metadata.severity (없으면 medium).
    반환: (allowed_rule_ids, rule_id -> severity)
    """
    data_dir = _get_data_dir()
    path = data_dir / "manifest.json"
    allowed: set[str] = set()
    severity_by_rule: dict[str, str] = {}
    if not path.exists():
        return allowed, severity_by_rule
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for doc in data.get("documents") or []:
            rid = doc.get("id")
            if not rid:
                continue
            meta = doc.get("metadata") or {}
            if meta.get("status") != "active":
                continue
            allowed.add(rid)
            sev = (meta.get("severity") or "medium").lower()
            if sev not in ("high", "medium", "low"):
                sev = "medium"
            severity_by_rule[rid] = sev
    except Exception:
        pass
    return allowed, severity_by_rule


# ---------------------------------------------------------------------------
# 보안성 검토 (설계 Bicep vs 참조 Bicep + 정책 RAG)
# ---------------------------------------------------------------------------
# 1) Bicep 전체를 AI가 보고 CAT-001~005 중 관련 카테고리 선별 (1~5개)
# 2) CAT-006(필수) + 선별된 카테고리에서만 RAG로 청크 검색 후 검토


def _load_categories_from_data() -> list[dict]:
    """data/categories.json에서 카테고리 로드. 없으면 schema fallback."""
    data_dir = _get_data_dir()
    path = data_dir / "categories.json"
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    try:
        from data.schema import CATEGORIES
        return list(CATEGORIES)
    except Exception:
        return []


# CAT-001~005만 (AI가 이 중에서 선택). CAT-006은 항상 포함하므로 제외.
_CAT_001_TO_005_IDS = ["CAT-001", "CAT-002", "CAT-003", "CAT-004", "CAT-005"]


async def _select_categories_by_ai(bicep: str) -> list[str]:
    """
    Bicep 코드 전체를 보고, CAT-001~005 중 이 설계와 관련된 카테고리 ID 목록을 AI가 선별.
    한 개~다섯 개까지 반환. 실패 시 빈 리스트 (호출측에서 CAT-001~005 전부로 폴백 가능).
    """
    categories = _load_categories_from_data()
    # CAT-001~005만 사용 (이름·설명을 LLM에 전달)
    options = []
    for c in categories:
        cid = c.get("category_id") or ""
        if cid not in _CAT_001_TO_005_IDS:
            continue
        name = c.get("category_name") or ""
        desc = c.get("description") or ""
        options.append(f"- {cid}: {name}. {desc}")
    if not options:
        return []

    options_text = "\n".join(options)
    system = """당신은 Azure Bicep 인프라 설계를 보고, 이 설계와 관련 있는 보안 정책 카테고리를 골라줍니다.
아래 5개 카테고리(CAT-001~CAT-005) 중에서, 주어진 Bicep 설계에 적용할 때 의미 있는 정책이 있을 수 있는 카테고리만 선택하세요.
1개일 수도 있고 2개, 3개, 5개 전부일 수도 있습니다. 관련 없는 카테고리는 넣지 마세요.

답변은 반드시 JSON 한 줄만: { "category_ids": ["CAT-002", "CAT-003"] }
category_ids는 반드시 CAT-001, CAT-002, CAT-003, CAT-004, CAT-005 중에서만 구성."""

    user = f"""카테고리 목록:

{options_text}

---

Bicep 코드:

```bicep
{(bicep or "")[:12000]}
```

위 Bicep 설계와 관련 있는 카테고리 ID만 골라서 category_ids 배열로 출력하세요. JSON만."""

    out = await _call_llm_json(system, user)
    if not out or not isinstance(out.get("category_ids"), list):
        return []
    # 유효한 CAT-001~005만
    valid = [x for x in out["category_ids"] if isinstance(x, str) and x in _CAT_001_TO_005_IDS]
    return list(dict.fromkeys(valid))  # 순서 유지, 중복 제거


def _load_reference_bicep() -> list[dict]:
    """data/bicep_reference/ manifest 및 .bicep 파일 로드. [{ "path", "content", "policy_categories" }, ...]"""
    data_dir = _get_data_dir()
    ref_dir = data_dir / "bicep_reference"
    manifest_path = ref_dir / "manifest.json"
    out = []
    if not ref_dir.exists():
        return out
    entries = []
    if manifest_path.exists():
        try:
            with open(manifest_path, encoding="utf-8") as f:
                data = json.load(f)
            entries = data.get("templates") or data.get("files") or []
        except Exception:
            entries = []
    # manifest 없으면 ref_dir 내 .bicep 전부
    if not entries:
        for p in ref_dir.glob("*.bicep"):
            entries.append({"path": p.name, "content_path": str(p), "policy_categories": []})
    for e in entries:
        content_path = e.get("content_path") or e.get("path")
        if not content_path:
            continue
        full = ref_dir / content_path if not Path(content_path).is_absolute() else Path(content_path)
        if not full.exists():
            full = ref_dir / Path(content_path).name
        if full.exists() and full.suffix == ".bicep":
            try:
                content = full.read_text(encoding="utf-8")
            except Exception:
                content = ""
            out.append({
                "path": full.name,
                "content": content,
                "policy_categories": e.get("policy_categories") or [],
            })
    return out


async def handle_design_review(
    user_bicep: str,
    user_message: str = "",
) -> dict:
    """
    사용자 Bicep 설계를 참조 Bicep + 정책 RAG와 비교해 위반·권장 사항 보고.
    반환: { "status", "violations", "recommendations", "summary", "policy_citations" }
    """
    from data.rag import search

    def _err(reason: str) -> dict:
        return {
            "status": "error",
            "error": reason,
            "result_message": reason,
            "total_checks": 0,
            "violations": [],
            "recommendations": [],
            "summary": reason,
            "policy_citations": [],
            "source_documents": [],
        }

    # 0) 허용 rule_id 목록 및 severity (data/manifest.json, status=active + metadata.severity)
    allowed_rule_ids, severity_by_rule = _load_policy_rules_from_manifest()

    # 1) 참조 Bicep 로드
    ref_templates = _load_reference_bicep()

    ref_block = ""
    if ref_templates:
        ref_block = "\n\n--- 참조(정책 준수) Bicep 예시 ---\n\n" + "\n\n---\n\n".join(
            f"파일: {t['path']}\n{t['content'][:8000]}" for t in ref_templates
        )
    else:
        ref_block = "(참조 Bicep이 없습니다. data/bicep_reference/ 에 정책 준수 예시를 넣으면 더 정확한 검토가 가능합니다.)"

    # 2) Bicep 전체를 AI가 보고 CAT-001~005 중 관련 카테고리 선별 → CAT-006(필수) + 선별 결과
    try:
        selected = await _select_categories_by_ai(user_bicep)
    except Exception as e:
        return _err(f"카테고리 선별(LLM) 실패: {e!s}")
    if not selected:
        selected = list(_CAT_001_TO_005_IDS)  # AI 실패 시 5개 전부
    categories_to_use = ["CAT-006"] + selected

    policy_query = (
        "개발 설계 보안성 검토, 설계도 검토 기준, Bicep 인프라 설계 정책, "
        "데이터 스토리지 보안, API 호출 보안, 서버 접근 통제, 네트워크 보안 그룹, "
        "TLS 암호화, HTTPS 전용, 방화벽 규칙, NSG sourceAddressPrefix, Key Vault 네트워크 제한"
    )
    policy_chunks = ""
    source_documents: list[str] = []
    try:
        # 카테고리별로 RAG 검색 후 병합 (CAT-006은 더 많이, 나머지는 보조)
        merged: list[dict] = []
        seen_ids: set[str] = set()
        for cat_id in categories_to_use:
            k_per_cat = 6 if cat_id == "CAT-006" else 3
            # 현재 유효한 정책만 참고 (deprecated 제외)
            results = search(
                policy_query,
                k=k_per_cat,
                index=None,
                metadata_filter={"collection": cat_id, "status": "active"},
            )
            for r in results:
                uid = r.get("id") or r.get("path") or ""
                if uid and uid not in seen_ids:
                    seen_ids.add(uid)
                    merged.append(r)
        # 유사도 순 정렬 후 상위만 사용
        merged.sort(key=lambda x: x.get("score", 0), reverse=True)
        if merged:
            policy_chunks = "\n\n".join(
                f"[정책 출처: {r.get('path', r.get('id'))}]\n{r.get('content', '')}" for r in merged[:15]
            )
            # RAG 참조 문서 목록 (UI 출처 표시용)
            source_documents = list(
                dict.fromkeys(
                    (r.get("path") or r.get("id") or "").strip()
                    for r in merged[:15]
                    if (r.get("path") or r.get("id"))
                )
            )
    except Exception as e:
        return _err(f"정책 RAG 검색 실패: {e}")

    # 3) LLM으로 사용자 Bicep 검토: 위반/권장 (허용 rule_id만 사용, severity는 정책 데이터 기준)
    allowed_list = ", ".join(sorted(allowed_rule_ids)) if allowed_rule_ids else "(없음 - manifest.json에서 status=active 문서 확인)"
    rule_severity_note = "각 rule_id별 severity는 manifest에 정의되어 있으며, 출력 시 해당 값을 사용하세요." if severity_by_rule else "severity는 high/medium/low 중 판단하여 소문자로 출력하세요."

    system_review = f"""당신은 회사 보안 정책에 따른 인프라 설계 검토자입니다.
주어진 사용자 Bicep 코드를 아래 참조 Bicep(정책 준수 예시) 및 정책 문서 내용과 비교하여:
1. 정책 위반 사항(violations): 회사 정책 또는 참조 설계와 명백히 어긋나는 설정
2. 권장 사항(recommendations): 강화하면 좋은 항목

**필수:** rule 필드에는 반드시 아래 허용 목록에 있는 rule_id만 사용하세요. 목록에 없는 rule_id를 출력하면 무시됩니다.
허용 rule_id 목록: {allowed_list}
{rule_severity_note}

각 항목: rule(위 목록에서만 선택), severity(high/medium/low 소문자), message(설명, 한국어), recommendation(조치 방법, 한국어).
한국어로 작성하세요."""

    user_review = f"""사용자 설계 Bicep:

```bicep
{user_bicep[:15000]}
```

{ref_block}

---

관련 정책 문서 발췌:

{policy_chunks[:6000] if policy_chunks else "정책 문서 검색 결과 없음."}

---

위 사용자 Bicep을 참조 Bicep 및 정책에 따라 검토하여, violations와 recommendations를 JSON으로만 출력하세요.
**rule은 반드시 허용 목록에 있는 rule_id만 사용:** {allowed_list}

출력 형식(필드 이름 정확히):
{{
  "violations": [ {{ "rule": "DESIGN-REVIEW-001-NSG-NETWORK", "severity": "high", "message": "한국어 설명", "recommendation": "한국어 조치 방법" }} ],
  "recommendations": [ {{ "rule": "DESIGN-REVIEW-002-STORAGE-WEBAPP", "severity": "high", "message": "한국어 설명", "recommendation": "한국어 조치 방법" }} ],
  "summary": "한 줄 요약 (한국어)"
}}
"""

    try:
        result = await _call_llm_json(system_review, user_review)
    except Exception as e:
        return _err(f"검토 LLM 실패: {e!s}")
    if not result:
        err_msg = "검토 실패(LLM 오류). API 키 및 네트워크를 확인해 주세요."
        return {
            "status": "error",
            "error": err_msg,
            "result_message": err_msg,
            "total_checks": 0,
            "violations": [],
            "recommendations": [],
            "summary": err_msg,
            "policy_citations": [],
            "source_documents": [],
        }

    raw_violations = result.get("violations") or []
    raw_recommendations = result.get("recommendations") or []
    summary = result.get("summary") or "검토 완료"

    # 허용 rule_id만 유지 (manifest.json의 status=active 문서만 결과로 사용)
    def _rule_id(item: dict) -> str:
        return (item.get("rule_id") or item.get("rule") or "").strip()

    if allowed_rule_ids:
        raw_violations = [v for v in raw_violations if _rule_id(v) in allowed_rule_ids]
        raw_recommendations = [r for r in raw_recommendations if _rule_id(r) in allowed_rule_ids]

    # UI 형식에 맞춤: { rule, severity, message, recommendation }; severity는 manifest 기준
    def _to_ui_item(item: dict) -> dict:
        rule = _rule_id(item) or "-"
        sev = severity_by_rule.get(rule) or (item.get("severity") or "medium")
        return {
            "rule": rule,
            "severity": str(sev).lower() if str(sev).lower() in ("high", "medium", "low") else "medium",
            "message": item.get("message") or "",
            "recommendation": item.get("recommendation") or "",
        }

    violations = [_to_ui_item(v) for v in raw_violations]
    recommendations = [_to_ui_item(r) for r in raw_recommendations]

    # status: critical(위반 1개 이상) / warning(위반 0, 권장 있음) / normal(위반·권장 둘 다 0)
    if violations:
        status = "critical"
    elif recommendations:
        status = "warning"
    else:
        status = "normal"

    policy_citations = []
    for v in raw_violations + raw_recommendations:
        ref = v.get("policy_ref") or v.get("recommendation")
        if ref and ref not in policy_citations:
            policy_citations.append(ref)

    # 사용자에게 보여줄 결과 문구: 정책 검증완료, 위반 N개, 권장 M개
    n_v = len(violations)
    n_r = len(recommendations)
    if n_v == 0 and n_r == 0:
        result_message = "정책 검증완료. 위반 없음, 권장 사항 없음."
    elif n_v == 0:
        result_message = f"정책 검증완료. 위반 없음, 권장 {n_r}개."
    else:
        result_message = f"정책 검증완료. 위반 {n_v}개, 권장 {n_r}개."

    return {
        "status": status,
        "result_message": result_message,
        "total_checks": len(violations) + len(recommendations),
        "violations": violations,
        "recommendations": recommendations,
        "summary": summary,
        "policy_citations": policy_citations[:20],
        "source_documents": source_documents,
    }


# ---------------------------------------------------------------------------
# 진입점: Bicep 입력만 받아 보안 검토 (이미지→Bicep은 파이프라인에서 수행)
# ---------------------------------------------------------------------------

async def run(
    user_message: str = "",
    bicep_text: str | None = None,
) -> dict:
    """
    Bicep 코드를 받아 사내 정책 기준 보안 검토 후 결과 반환.

    이미지→Bicep 변환은 Policy Agent 앞단 파이프라인(Upload → Preprocess → BiCep)에서 수행하고,
    그 BiCep 출력을 여기 bicep_text 로 넣어 호출한다.
    반환: { "result_message", "status", ... } — status: "critical"|"warning"|"normal"|"error"
    """
    has_bicep = bool(bicep_text and bicep_text.strip())
    if not has_bicep:
        return {
            "error": "설계 검토를 하려면 Bicep 코드를 입력해 주세요. (파이프라인에서 이미지→BiCep 변환 후 여기로 전달)",
            "status": "error",
            "result_message": "Bicep 없음",
            "total_checks": 0,
            "violations": [],
            "recommendations": [],
            "summary": "Bicep 없음",
            "policy_citations": [],
            "source_documents": [],
        }

    review = await handle_design_review(bicep_text.strip(), user_message or "")
    return review


# ---------------------------------------------------------------------------
# analyze API 호환: Bicep만 넘겼을 때 기존 mock_policy_agent 대체
# ---------------------------------------------------------------------------

async def review_bicep_only(bicep_code: str) -> dict:
    """
    Bicep 코드만으로 보안성 검토 (기존 mock_policy_agent 대체용).
    반환 형식: { "result_message", "status", ... } — status: "critical"|"warning"|"normal"|"error"
    """
    return await handle_design_review(bicep_code, "")
