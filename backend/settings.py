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
    # --- Butterbase AI gateway（OpenAI 兼容 chat，路径 /v1/{app_id}/chat/completions）---
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
        description="平台 Service Key（bb_sk_...），见 Butterbase 控制台",
    )
    butterbase_json_response: bool = Field(
        default=False,
        validation_alias="BUTTERBASE_JSON_RESPONSE",
        description="为 True 时在 chat 请求里带 response_format=json_object（网关不支持时请保持 False）",
    )
    # --- 直连 OpenAI 或其它 OpenAI 兼容网关 ---
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
        description="BytePlus Seedance / Ark API key（与 seedance_video 环境变量同名）",
    )
    seedance_duration: int = Field(default=5, ge=1, le=60)
    seedance_ratio: str = Field(default="16:9")
    seedance_resolution: str | None = Field(
        default=None,
        description="Optional: 720p, 1080p, 2k",
    )
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="CORS_ORIGINS",
    )
    product_note_zh: str = Field(
        default=(
            "分镜与脚本按约 3 分钟叙事体量生成；Seedance 单次成片时长受模型与参数限制，"
            "当前流水线以「单段短片」为 MVP 输出。"
        ),
        validation_alias="PRODUCT_NOTE_ZH",
    )

    @field_validator(
        "butterbase_app_id",
        "butterbase_api_key",
        "openai_api_key",
        "seedance_api_key",
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
        """未显式设置模型且走 Butterbase 时，使用网关常用前缀。"""
        if self.butterbase_app_id and self.butterbase_api_key:
            if self.layer1_model == "gpt-4o-mini":
                object.__setattr__(self, "layer1_model", "openai/gpt-4o-mini")
            if self.layer2_model == "gpt-4o-mini":
                object.__setattr__(self, "layer2_model", "openai/gpt-4o-mini")
        return self

    def uses_butterbase_llm(self) -> bool:
        return bool(self.butterbase_app_id and self.butterbase_api_key)

    def resolve_llm(self) -> tuple[str, str, bool]:
        """(chat_completions 的 URL 前缀不含尾路径, api_key, 是否附加 response_format=json_object)。"""
        if self.uses_butterbase_llm():
            base = f"{self.butterbase_api_url.rstrip('/')}/v1/{self.butterbase_app_id}"
            return base, self.butterbase_api_key, self.butterbase_json_response
        if self.openai_api_key:
            return self.openai_base_url.rstrip("/"), self.openai_api_key, True
        raise RuntimeError(
            "未配置 LLM：请在 .env 中设置 BUTTERBASE_APP_ID 与 BUTTERBASE_API_KEY（Butterbase AI 网关），"
            "或设置 OPENAI_API_KEY（可选 OPENAI_BASE_URL 指向其它 OpenAI 兼容服务）。"
        )


def get_settings() -> Settings:
    """每次调用重新读取环境变量与 .env（开发时改配置无需依赖进程缓存）。"""
    return Settings()
