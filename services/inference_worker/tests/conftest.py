import os
import sys

# Ensure `app.main` is importable when pytest is invoked from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    """TestClient entered as a context manager so the lifespan runs."""
    with TestClient(app) as c:
        yield c
