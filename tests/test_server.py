"""Tests for bear_mcp.server — timezone awareness and input validation."""
import datetime
from unittest.mock import patch, MagicMock

from bear_mcp import server


class TestCoreDataTimestamp:
    """Core Data epoch and cutoff must be timezone-aware (UTC)."""

    def test_core_data_epoch_is_utc(self):
        """_CORE_DATA_EPOCH must have tzinfo=UTC."""
        assert server._CORE_DATA_EPOCH.tzinfo is not None, (
            "_CORE_DATA_EPOCH is naive — must be timezone-aware (UTC)"
        )
        assert server._CORE_DATA_EPOCH.tzinfo == datetime.timezone.utc

    @patch("bear_mcp.server._get_connection")
    def test_cutoff_timestamp_is_correct(self, mock_connect):
        """get_recent_notes must compute a UTC-based Core Data timestamp."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_connect.return_value = mock_conn

        # Call with known parameters
        server.get_recent_notes(days=7, limit=10)

        # Extract the cutoff value passed to the SQL query
        call_args = mock_conn.execute.call_args
        assert call_args is not None, "execute was never called"
        params = call_args[0][1]  # second positional arg = params tuple
        cutoff = params[0]

        # Compute expected cutoff using UTC
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        epoch = datetime.datetime(2001, 1, 1, tzinfo=datetime.timezone.utc)
        expected = (now_utc - datetime.timedelta(days=7) - epoch).total_seconds()

        # Allow 5 seconds tolerance for test execution time
        assert abs(cutoff - expected) < 5, (
            f"Cutoff {cutoff} differs from expected UTC-based value {expected}"
        )


class TestInputValidation:
    """limit and days parameters must be clamped to sensible ranges."""

    @patch("bear_mcp.server._get_connection")
    def test_limit_negative_clamped(self, mock_connect):
        """limit=-1 should be clamped to 1."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_connect.return_value = mock_conn

        server.search_bear_notes(query="test", limit=-1)

        params = mock_conn.execute.call_args[0][1]
        limit_param = params[-1]  # limit is always last param
        assert limit_param >= 1, f"limit was {limit_param}, expected >= 1"

    @patch("bear_mcp.server._get_connection")
    def test_limit_zero_clamped(self, mock_connect):
        """limit=0 should be clamped to 1."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_connect.return_value = mock_conn

        server.search_bear_notes(query="test", limit=0)

        params = mock_conn.execute.call_args[0][1]
        limit_param = params[-1]
        assert limit_param >= 1, f"limit was {limit_param}, expected >= 1"

    @patch("bear_mcp.server._get_connection")
    def test_limit_over_500_clamped(self, mock_connect):
        """limit=9999 should be clamped to 500."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_connect.return_value = mock_conn

        server.search_bear_notes(query="test", limit=9999)

        params = mock_conn.execute.call_args[0][1]
        limit_param = params[-1]
        assert limit_param <= 500, f"limit was {limit_param}, expected <= 500"

    @patch("bear_mcp.server._get_connection")
    def test_days_negative_clamped(self, mock_connect):
        """days=-5 should be clamped to 1."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_connect.return_value = mock_conn

        server.get_recent_notes(days=-5, limit=10)

        params = mock_conn.execute.call_args[0][1]
        cutoff = params[0]

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        epoch = datetime.datetime(2001, 1, 1, tzinfo=datetime.timezone.utc)
        expected_1day = (now_utc - datetime.timedelta(days=1) - epoch).total_seconds()

        assert abs(cutoff - expected_1day) < 5, (
            f"days=-5 was not clamped to 1: cutoff={cutoff}, expected ~{expected_1day}"
        )

    @patch("bear_mcp.server._get_connection")
    def test_days_over_365_clamped(self, mock_connect):
        """days=9999 should be clamped to 365."""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_connect.return_value = mock_conn

        server.get_recent_notes(days=9999, limit=10)

        params = mock_conn.execute.call_args[0][1]
        cutoff = params[0]

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        epoch = datetime.datetime(2001, 1, 1, tzinfo=datetime.timezone.utc)
        expected_365 = (now_utc - datetime.timedelta(days=365) - epoch).total_seconds()

        assert abs(cutoff - expected_365) < 5, (
            f"days=9999 was not clamped to 365: cutoff={cutoff}, expected ~{expected_365}"
        )
