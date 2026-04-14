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
    use_r2 = _as_bool(os.getenv("USE_R2_ARTIFACTS"), default=False)

    access = os.getenv("R2_ACCESS_KEY")
    secret = os.getenv("R2_SECRET_KEY")
    endpoint = os.getenv("R2_ENDPOINT")
    bucket = os.getenv("R2_BUCKET")

    if use_r2:
        missing = [
            name for name, val in [
                ("R2_ACCESS_KEY", access),
                ("R2_SECRET_KEY", secret),
                ("R2_ENDPOINT", endpoint),
                ("R2_BUCKET", bucket),
            ] if not val
        ]

        if missing:
            raise RuntimeError(f"Missing required R2 env vars: {missing}")

    return Settings(
        env=os.getenv("ENV", "development"),
        use_r2_artifacts=use_r2,
        r2_access_key=access,
        r2_secret_key=secret,
        r2_endpoint=endpoint,
        r2_bucket=bucket,
    )
settings = get_settings()