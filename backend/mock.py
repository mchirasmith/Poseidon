"""Mock server: same routes as the live API, served from bundled fixtures."""
from pathlib import Path

from app.config import Settings
from app.deps import FixtureBackend
from app.main import create_app

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

settings = Settings()
app = create_app(backend=FixtureBackend(FIXTURES_DIR, settings), settings=settings)
