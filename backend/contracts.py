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
    duration_hint_sec: float = Field(ge=0, le=15)
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
    storyboard: list[StoryboardShot] = Field(default_factory=list, max_length=12)
    script: str
    characters: list[Character]
    dialogue: list[DialogueLine]

    model_config = {"extra": "allow"}

    @field_validator("script", mode="before")
    @classmethod
    def _script_str(cls, v):
        return _coerce_str(v)


class MakeupPlanItem(BaseModel):
    character_key: str
    prompt_en: str

    model_config = {"extra": "allow"}

    @field_validator("character_key", "prompt_en", mode="before")
    @classmethod
    def _strings(cls, v):
        return _coerce_str(v)


class MakeupPlanSceneItem(BaseModel):
    """Wide / environment still aligned to a storyboard shot (no character portrait)."""

    shot_id: str
    prompt_en: str

    model_config = {"extra": "allow"}

    @field_validator("shot_id", "prompt_en", mode="before")
    @classmethod
    def _strings(cls, v):
        return _coerce_str(v)


class MakeupPlan(BaseModel):
    items: list[MakeupPlanItem] = Field(default_factory=list, min_length=1, max_length=6)
    scene_items: list[MakeupPlanSceneItem] = Field(
        default_factory=list,
        max_length=6,
        description="1–3 wide establishing shots for Scene Art; may be empty (server falls back).",
    )

    model_config = {"extra": "allow"}


class MakeupOutput(BaseModel):
    character_image_urls: list[str] = Field(default_factory=list)
    makeup_prompts: list[str] = Field(default_factory=list)
    scene_image_urls: list[str] = Field(default_factory=list)
    scene_prompts: list[str] = Field(default_factory=list)
    meta: Optional[dict[str, Any]] = None

    model_config = {"extra": "allow"}


class SeedancePromptSegment(BaseModel):
    segment_id: str
    prompt: str
    segment_goal: Optional[str] = None
    camera_notes: Optional[str] = None
    image_refs: Optional[list[int]] = None
    image_roles: Optional[list[str]] = None
    duration_sec: Optional[int] = Field(default=None, ge=1, le=60)
    ratio: Optional[str] = None
    resolution: Optional[str] = None
    generate_audio: Optional[bool] = None
    camera_fixed: Optional[bool] = None
    seed: Optional[int] = None

    model_config = {"extra": "allow"}

    @field_validator("segment_id", "prompt", "segment_goal", "camera_notes", mode="before")
    @classmethod
    def _strings(cls, v):
        if v is None:
            return v
        return _coerce_str(v)


class Layer2Output(BaseModel):
    """Director JSON: primary field is seedance_prompts; character_image_urls is legacy—new pipeline uses makeup_output."""
    director_notes: Optional[str] = None
    character_image_urls: list[str] = Field(default_factory=list)
    image_prompts_used: Optional[list[str]] = None
    seedance_prompts: list[SeedancePromptSegment] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class Layer3Output(BaseModel):
    video_url: str
    model: str
    duration_sec: Optional[float] = Field(default=None, ge=0)
    meta: Optional[dict[str, Any]] = None

    model_config = {"extra": "allow"}
