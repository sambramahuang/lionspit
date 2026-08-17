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
    # DATABASE_URL is what local dev sets in .env. POSTGRES_URL is what
    # Vercel's native Supabase integration auto-provisions when a Supabase
    # project is linked to the Vercel project (found under Storage/
    # Integrations) -- it's the pooled/transaction-mode connection string,
    # same as what we want DATABASE_URL to be. Preferring DATABASE_URL
    # first means an explicit .env value always wins if both are set.
    DATABASE_URL: str = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL", "")
    CORS_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",") if o.strip()
    ]
    # Allow all origins in development, restrict in production via environment variable
    IS_DEVELOPMENT: bool = os.getenv("ENVIRONMENT", "development") == "development"

    # app.auth verifies a caller's bearer token by asking Supabase's own
    # Auth API whether it's valid (GET /auth/v1/user), rather than decoding
    # the JWT locally -- Supabase signs tokens with whichever algorithm a
    # given project is configured for (the legacy shared HS256 secret, or
    # newer asymmetric ES256 signing keys), and there's no one algorithm
    # this backend could safely hardcode. SUPABASE_URL/SUPABASE_ANON_KEY
    # are the same values the frontend already uses (VITE_SUPABASE_URL /
    # VITE_SUPABASE_ANON_KEY) -- the anon key is a public, non-sensitive
    # identifier, not a secret.
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    # Partner status (who may set/edit a matter's ethical wall) is a static
    # allowlist, not a DB table -- comma-separated verified emails,
    # lower-cased for case-insensitive comparison.
    PARTNER_EMAILS: set[str] = {
        e.strip().lower() for e in os.getenv("PARTNER_EMAILS", "").split(",") if e.strip()
    }

    def require_api_key(self) -> str:
        if not self.OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy backend/.env.example to "
                "backend/.env and add your key."
            )
        return self.OPENAI_API_KEY

    def require_supabase_url(self) -> str:
        if not self.SUPABASE_URL:
            raise RuntimeError(
                "SUPABASE_URL is not set. Copy it from the Supabase "
                "dashboard (Project Settings -> API -> Project URL) into "
                "backend/.env."
            )
        return self.SUPABASE_URL

    def require_supabase_anon_key(self) -> str:
        if not self.SUPABASE_ANON_KEY:
            raise RuntimeError(
                "SUPABASE_ANON_KEY is not set. Copy it from the Supabase "
                "dashboard (Project Settings -> API -> anon/public key) "
                "into backend/.env."
            )
        return self.SUPABASE_ANON_KEY

    def require_database_url(self) -> str:
        if not self.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. Add your Supabase Postgres connection "
                "string (transaction pooler) to backend/.env."
            )
        return self.DATABASE_URL


settings = Settings()
