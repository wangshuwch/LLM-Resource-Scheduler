from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "LLM Resource Scheduler"
    debug: bool = True
    total_qpm_limit: int = 1000
    total_tpm_limit: int = 1000000
    llm_min_delay_ms: int = 100
    llm_max_delay_ms: int = 500


settings = Settings()
