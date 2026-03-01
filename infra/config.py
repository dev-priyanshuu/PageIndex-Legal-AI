from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "dev")
    storage_backend: str = os.getenv("STORAGE_BACKEND", "memory")  # memory|sqlite|postgres
    sqlite_path: str = os.getenv("SQLITE_PATH", "data/legal_ai.db")
    postgres_dsn: str | None = os.getenv("POSTGRES_DSN")
    redis_url: str | None = os.getenv("REDIS_URL")
    s3_bucket: str | None = os.getenv("S3_BUCKET")
    llm_default_provider: str = os.getenv("LLM_PROVIDER", "mock")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    gemini_model: str = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")
    gemini_models: str = os.getenv(
        "GEMINI_MODELS",
        ",".join(
            [
                "models/gemini-2.5-flash",
                "gemini-2.5-flash",
                "models/gemini-2.5-pro",
                "gemini-2.5-pro",
                "models/gemini-2.0-flash-001",
                "gemini-2.0-flash-001",
                "models/gemini-flash-latest",
                "gemini-flash-latest",
            ]
        ),
    )
    # PageIndex tree generation settings (also uses Gemini)
    pageindex_model: str = os.getenv("PAGEINDEX_MODEL", "models/gemini-2.5-flash")
    tree_generation_mode: str = os.getenv("TREE_GENERATION_MODE", "auto")  # auto|pageindex|local

    # LangSmith observability
    langsmith_api_key: str | None = os.getenv("LANGSMITH_API_KEY")
    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "pageindex-legal-ai")
    langsmith_tracing: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"


SETTINGS = Settings()
