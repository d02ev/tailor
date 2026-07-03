from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    api_base_url: str
    api_key: str
    github_access_token: str
    model: str = "openai/gpt-4o"

    # LLM endpoint — single source of truth so every module (Pass 1/2, project
    # matcher, cover letter, CV) hits the same configured inference API.
    llm_base_url: str = "https://models.github.ai/inference"

    # Free-tier resilience knobs. GitHub Models rate-limits aggressively, so the
    # shared client retries with backoff, spaces calls apart, and caps request time.
    request_timeout: float = 60.0          # seconds per LLM request
    max_retries: int = 5                   # attempts on 429 / 5xx before giving up
    min_seconds_between_calls: float = 3.0 # throttle: minimum spacing between calls
    cache_enabled: bool = True             # cache LLM responses to avoid re-spending quota
    cache_dir: str = ".tailor_cache"       # relative to cwd

    class Config:
        env_file = ".env.development"
        env_file_encoding = "utf-8"


settings = Settings()
