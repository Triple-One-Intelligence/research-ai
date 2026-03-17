"""Shared fixtures for the test suite."""

import os
import pytest
from unittest.mock import MagicMock

# Set required env vars before any app imports
os.environ.setdefault("REMOTE_NEO4J_URL", "bolt://localhost:7687")
os.environ.setdefault("REMOTE_NEO4J_USER", "neo4j")
os.environ.setdefault("REMOTE_NEO4J_PASS", "testpassword")
os.environ.setdefault("AI_SERVICE_URL", "http://localhost:11434")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")


@pytest.fixture
def mock_neo4j_driver():
    """A mock Neo4j driver with session and transaction support."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver, session
