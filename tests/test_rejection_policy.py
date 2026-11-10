"""Unit tests for the coordinator's pure rejection policy."""
from custom_components.dess_monitor_local.coordinators.rejection import (
    is_rejected,
)


class TestIsRejected:
    def test_success(self):
        assert is_rejected("QPIGS", None) is False
        assert is_rejected("QPIGS", "") is False

    def test_regular_command_error_is_rejected(self):
        assert is_rejected("QPIGS", "timeout") is True
        assert is_rejected("QPIRI", "CRC mismatch") is True

    def test_expected_nak_for_optional_command_is_not_rejected(self):
        assert is_rejected(
            "QPIGS2", "NAK response received. Command not accepted."
        ) is False
        assert is_rejected(
            "QFWS", "null response received"
        ) is False
        assert is_rejected(
            "QPIGS2", "Unknown command"
        ) is False

    def test_timeout_on_optional_command_is_rejected(self):
        # QPIGS2/QFWS are optional, but a timeout is a transport failure,
        # not an "unsupported command" answer.
        assert is_rejected("QPIGS2", "timeout waiting for response") is True
        assert is_rejected("QFWS", "no response") is True
