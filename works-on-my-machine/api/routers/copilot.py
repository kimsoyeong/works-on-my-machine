import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from copilot import CopilotClient
    from copilot.types import CopilotClientOptions
    _COPILOT_AVAILABLE = True
except ImportError:
    _COPILOT_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter()


class CopilotRequest(BaseModel):
    prompt: str = Field(default="What is 2 + 2?", description="Copilot에 보낼 프롬프트")
    model: str = Field(default="gpt-4.1", description="사용할 모델")
    timeout: float = Field(default=120.0, description="응답 대기 타임아웃(초)")


class CopilotResponse(BaseModel):
    status: str
    prompt: str
    model: str
    content: str | None = None
    error: str | None = None


@router.post("/copilot", response_model=CopilotResponse)
async def test_copilot(req: CopilotRequest):
    """GitHub Copilot SDK 실행 테스트."""
    if not _COPILOT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="GitHub Copilot SDK가 설치되어 있지 않습니다. (copilot 패키지 없음)",
        )

    client_opts = {}
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        client_opts["github_token"] = github_token
        client_opts["use_logged_in_user"] = False

    client = CopilotClient(client_opts if client_opts else None)  # type: ignore[name-defined]
    try:
        await client.start()
        session = await client.create_session({"model": req.model})
        response = await session.send_and_wait(
            {"prompt": req.prompt},
            timeout=req.timeout,
        )

        content = None
        if response and response.data:
            content = response.data.content

        return CopilotResponse(
            status="success",
            prompt=req.prompt,
            model=req.model,
            content=content,
        )
    except Exception as e:
        logger.exception("Copilot SDK 호출 실패")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.stop()
