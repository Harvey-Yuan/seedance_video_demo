"""HTTP API 请求/响应模型（供 OpenAPI 与路由复用）。"""

from pydantic import BaseModel, Field


class CreateRunBody(BaseModel):
    drama: str = Field(min_length=1, max_length=32000)


class CreateRunResponse(BaseModel):
    id: str
    status: str
