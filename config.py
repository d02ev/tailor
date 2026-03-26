from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    api_base_url: str
    api_key: str
    github_access_token: str
    model: str = "openai/gpt-4o"

    class Config:
        env_file = ".env.development"
        env_file_encoding = "utf-8"


settings = Settings()