"""
Vercel Serverless Function entry point for FastAPI backend.
"""
import sys
from pathlib import Path

# Add backend directory to path so imports work
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.main import app

# Export the app for Vercel
__all__ = ["app"]
