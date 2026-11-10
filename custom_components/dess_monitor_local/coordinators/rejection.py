"""Pure rejection policy for coordinator command results.

A command can "succeed" at the transport layer while the inverter rejects
it. Treating every non-empty dict as success hides real failures, freezes
sections silently and keeps the consecutive-failure counter at zero.

Some commands are optional by design: a PI30 inverter that does not have a
second MPPT answers ``QPIGS2`` with a NAK, and PI18 devices answer ``QFWS``
the same way. Those are expected "not supported" replies and must not count
as transport failures. Every other error, including a timeout after an
expected NAK command, is a real failure.

Kept free of Home Assistant imports so the policy is unit-testable without
the full HA test harness.
"""
from __future__ import annotations

# Commands whose NAK is an expected "not supported" answer on some
# protocols. Keep this list narrow: an SMG-II QFWS timeout is a genuine
# transport failure, not an unsupported command.
NAK_EXPECTED = ("QPIGS2", "QFWS")

# Substrings that identify an explicit "the inverter does not implement
# this" reply. Matching is case-insensitive.
UNSUPPORTED_MARKERS = (
    "nak response received",
    "null response received",
    "empty response",
    "empty pi18 payload",
    "unknown command",
    "not supported",
    "unsupported",
)


def is_rejected(command: str, error: str | None) -> bool:
    """Return True when *error* means the command result must be discarded.

    ``None``/empty means success. For optional commands, an explicit
    unsupported/NAK reply is *not* a rejection (the section is simply
    empty); any other error still is.
    """
    if not error:
        return False
    lowered = error.lower()
    if command in NAK_EXPECTED:
        return not any(marker in lowered for marker in UNSUPPORTED_MARKERS)
    return True
