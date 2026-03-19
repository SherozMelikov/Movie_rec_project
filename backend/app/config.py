from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    env: str
    use_r2_artifacts: bool
    r2_access_key: str | None
    r2_secret_key: str | None
    r2_endpoint: str | None
    r2_bucket: str | None


def get_settings() -> Settings:
    return Settings(
        env=os.getenv("ENV", "development"),
        use_r2_artifacts=_as_bool(os.getenv("USE_R2_ARTIFACTS"), default=False),
        r2_access_key=os.getenv("R2_ACCESS_KEY"),
        r2_secret_key=os.getenv("R2_SECRET_KEY"),
        r2_endpoint=os.getenv("R2_ENDPOINT"),
        r2_bucket=os.getenv("R2_BUCKET"),
    )


settings = get_settings()