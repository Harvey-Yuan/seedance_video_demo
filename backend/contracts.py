"""Pydantic models aligned with ../contracts/*.schema.json."""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


def _coerce_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


class StoryboardShot(BaseModel):
    shot_id: str
    visual: str
    duration_hint_sec: float = Field(ge=0)
    camera_notes: Optional[str] = None

    model_config = {"extra": "allow"}

    @field_validator("shot_id", "visual", "camera_notes", mode="before")
    @classmethod
    def _strings(cls, v):
        if v is None:
            return v
        return _coerce_str(v)


class Character(BaseModel):
    name: str
    description: str
    voice_notes: Optional[str] = None

    model_config = {"extra": "allow"}

    @field_validator("name", "description", "voice_notes", mode="before")
    @classmethod
    def _strings(cls, v):
        if v is None:
            return v
        return _coerce_str(v)


class DialogueLine(BaseModel):
    speaker: str
    line: str
    shot_ref: Optional[str] = None

    model_config = {"extra": "allow"}

    @field_validator("speaker", "line", "shot_ref", mode="before")
    @classmethod
    def _strings(cls, v):
        if v is None:
            return v
        return _coerce_str(v)


class Layer1Output(BaseModel):
    storyboard: list[StoryboardShot]
    script: str
    characters: list[Character]
    dialogue: list[DialogueLine]

    model_config = {"extra": "allow"}

    @field_validator("script", mode="before")
    @classmethod
    def _script_str(cls, v):
        return _coerce_str(v)


class SeedancePromptSegment(BaseModel):
    segment_id: str
    prompt: str
    image_refs: Optional[list[int]] = None

    model_config = {"extra": "allow"}

    @field_validator("segment_id", "prompt", mode="before")
    @classmethod
    def _strings(cls, v):
        return _coerce_str(v)


class Layer2Output(BaseModel):
    character_image_urls: list[str] = Field(default_factory=list)
    image_prompts_used: Optional[list[str]] = None
    seedance_prompts: list[SeedancePromptSegment]

    model_config = {"extra": "allow"}


class Layer3Output(BaseModel):
    video_url: str
    model: str
    duration_sec: Optional[float] = Field(default=None, ge=0)
    meta: Optional[dict[str, Any]] = None

    model_config = {"extra": "allow"}
