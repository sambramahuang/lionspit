"""
Central config. Everything sensitive comes from environment variables
(loaded from .env in local dev via python-dotenv). Nothing here should
ever hold a real key -- .env is gitignored on purpose.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load backend/.env if present. Safe no-op if it doesn't exist yet.
BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    # text-embedding-3-small: 1536 dimensions, cheap, no local model download --
    # unlike Chroma's old bundled embedding model, this is just an HTTP call,
    # so it works the same in local dev and stateless serverless functions.
    OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    CORS_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",") if o.strip()
    ]
    # Allow all origins in development, restrict in production via environment variable
    IS_DEVELOPMENT: bool = os.getenv("ENVIRONMENT", "development") == "development"

    def require_api_key(self) -> str:
        if not self.OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy backend/.env.example to "
                "backend/.env and add your key."
            )
        return self.OPENAI_API_KEY

    def require_database_url(self) -> str:
        if not self.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. Add your Supabase Postgres connection "
                "string (transaction pooler) to backend/.env."
            )
        return self.DATABASE_URL


settings = Settings()
