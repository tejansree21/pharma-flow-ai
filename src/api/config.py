"""
PharmaFlow AI — Production Configuration & Security Layer (Phase 5)
====================================================================
Centralises all configuration via environment variables with secure defaults.
Provides:
  - Settings class (pydantic-settings compatible)
  - API Key authentication middleware
  - JWT token generation / verification
  - Rate limiting helpers
"""

import os
import secrets
import logging
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env from project root
_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")

log = logging.getLogger("pharma.config")


# ═════════════════════════════════════════════════════════════════════════════
# Settings
# ═════════════════════════════════════════════════════════════════════════════

class Settings:
    """
    Centralised app settings. Reads from environment variables with safe defaults.
    Access via get_settings() (cached singleton).
    """

    def __init__(self):
        # Server
        self.api_host: str          = os.getenv("API_HOST", "0.0.0.0")
        self.api_port: int          = int(os.getenv("API_PORT", "8000"))
        self.environment: str       = os.getenv("ENVIRONMENT", "development")
        self.log_level: str         = os.getenv("LOG_LEVEL", "INFO")

        # Security
        self.secret_key: str        = os.getenv("SECRET_KEY", secrets.token_hex(32))
        self.api_key: str           = os.getenv("API_KEY", "")
        self.jwt_algorithm: str     = os.getenv("JWT_ALGORITHM", "HS256")
        self.token_expire_minutes   = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

        # Rate limiting
        self.rate_limit_per_minute  = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

        # CORS
        raw_origins = os.getenv("CORS_ORIGINS", "*")
        self.cors_origins = [o.strip() for o in raw_origins.split(",")]

        # Paths
        self.data_dir  = _ROOT / os.getenv("DATA_DIR", "data")
        self.models_dir = _ROOT / os.getenv("MODELS_DIR", "models")

        # Feature flags
        self.news_api_key: str      = os.getenv("NEWS_API_KEY", "")
        self.news_api_enabled: bool = os.getenv("NEWS_API_ENABLED", "false").lower() == "true"
        self.gdelt_enabled: bool    = os.getenv("GDELT_ENABLED", "false").lower() == "true"
        self.prometheus_enabled: bool = os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"
        self.metrics_path: str      = os.getenv("METRICS_PATH", "/metrics")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def auth_enabled(self) -> bool:
        """Auth is enforced in production and when API_KEY is set."""
        return self.is_production or bool(self.api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# ═════════════════════════════════════════════════════════════════════════════
# API Key Authentication
# ═════════════════════════════════════════════════════════════════════════════

from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: Optional[str] = Security(_API_KEY_HEADER),
) -> str:
    """
    FastAPI dependency — verifies X-API-Key header.
    Skipped entirely if auth is disabled (development without API_KEY set).
    """
    settings = get_settings()

    if not settings.auth_enabled:
        return "no-auth"

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    # Constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return api_key


# ═════════════════════════════════════════════════════════════════════════════
# JWT (for future user-facing auth — e.g. admin portal)
# ═════════════════════════════════════════════════════════════════════════════

try:
    from jose import JWTError, jwt
    _JWT_AVAILABLE = True
except ImportError:
    _JWT_AVAILABLE = False
    log.warning("python-jose not installed — JWT auth disabled")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    if not _JWT_AVAILABLE:
        raise RuntimeError("python-jose required for JWT tokens")
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    if not _JWT_AVAILABLE:
        raise RuntimeError("python-jose required for JWT tokens")
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )


# ═════════════════════════════════════════════════════════════════════════════
# Logging setup
# ═════════════════════════════════════════════════════════════════════════════

def configure_logging():
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    # Silence noisy libraries in production
    if settings.is_production:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("watchfiles").setLevel(logging.ERROR)
