from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "YUEDMAI Next")
    app_env: str = os.getenv("APP_ENV", "development")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    pose_backend: str = os.getenv("POSE_BACKEND", "mock")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./yuedmai.db")


settings = Settings()
