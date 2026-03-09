"""Tests for database connection and index management."""

from unittest.mock import MagicMock, patch, PropertyMock
import pytest

import app.utils.database_utils.database_utils as database_utils


class TestValidateIndex:
    def test_valid_simple_name(self):
        database_utils.validate_index("ValueFulltextIndex")

    def test_valid_with_underscores(self):
        database_utils.validate_index("my_index_1")

    def test_rejects_spaces(self):
        with pytest.raises(ValueError, match="Invalid index name"):
            database_utils.validate_index("bad index")

    def test_rejects_special_chars(self):
        with pytest.raises(ValueError, match="Invalid index name"):
            database_utils.validate_index("index; DROP INDEX")

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Invalid index name"):
            database_utils.validate_index("")

    def test_rejects_starts_with_number(self):
        with pytest.raises(ValueError, match="Invalid index name"):
            database_utils.validate_index("1index")


class TestGetGraph:
    def test_raises_when_not_initialized(self):
        original = database_utils.graph
        try:
            database_utils.graph = None
            with pytest.raises(RuntimeError, match="Neo4j driver not initialized"):
                database_utils.get_graph()
        finally:
            database_utils.graph = original

    def test_returns_driver_when_initialized(self):
        mock_driver = MagicMock()
        original = database_utils.graph
        try:
            database_utils.graph = mock_driver
            assert database_utils.get_graph() is mock_driver
        finally:
            database_utils.graph = original


class TestShutdown:
    def test_closes_driver_and_sets_none(self):
        mock_driver = MagicMock()
        original = database_utils.graph
        try:
            database_utils.graph = mock_driver
            database_utils.shutdown()
            mock_driver.close.assert_called_once()
            assert database_utils.graph is None
        finally:
            database_utils.graph = original

    def test_noop_when_no_driver(self):
        original = database_utils.graph
        try:
            database_utils.graph = None
            database_utils.shutdown()  # should not raise
            assert database_utils.graph is None
        finally:
            database_utils.graph = original


class TestConnectToDatabase:
    @patch("app.utils.database_utils.database_utils.GraphDatabase")
    def test_connects_successfully(self, mock_gdb):
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        original = database_utils.graph
        try:
            database_utils.connect_to_database(max_retries=1)
            mock_driver.verify_connectivity.assert_called_once()
            assert database_utils.graph is mock_driver
        finally:
            database_utils.graph = original

    @patch("app.utils.database_utils.database_utils.time.sleep")
    @patch("app.utils.database_utils.database_utils.GraphDatabase")
    def test_retries_on_failure(self, mock_gdb, mock_sleep):
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        mock_driver.verify_connectivity.side_effect = [
            ConnectionError("down"),
            None,  # succeeds on retry
        ]
        original = database_utils.graph
        try:
            database_utils.connect_to_database(max_retries=2, retry_delay=0.1)
            assert mock_driver.verify_connectivity.call_count == 2
            assert database_utils.graph is mock_driver
        finally:
            database_utils.graph = original

    @patch("app.utils.database_utils.database_utils.time.sleep")
    @patch("app.utils.database_utils.database_utils.GraphDatabase")
    def test_raises_after_max_retries(self, mock_gdb, mock_sleep):
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        mock_driver.verify_connectivity.side_effect = ConnectionError("down")
        original = database_utils.graph
        try:
            with pytest.raises(ConnectionError, match="down"):
                database_utils.connect_to_database(max_retries=2, retry_delay=0.01)
        finally:
            database_utils.graph = original


class TestEnsureFulltextIndexes:
    def test_creates_index_when_missing(self):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        # First call (SHOW INDEXES) returns no result
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result

        database_utils.ensure_fulltext_indexes(mock_driver)

        calls = mock_session.run.call_args_list
        # Should have: SHOW INDEXES, CREATE INDEX, CALL db.awaitIndex
        assert len(calls) == 3
        assert "CREATE FULLTEXT INDEX" in calls[1][0][0]

    def test_skips_creation_when_exists(self):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        mock_result = MagicMock()
        mock_result.single.return_value = {"name": "ValueFulltextIndex"}
        mock_session.run.return_value = mock_result

        database_utils.ensure_fulltext_indexes(mock_driver)

        calls = mock_session.run.call_args_list
        # Should have: SHOW INDEXES, CALL db.awaitIndex (no CREATE)
        assert len(calls) == 2
        assert "CREATE" not in calls[1][0][0]


class TestEnsureVectorIndex:
    def test_creates_index_when_missing(self):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result

        database_utils.ensure_vector_index(mock_driver, 768)

        calls = mock_session.run.call_args_list
        assert len(calls) == 2  # SHOW + CREATE
        assert "CREATE VECTOR INDEX" in calls[1][0][0]

    def test_skips_when_dimensions_match(self):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        mock_result = MagicMock()
        mock_result.single.return_value = {
            "options": {"indexConfig": {"vector.dimensions": 768}}
        }
        mock_session.run.return_value = mock_result

        database_utils.ensure_vector_index(mock_driver, 768)

        calls = mock_session.run.call_args_list
        assert len(calls) == 1  # only SHOW, no CREATE

    def test_recreates_when_dimensions_mismatch(self):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        mock_result = MagicMock()
        mock_result.single.return_value = {
            "options": {"indexConfig": {"vector.dimensions": 512}}
        }
        mock_session.run.return_value = mock_result

        database_utils.ensure_vector_index(mock_driver, 768)

        calls = mock_session.run.call_args_list
        assert len(calls) == 3  # SHOW + DROP + CREATE
        assert "DROP INDEX" in calls[1][0][0]
        assert "CREATE VECTOR INDEX" in calls[2][0][0]
