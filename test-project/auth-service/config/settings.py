from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    postgres_url: str = "postgresql+asyncpg://auth:auth@localhost:5432/auth_db"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    token_ttl: int = 900  # 15 minutes
    refresh_ttl: int = 2_592_000  # 30 days

    google_oauth_client_id: str = ""
    google_oauth_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/oauth/google/callback"

    password_min_length: int = 8
    max_login_attempts: int = 5
    lockout_duration: int = 900  # 15 minutes

    service_name: str = "auth-service"
    debug: bool = False

    model_config = {"env_prefix": "AUTH_"}


settings = AuthSettings()
