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

# Vercel Functions have a read-only filesystem everywhere except /tmp. Two
# separate things need a writable path there, so both get redirected before
# anything (chromadb included) has a chance to touch them:
#   1. ChromaDB's PersistentClient, which writes its SQLite file under
#      CHROMA_PERSIST_DIR.
#   2. Chroma's local embedding model (all-MiniLM-L6-v2), which downloads
#      and caches under `~` (os.path.expanduser) the first time it runs --
#      Vercel's sandbox sets HOME to a read-only directory, so that cache
#      write fails too unless HOME itself points somewhere writable.
# Vercel sets VERCEL=1 in every deployment environment, so use that to
# switch both without touching local dev's real home directory.
ON_VERCEL = bool(os.getenv("VERCEL"))
if ON_VERCEL:
    os.environ["HOME"] = "/tmp"

_DEFAULT_CHROMA_DIR = "/tmp/chroma_data" if ON_VERCEL else str(BACKEND_DIR / "chroma_data")


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
