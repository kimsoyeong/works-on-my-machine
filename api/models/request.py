from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    """파일 분석 요청 시 추가 옵션 (multipart form과 함께 전송)."""
    pass
