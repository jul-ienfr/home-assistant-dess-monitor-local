"""Shared helpers for writable SMG-II Modbus settings.

The read-only telemetry lives in the coordinator's QPIGS projection; the
config registers live in QPIRI. These helpers keep the config entities
(select / number / switch) on the same command queue as the poller so a
write can never interleave with a read on the half-duplex RS485 bus.
"""
from __future__ import annotations

from .api.commands.direct_command_queue import get_command_queue

# Hardware limits of the 4.2 kW / 24 V SMG-II documented in PROTOCOL.md.
# Keep these as floats: the registers use 0.1 A resolution.
SMG2_MAX_CHARGE_CURRENT = 100.0
SMG2_MAX_UTILITY_CHARGE_CURRENT = 80.0

# Utility charging is offered in whole-ampere steps. The 4.2 kW / 24 V
# SMG-II reports 80 A on register 333; never offer 110/120 A.
UTILITY_CURRENT_STEPS = (2, 10, 20, 30, 40, 50, 60, 70, 80)


def max_utility_charging_current_options(qpiri: dict | None) -> list[str]:
    """Return valid utility-charge-current steps for this inverter.

    Register 333 is capped at 80 A on the 4.2 kW SMG-II. When the inverter
    reports a lower total charge limit (register 332), that lower value is
    used as the cap instead.
    """
    cap = SMG2_MAX_UTILITY_CHARGE_CURRENT
    raw = (qpiri or {}).get("max_charging_current")
    try:
        reported = int(float(raw))
    except (TypeError, ValueError):
        reported = 0
    if reported >= UTILITY_CURRENT_STEPS[0]:
        cap = min(cap, reported)
    options = [str(value) for value in UTILITY_CURRENT_STEPS if value <= cap]
    return options or [str(UTILITY_CURRENT_STEPS[1])]


def min_total_charge_current(qpiri: dict | None) -> float:
    """Return the firmware's lower bound for the total charge current.

    SMG-II program 02 (register 332) is the *total* charging current, not a
    solar-only limit: the manual states
    ``max charging current = utility charging current + solar charging current``.
    The firmware also refuses a total lower than program 11 (register 333),
    the maximum mains charging current. Expose that bound so the number
    entity cannot send a value the inverter will reject.
    """
    raw = (qpiri or {}).get("max_utility_charging_current")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, value)


def ui_language(hass) -> str:
    """Return the HA UI language, defaulting to English."""
    language = getattr(getattr(hass, "config", None), "language", None) or "en"
    return "fr" if str(language).lower().startswith("fr") else "en"


async def async_write_smg2_register(
    hass, device: str, address: int, value: int
) -> dict:
    """Write one holding register through the shared endpoint queue."""
    # Lazy import: the dispatcher pulls in the optional serial transports,
    # and pure tests / non-serial runtimes must still be able to import the
    # setting tables.
    from .api.dispatcher import set_register

    queue = await get_command_queue(hass, device)
    return await queue.enqueue(lambda: set_register(device, address, value))
