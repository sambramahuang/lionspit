"""
Vercel Serverless Function entry point for FastAPI backend.
"""
import sys
from pathlib import Path

# Add app directory to path so imports work
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))

from app.main import app

# Export the app for Vercel
__all__ = ["app"]
