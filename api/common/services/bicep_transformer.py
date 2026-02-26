"""
아키텍처 다이어그램/이미지 → Bicep 코드 변환.

Microsoft AI Foundry LLM(비전 가능 모델)을 사용해 이미지를 분석하고 Bicep 코드를 생성합니다.
RAG·검색용 데이터는 사내 정책에 따라 Azure Blob 대신 로컬 벡터 스토어(data/vector_index 등)를 사용합니다.
"""

import asyncio
import logging
import base64
import os
import re
from pathlib import Path

from agent_framework.azure import AzureOpenAIChatClient
from agent_framework import Message, Content


logger = logging.getLogger(__name__)


SAMPLE_BICEP_PATH = Path(__file__).parent.parent / "samples" / "sample_bicep.bicep"


def create_foundry_agent():
    """
    AzureOpenAIChatClient 기반 Vision Agent 생성
    (전역 캐시 사용하지 않음)
    """
    client = AzureOpenAIChatClient(
        endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )

    return client.as_agent(
        name="BicepVisionAgent",
        instructions=BICEP_VISION_SYSTEM,
        temperature=0.2,
        max_tokens=4096,
    )


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
    if re.search(r"\b(resource|param|module|output|var)\b", text):
        return text

    return text


async def _call_foundry_vision(
    image_base64: str, mime_type: str
) -> tuple[str | None, str]:
    """
    Foundry Vision 모델로 이미지 → Bicep 생성
    반환: (결과, 실패원인)
    """

    try:
        agent = create_foundry_agent()

    except Exception as exc:
        logger.exception("AzureOpenAIChatClient 초기화 실패")
        return (
            None,
            f"Agent 초기화 실패: {type(exc).__name__}: {exc}",
        )

    try:
        logger.debug(
            "Foundry Vision Agent 호출 시작 (mime=%s)",
            mime_type,
        )

        # base64 → bytes 변환
        image_bytes = base64.b64decode(image_base64)

        message = Message(
            role="user",
            contents=[
                Content.from_text(text=BICEP_VISION_USER),
                Content.from_data(
                    data=image_bytes,
                    media_type=mime_type,
                ),
            ],
        )

        result = await agent.run(message)

        text = (result.text or "").strip()
        extracted = _extract_bicep_from_response(text) or None

        if extracted:
            logger.debug(
                "Foundry Vision Agent 응답 수신 완료 (%d chars)",
                len(extracted),
            )
            return extracted, ""

        return (
            None,
            f"LLM 응답에서 Bicep 코드 추출 실패 (raw={text[:200]!r})",
        )

    except Exception as exc:
        logger.error("Foundry Vision Agent 호출 중 오류 발생.", exc_info=True)
        return None, f"{type(exc).__name__}: {exc}"


def _is_image_filename(filename: str) -> bool:
    ext = (os.path.splitext(filename or "")[1] or "").lower()
    return ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")


def _mime_for_filename(filename: str) -> str:
    ext = (os.path.splitext(filename or "")[1] or "").lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "image/png")


async def transform_image_to_bicep(file_content: bytes, filename: str) -> str:
    """
    아키텍처 이미지 또는 파일을 Bicep 코드로 변환.

    - AI Foundry가 설정되어 있고, 파일이 이미지이면 Foundry 비전 LLM으로 변환.
    - 그 외(설정 없음, 비이미지, LLM 실패)는 기존처럼 샘플 Bicep을 반환합니다.
    """
    # 이미지이고 Foundry 사용 가능하면 LLM 호출
    logger.info("✅ Image to Bicep transformation started for file: %s", filename)

    if file_content and _is_image_filename(filename):

        mime = _mime_for_filename(filename)
        b64 = base64.standard_b64encode(file_content).decode("ascii")
        out, reason = await _call_foundry_vision(b64, mime)
        if out:
            logger.info(
                "✅ Image to Bicep transformation succeeded for file: %s", filename
            )
            return out
        else:
            logger.warning(
                "⚠️ Image to Bicep transformation failed for file: %s — reason: %s",
                filename,
                reason,
            )

    # PDF/텍스트 등은 현재 지원하지 않음 → 샘플 반환
    await asyncio.sleep(0.3)
    if SAMPLE_BICEP_PATH.exists():
        logger.info("📄 Returning sample Bicep code for file: %s", filename)
        return SAMPLE_BICEP_PATH.read_text(encoding="utf-8")

    logger.info("📄 Returning default Bicep code for file: %s", filename)
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
