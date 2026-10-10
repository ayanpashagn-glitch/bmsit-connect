from pydantic import Field
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str
    cors_origins: list[str] = ['http://localhost:3000', 'http://localhost:5173']
    cookie_secure: bool = False
    public_origin: str = ""
    redis_url: str = ''
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)
    uploads_enabled: bool = True
    session_hours: int = Field(default=24, ge=1, le=168)
    # Restrict registration to college-controlled email domains for deployment.
    allowed_email_domains: list[str] = []


    smtp_host: str = ''
    smtp_port: int = 587
    smtp_username: str = ''
    smtp_password: str = ''
    smtp_from: str = ''
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_timeout_seconds: int = Field(default=10, ge=2, le=30)
    # Per-IP ceiling across all auth endpoints. Campus Wi-Fi often shares one public IP,
    # so raise this for a whole-college rollout; per-account limits still stop guessing.
    auth_ip_limit_per_minute: int = Field(default=300, ge=10, le=100000)

    google_client_id: str = ''
    google_hosted_domain: str = ''
    storage_backend: Literal['local','s3'] = 'local'
    media_root: str = '.data/covers'
    s3_bucket: str = ''
    s3_endpoint_url: str = ''
    s3_region: str = 'us-east-1'
    s3_access_key_id: str = ''
    s3_secret_access_key: str = ''
    cover_max_bytes: int = Field(default=2_000_000, ge=1000, le=2_000_000)

settings = Settings()
