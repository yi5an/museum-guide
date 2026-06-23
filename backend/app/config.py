from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql://museum:museum_pass@172.16.28.250:5432/museum_guide"
    llm_base_url: str = "http://172.16.28.250:8317/v1"
    llm_api_key: str = "sk-cpa-local"
    llm_model: str = "glm-5.2"
    recognize_confidence_threshold: float = 0.85
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
