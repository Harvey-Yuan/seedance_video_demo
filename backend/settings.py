import os

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), "..", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_path: str = Field(
        default_factory=lambda: os.path.join(
            os.path.dirname(__file__), "data", "runs.sqlite3"
        )
    )
    # --- Butterbase AI gateway (OpenAI-compatible chat, path /v1/{app_id}/chat/completions) ---
    butterbase_api_url: str = Field(
        default="https://api.butterbase.ai",
        validation_alias="BUTTERBASE_API_URL",
    )
    butterbase_app_id: str | None = Field(
        default=None,
        validation_alias="BUTTERBASE_APP_ID",
    )
    butterbase_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "BUTTERBASE_API_KEY", "BUTTERBASE_SERVICE_KEY"
        ),
        description="Platform service key (bb_sk_...); see Butterbase console",
    )
    butterbase_json_response: bool = Field(
        default=False,
        validation_alias="BUTTERBASE_JSON_RESPONSE",
        description="If True, send response_format=json_object on chat requests (keep False if gateway rejects it)",
    )
    # --- Direct OpenAI or other OpenAI-compatible gateway ---
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="OPENAI_BASE_URL",
    )
    layer1_model: str = Field(default="gpt-4o-mini", validation_alias="LAYER1_MODEL")
    layer2_model: str = Field(default="gpt-4o-mini", validation_alias="LAYER2_MODEL")
    image_model: str | None = Field(
        default=None,
        validation_alias="IMAGE_MODEL",
        description="If set, try images/generations with this model id (provider-specific).",
    )
    seedance_api_key: str | None = Field(
        default=None,
        validation_alias="SEEDANCE_2_0_API",
        description="BytePlus Seedance / Ark API key (same env name as seedance_video)",
    )
    seedance_duration: int = Field(default=5, ge=1, le=60)
    seedance_ratio: str = Field(default="16:9")
    seedance_resolution: str | None = Field(
        default=None,
        description="Optional: 720p, 1080p, 2k",
    )
    seedance_video_model: str = Field(
        default="dreamina-seedance-2-0-260128",
        validation_alias="SEEDANCE_VIDEO_MODEL",
    )
    makeup_image_model: str | None = Field(
        default="seedream-4-0-250828",
        validation_alias="MAKEUP_IMAGE_MODEL",
        description=(
            "ModelArk image model id (makeup). Official Seedream 4.0 single-image: "
            "https://docs.byteplus.com/en/docs/ModelArk/1824718 (Model Version: seedream-4-0-250828). "
            "Override if your console uses an inference endpoint ep-…."
        ),
    )
    ark_image_base_url: str | None = Field(
        default=None,
        validation_alias="ARK_IMAGE_BASE_URL",
        description="Image API base URL; defaults to same region as Seedance (ark .../api/v3)",
    )
    ffmpeg_path: str = Field(default="ffmpeg", validation_alias="FFMPEG_PATH")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="CORS_ORIGINS",
    )
    product_note: str = Field(
        default=(
            "~1 min writer output; makeup = photoreal reference stills; director = multi-segment "
            "Seedance params; final video = segments + ffmpeg merge; upload to Butterbase Storage "
            "(download URLs expire; object_id in meta)."
        ),
        validation_alias=AliasChoices("PRODUCT_NOTE", "PRODUCT_NOTE_ZH"),
    )

    @field_validator(
        "butterbase_app_id",
        "butterbase_api_key",
        "openai_api_key",
        "seedance_api_key",
        "makeup_image_model",
        "ark_image_base_url",
        mode="before",
    )
    @classmethod
    def _strip_empty_strings(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return v

    @model_validator(mode="after")
    def _default_models_for_butterbase(self):
        """When using Butterbase without explicit models, apply gateway-style model prefixes."""
        if self.butterbase_app_id and self.butterbase_api_key:
            if self.layer1_model == "gpt-4o-mini":
                object.__setattr__(self, "layer1_model", "openai/gpt-4o-mini")
            if self.layer2_model == "gpt-4o-mini":
                object.__setattr__(self, "layer2_model", "openai/gpt-4o-mini")
        return self

    def uses_butterbase_llm(self) -> bool:
        return bool(self.butterbase_app_id and self.butterbase_api_key)

    def resolve_llm(self) -> tuple[str, str, bool]:
        """(chat_completions URL prefix without trailing path, api_key, whether to add response_format=json_object)."""
        if self.uses_butterbase_llm():
            base = f"{self.butterbase_api_url.rstrip('/')}/v1/{self.butterbase_app_id}"
            return base, self.butterbase_api_key, self.butterbase_json_response
        if self.openai_api_key:
            return self.openai_base_url.rstrip("/"), self.openai_api_key, True
        raise RuntimeError(
            "LLM not configured: set BUTTERBASE_APP_ID and BUTTERBASE_API_KEY (Butterbase AI gateway) "
            "in .env, or set OPENAI_API_KEY (optional OPENAI_BASE_URL for other OpenAI-compatible APIs)."
        )


def get_settings() -> Settings:
    """Reload env and .env on each call (handy in dev without process restart)."""
    return Settings()
