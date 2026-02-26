"""
아키텍처 다이어그램/이미지 → Bicep 코드 변환.

Microsoft AI Foundry LLM(비전 가능 모델)을 사용해 이미지를 분석하고 Bicep 코드를 생성합니다.
RAG·검색용 데이터는 사내 정책에 따라 Azure Blob 대신 로컬 벡터 스토어(data/vector_index 등)를 사용합니다.
"""

import asyncio
import base64
import os
import re
from pathlib import Path

SAMPLE_BICEP_PATH = Path(__file__).parent.parent / "samples" / "sample_bicep.bicep"

# AI Foundry 설정 (미설정 시 샘플 Bicep 반환)
AI_FOUNDRY_ENDPOINT = os.environ.get("AI_FOUNDRY_ENDPOINT", "").strip()
AI_FOUNDRY_API_KEY = os.environ.get("AI_FOUNDRY_API_KEY", "").strip()
AI_FOUNDRY_MODEL = os.environ.get("AI_FOUNDRY_MODEL", "gpt-4o")


def _get_foundry_client():
    """Microsoft AI Foundry 또는 Azure OpenAI 호환 엔드포인트용 클라이언트 반환. 없으면 None."""
    # 1) AI Foundry 엔드포인트 + API 키 (OpenAI 호환 엔드포인트 URL)
    if AI_FOUNDRY_ENDPOINT and AI_FOUNDRY_API_KEY:
        try:
            from openai import OpenAI
            base = AI_FOUNDRY_ENDPOINT.rstrip("/")
            return OpenAI(api_key=AI_FOUNDRY_API_KEY, base_url=base), AI_FOUNDRY_MODEL
        except ImportError:
            pass
    # 2) AI Foundry 엔드포인트만 (Entra ID)
    if AI_FOUNDRY_ENDPOINT:
        try:
            from azure.ai.projects import AIProjectClient
            from azure.identity import DefaultAzureCredential
            project = AIProjectClient(
                endpoint=AI_FOUNDRY_ENDPOINT.rstrip("/"),
                credential=DefaultAzureCredential(),
            )
            openai_client = project.get_openai_client(api_version="2024-10-21")
            return openai_client, AI_FOUNDRY_MODEL
        except Exception:
            pass
    return None, None


BICEP_VISION_SYSTEM = """You are an expert Azure infrastructure architect. Your task is to convert architecture diagrams or design images into valid Azure Bicep (infrastructure-as-code).

Rules:
- Output only the Bicep code. No explanation before or after.
- Use valid Bicep syntax: parameters, resources (Microsoft.Network, Microsoft.Storage, Microsoft.Web, Microsoft.Compute, etc.), outputs.
- If the image does not clearly show an architecture, produce a minimal secure Bicep template (e.g. a storage account with HTTPS and TLS 1.2).
- Prefer Korean comments for resource descriptions."""

BICEP_VISION_USER = """Convert the attached architecture diagram or design image into Azure Bicep code. Output only the Bicep code, optionally wrapped in a ```bicep ... ``` block."""


def _extract_bicep_from_response(text: str) -> str:
    """응답 텍스트에서 Bicep 코드 블록 또는 전체 텍스트 추출."""
    if not text or not text.strip():
        return ""
    text = text.strip()
    # ```bicep ... ``` 또는 ``` ... ```
    m = re.search(r"```(?:bicep)?\s*\n([\s\S]*?)```", text)
    if m:
        return m.group(1).strip()
    # 코드 블록 없으면 전체를 Bicep으로 간주 (param/resource/output 포함 시)
    if "resource " in text or "param " in text:
        return text
    return text


async def _call_foundry_vision(image_base64: str, mime_type: str) -> str | None:
    """Foundry 비전 모델로 이미지 → Bicep 생성. 실패 시 None."""
    client, model = _get_foundry_client()
    if client is None:
        return None
    url = f"data:{mime_type};base64,{image_base64}"
    content = [
        {"type": "text", "text": BICEP_VISION_USER},
        {"type": "image_url", "image_url": {"url": url}},
    ]
    try:
        # 동기 호출을 이벤트 루프에서 실행
        def _create():
            return client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": BICEP_VISION_SYSTEM},
                    {"role": "user", "content": content},
                ],
                max_tokens=4096,
                temperature=0.2,
            )
        loop = asyncio.get_event_loop()
        resp = await asyncio.to_thread(_create) if hasattr(asyncio, "to_thread") else await loop.run_in_executor(None, _create)
        text = (resp.choices[0].message.content or "").strip()
        return _extract_bicep_from_response(text) or None
    except Exception:
        return None


def _is_image_filename(filename: str) -> bool:
    ext = (os.path.splitext(filename or "")[1] or "").lower()
    return ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")


def _mime_for_filename(filename: str) -> str:
    ext = (os.path.splitext(filename or "")[1] or "").lower()
    return {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}.get(ext, "image/png")


async def mock_bicep_transform(file_content: bytes, filename: str) -> str:
    """
    아키텍처 이미지 또는 파일을 Bicep 코드로 변환.

    - AI Foundry(AI_FOUNDRY_ENDPOINT 등)가 설정되어 있고, 파일이 이미지이면 Foundry 비전 LLM으로 변환.
    - 그 외(설정 없음, 비이미지, LLM 실패)는 기존처럼 샘플 Bicep을 반환합니다.
    """
    # 이미지이고 Foundry 사용 가능하면 LLM 호출
    if file_content and _is_image_filename(filename):
        mime = _mime_for_filename(filename)
        b64 = base64.standard_b64encode(file_content).decode("ascii")
        out = await _call_foundry_vision(b64, mime)
        if out:
            return out
    # PDF/텍스트 등은 현재 지원하지 않음 → 샘플 반환
    await asyncio.sleep(0.3)
    if SAMPLE_BICEP_PATH.exists():
        return SAMPLE_BICEP_PATH.read_text(encoding="utf-8")
    return _get_default_bicep()


def _get_default_bicep() -> str:
    """샘플 파일이 없을 경우 기본 Bicep 코드 반환."""
    return """\
param location string = resourceGroup().location

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'defaultstorage'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
}
"""