from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql://user:pass@localhost:5432/museum_guide"
    llm_base_url: str = "http://localhost:8317/v1"
    llm_api_key: str = "your-api-key"
    llm_model: str = "glm-5.2"
    recognize_confidence_threshold: float = 0.85
    host: str = "0.0.0.0"
    port: int = 8000
    admin_token: str = ""  # 采集后台访问 token，空则不校验（仅本地）


settings = Settings()
