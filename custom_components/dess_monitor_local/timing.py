"""Update-interval helpers shared by the config flow and the coordinator.

The EyBond dongle answers over a single, cycling TCP session: it clean-closes
roughly every four seconds, waits up to three seconds for a forwarded command,
and takes up to five seconds to answer. A one-second poll therefore lands in
session gaps and mostly produces timeouts. Five seconds is the practical floor
used by the other DESS integrations; other transports keep the one-second
minimum.

Keeping the clamp here (instead of only in the UI selector) protects existing
entries whose stored option is below the floor, a hand-edited options file, and
future callers that forget to validate. It also means the coordinator and the
config flow cannot drift apart.
"""
from __future__ import annotations

import logging

from .const import (
    DEFAULT_UPDATE_INTERVAL,
    MAX_UPDATE_INTERVAL,
    MIN_EYBOND_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
    PROTOCOL_EYBOND,
    TRANSPORT_EYBOND,
)

_LOGGER = logging.getLogger(__name__)


def is_eybond_transport(
    transport: str | None = None,
    protocol: str | None = None,
    uri: str | None = None,
) -> bool:
    """Return True when the endpoint is served by an EyBond dongle.

    Covers the current ``transport``/``protocol`` options, the legacy
    ``PROTOCOL_EYBOND`` value, and every URI scheme the dispatcher accepts
    (``eybond://``, ``eybond-modbus://``, ``eybond-pi18://``).
    """
    if transport == TRANSPORT_EYBOND or protocol == PROTOCOL_EYBOND:
        return True
    return bool(uri and str(uri).startswith("eybond"))


def min_update_interval(
    *,
    transport: str | None = None,
    protocol: str | None = None,
    uri: str | None = None,
) -> int:
    """Minimum base poll interval for this endpoint, in seconds."""
    if is_eybond_transport(transport=transport, protocol=protocol, uri=uri):
        return MIN_EYBOND_UPDATE_INTERVAL
    return MIN_UPDATE_INTERVAL


def clamp_update_interval(
    value: object,
    *,
    minimum: int = MIN_UPDATE_INTERVAL,
    maximum: int = MAX_UPDATE_INTERVAL,
    default: int = DEFAULT_UPDATE_INTERVAL,
) -> int:
    """Coerce a stored option to a safe integer interval.

    Invalid values fall back to ``default`` rather than the minimum: a
    corrupted option should not silently turn into the fastest possible poll.
    Valid out-of-range values are clamped and logged so the user can see why
    the effective interval differs from the stored one.
    """
    try:
        interval = int(value)
    except (TypeError, ValueError):
        _LOGGER.warning(
            "Invalid update interval %r; falling back to %ss", value, default
        )
        return default

    if interval < minimum:
        _LOGGER.warning(
            "Update interval %ss is below the %ss minimum; using %ss",
            interval,
            minimum,
            minimum,
        )
        return minimum
    if interval > maximum:
        _LOGGER.warning(
            "Update interval %ss is above the %ss maximum; using %ss",
            interval,
            maximum,
            maximum,
        )
        return maximum
    return interval
