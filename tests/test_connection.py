"""Tests for bear_mcp.server — connection reuse."""
from unittest.mock import patch, MagicMock, call
import sqlite3

from bear_mcp import server


class TestConnectionReuse:
    """Multiple tool calls must reuse a single SQLite connection."""

    def setup_method(self):
        """Reset connection state between tests."""
        server._shared_conn = None

    @patch("bear_mcp.server.sqlite3.connect")
    @patch("bear_mcp.server.os.path.exists", return_value=True)
    def test_get_connection_reuses(self, mock_exists, mock_connect):
        """_get_connection() called twice must return the same connection."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        conn1 = server._get_connection()
        conn2 = server._get_connection()

        assert conn1 is conn2, "Expected same connection object on second call"
        assert mock_connect.call_count == 1, (
            f"sqlite3.connect called {mock_connect.call_count} times, expected 1"
        )

    @patch("bear_mcp.server.sqlite3.connect")
    @patch("bear_mcp.server.os.path.exists", return_value=True)
    def test_connection_check_same_thread_false(self, mock_exists, mock_connect):
        """Connection must use check_same_thread=False for MCP threading."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        server._get_connection()

        connect_kwargs = mock_connect.call_args
        # check_same_thread should be explicitly set to False
        assert connect_kwargs[1].get("check_same_thread") is False or \
            "check_same_thread=False" in str(connect_kwargs), (
            "Connection must use check_same_thread=False"
        )

    @patch("bear_mcp.server._get_connection")
    def test_tools_do_not_close_connection(self, mock_get_conn):
        """Tool functions must not close the shared connection."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_get_conn.return_value = mock_conn

        # Call multiple tools
        server.search_bear_notes(query="test")
        server.list_bear_tags()

        # Connection must never be closed
        mock_conn.close.assert_not_called()
