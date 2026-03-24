"""Shared fixtures for unit tests."""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with mocked database startup."""
    with patch("app.utils.database_utils.database_utils.startup"):
        with patch("app.utils.database_utils.database_utils.shutdown"):
            from app.main import app
            with TestClient(app) as c:
                yield c
