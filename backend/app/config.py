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
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", str(BACKEND_DIR / "chroma_data"))
    CORS_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()
    ]

    def require_api_key(self) -> str:
        if not self.OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy backend/.env.example to "
                "backend/.env and add your key."
            )
        return self.OPENAI_API_KEY


settings = Settings()
