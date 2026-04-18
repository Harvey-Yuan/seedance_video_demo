"""HTTP API request/response models (shared by OpenAPI and routes)."""

from pydantic import BaseModel, Field


class CreateRunBody(BaseModel):
    drama: str = Field(min_length=1, max_length=32000)


class CreateRunResponse(BaseModel):
    id: str
    status: str
