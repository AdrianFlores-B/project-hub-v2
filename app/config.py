from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://projecthub:projecthub@localhost:5432/projecthub"
    jwt_secret: str = "dev-only-secret-change-me-in-prod-please"
    jwt_expires_minutes: int = 60

    # defaults point at localstack; unset S3_ENDPOINT_URL to talk to real AWS
    s3_endpoint_url: str | None = "http://localhost:4566"
    s3_bucket: str = "projecthub-documents"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    aws_region: str = "us-east-1"


settings = Settings()
