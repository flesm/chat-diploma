from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.example", extra="ignore")

    mongo_url: str = Field(alias="MONGO_URL")
    mongo_db: str = Field(alias="MONGO_DB")
    auth_api_url: str = Field(alias="AUTH_API_URL")
    core_api_url: str = Field(alias="CORE_API_URL")
