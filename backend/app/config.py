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

# Vercel Functions have a read-only filesystem everywhere except /tmp, so
# ChromaDB's PersistentClient can't create its SQLite file under the deployed
# backend folder there. Vercel sets VERCEL=1 in every deployment environment,
# so use that to fall back to the writable /tmp scratch space on Vercel while
# keeping the normal on-disk path for local dev. Note /tmp is ephemeral --
# wiped between cold starts -- so a Vercel deployment starts empty and relies
# on live ingestion (the app's actual demo flow) rather than a seeded corpus
# persisting between sessions.
_DEFAULT_CHROMA_DIR = "/tmp/chroma_data" if os.getenv("VERCEL") else str(BACKEND_DIR / "chroma_data")


class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", _DEFAULT_CHROMA_DIR)
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


settings = Settings()
