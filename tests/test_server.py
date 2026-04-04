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

    @patch("bear_mcp.server._connect")
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
