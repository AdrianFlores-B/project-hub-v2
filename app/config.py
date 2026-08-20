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

    # shared secret for the endpoint the size-calculator lambda reports to
    internal_token: str = "dev-internal-token"
    project_size_limit_bytes: int = 50 * 1024 * 1024  # 50 MiB per project

    # share-by-email (defaults point at the mailpit container)
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    email_from: str = "noreply@projecthub.local"
    app_base_url: str = "http://localhost:8000"
    share_token_expires_hours: int = 72


settings = Settings()
