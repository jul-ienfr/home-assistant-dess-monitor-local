import asyncio
import logging
import time
from datetime import datetime, timedelta

import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from custom_components.dess_monitor_local import diag_hub
from custom_components.dess_monitor_local.api.commands.direct_command_queue import (
    get_command_queue,
)
from custom_components.dess_monitor_local.api.dispatcher import get_direct_data
from custom_components.dess_monitor_local.const import (
    CONF_DEVICE,
    CONF_NAME,
    CONF_PROTOCOL,
    CONF_STRICT_CRC,
    CONF_UPDATE_INTERVAL,
    DEFAULT_STRICT_CRC,
    DEFAULT_UPDATE_INTERVAL,
    PROTOCOL_VOLTRONIC,
)
from custom_components.dess_monitor_local.coordinators.device_target import DeviceTarget
from custom_components.dess_monitor_local.coordinators.failure_tracker import (
    FailureOutcome,
    FailureTracker,
)
from custom_components.dess_monitor_local.coordinators.rejection import (
    is_rejected,
)

_LOGGER = logging.getLogger(__name__)


def _qpiri_values_match(fetched, expected) -> bool:
    """Compare a polled QPIRI value with an optimistic write value."""
    try:
        return abs(float(fetched) - float(expected)) < 0.01
    except (TypeError, ValueError):
        return str(fetched) == str(expected)


class DirectCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""
    devices = []

    # Resilience to transient transport errors (CRC mismatches, brief
    # buffer corruption, gateway hiccups). One fast retry per command,
    # then up to N-1 consecutive failures fall back to the last known
    # sub-dict before the entity finally goes to "unavailable".
    _RETRY_DELAY_S = 0.25
    # 6 (not 3): EyBond dongles clean-close every ~4s and reconnect in ~1s, so a
    # child's poll occasionally lands in a gap and fails. With the now-short
    # cycles a child reaches 3 consecutive failures in ~30s, flickering entities
    # to "unavailable" during normal cycling. Tolerate more transient misses —
    # stay on frozen last-known — before flipping unavailable.
    _MAX_CONSECUTIVE_FAILURES = 6
    # Per-command poll cadence (poll every Nth cycle; carry forward in between).
    # Live telemetry every cycle keeps values fresh and the per-cycle command
    # count tiny (fits a cycling dongle's brief window → far fewer failures);
    # static/slow data is refreshed periodically. (cmd, section, every_n_cycles)
    _CMD_SCHEDULE = (
        ("QPIGS", "qpigs", 1),    # live telemetry — every cycle
        ("QMOD", "qmod", 2),      # operating mode — changes slowly
        ("QPIGS2", "qpigs2", 2),  # 2nd MPPT (often NAK'd)
        ("QPIWS", "qpiws", 3),    # warnings/faults (PI30)
        ("QFWS", "qfws", 3),      # warnings/faults (PI18)
        ("QPIRI", "qpiri", 12),   # ratings/nameplate — essentially static
    )
    # Per-device poll bound, applied ONLY with multiple devices (an EyBond hub
    # with several children). One stuck/half-attentive dongle answering FC=4
    # slowly used to drag the whole-hub gather past the 120s cycle cap, which
    # failed the entire update and starved EVERY child of data ("one update per
    # ~30 min" in the field). Capping each child means a stuck one freezes on
    # last-known for the cycle while the healthy ones still publish on time.
    # Single-device entries stay uncapped — a legacy cloud-proxied transport can
    # legitimately take minutes and has no sibling to starve.
    # With per-dongle parallelism the cycle is the SLOWEST child (not the sum),
    # and the publish is atomic at that point, so keep the bound tight: a child
    # stuck past this (its dongle gone for the whole poll) freezes on last-known
    # rather than dragging every entity's update behind it.
    _PER_DEVICE_POLL_TIMEOUT = 25.0
    # Keep an optimistic QPIRI write visible until a fresh read confirms it.
    # A poll that was already in flight when the write landed can still
    # return the old register value; publishing that would shrink the
    # register-333 select back before the caller can use the new options.
    _QPIRI_OVERRIDE_TTL_S = 60.0

    def __init__(self, hass: HomeAssistant, config_entry, targets=None):
        """Initialize my coordinator.

        ``targets`` is an explicit list of :class:`DeviceTarget` to poll
        (used by the EyBond hub, where children are derived from the
        discovery registry). When ``None``, the coordinator falls back to
        the legacy single ``CONF_DEVICE`` from the entry options.
        """
        interval_seconds = int(
            config_entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Direct request sensor",
            config_entry=config_entry,
            update_interval=timedelta(seconds=interval_seconds),
            # Set always_update to `False` if the data returned from the
            # api can be compared via `__eq__` to avoid duplicate updates
            # being dispatched to listeners
            always_update=False

        )
        self._targets = targets
        # Per-(target id, command) consecutive-failure counter + freeze policy.
        self._failures = FailureTracker(self._MAX_CONSECUTIVE_FAILURES)
        # Cycle counter driving the split poll cadence (see _CMD_SCHEDULE).
        self._cycle = 0
        # Sections that must be refreshed on the next cycle even if their
        # normal cadence says otherwise (used by the select entities after
        # a write so the optimistic value is confirmed immediately).
        self._forced_sections: set[str] = set()
        # Optimistic QPIRI writes: {device_id: {data_key: (value, expires)}}
        self._pending_qpiri: dict[str, dict[str, tuple[str, float]]] = {}
        self._cmd_by_section = {
            section: cmd for cmd, section, _ in self._CMD_SCHEDULE
        }
        # self.my_api = my_api
        # self._device: MyDevice | None = None

    async def _async_setup(self):
        """Set up the coordinator

        This is the place to set up your coordinator,
        or to load data, that only needs to be loaded once.

        This method will be called automatically during
        coordinator.async_config_entry_first_refresh.
        """
        self.devices = await self.get_active_devices()

    def set_targets(self, targets) -> None:
        """Swap the explicit poll-target list at runtime.

        Used by the EyBond hub's in-place child reconcile (no entry reload):
        the next poll cycle reads ``self.devices``, and ``_async_update_data``
        snapshots it per cycle, so replacing the list between cycles is safe.
        """
        self._targets = list(targets)
        self.devices = list(targets)

    def _child_failure_summary(self) -> dict:
        """Per-child ``"ok"`` / ``"fail:N"`` for the debug panel's cycle event."""
        out: dict = {}
        for target in self.devices:
            key = getattr(target, "id", target)
            n = sum(
                self._failures.count(key, cmd)
                for cmd, _section, _cadence in self._CMD_SCHEDULE
            )
            out[key] = "ok" if n == 0 else f"fail:{n}"
        return out

    def force_section(self, section: str) -> None:
        """Refresh *section* on the next poll regardless of its cadence.

        Called after a successful write so a select does not have to wait
        up to 12 cycles (2 minutes at the default interval) for QPIRI to
        confirm the new value.
        """
        self._forced_sections.add(section)

    def update_cached_qpiri(self, device_id: str, **values) -> None:
        """Patch cached QPIRI values after a successful write.

        Dependent entities recompute from this cache: the register-333
        select's options are capped by register 332, and register 332's
        minimum is register 333. Without the patch they keep the stale
        coupling until the next QPIRI poll (up to 12 cycles away), which
        made a 332 write followed by a 333 write fail with "Option 80 is
        not valid". The override is kept until a fresh QPIRI read matches
        it, because a poll already in flight when the write lands can still
        return the old value.
        """
        now = time.monotonic()
        pending = self._pending_qpiri.setdefault(device_id, {})
        for key, value in values.items():
            pending[key] = (str(value), now + self._QPIRI_OVERRIDE_TTL_S)

        data = self.data
        patched = False
        if data:
            device = data.get(device_id)
            if isinstance(device, dict):
                qpiri = device.get("qpiri")
                if isinstance(qpiri, dict):
                    qpiri.update(
                        {key: str(value) for key, value in values.items()}
                    )
                    patched = True
        if patched:
            self.async_update_listeners()

    def _apply_qpiri_overrides(self, device_id: str, qpiri: dict) -> None:
        """Keep optimistic writes in front of a stale fresh poll.

        Called on every successfully read QPIRI section. A value that now
        matches is confirmed and dropped; a different one is kept only
        until its TTL, so a failed write eventually shows the real value.
        """
        pending = self._pending_qpiri.get(device_id)
        if not pending:
            return
        now = time.monotonic()
        for key, (value, expires) in list(pending.items()):
            if now >= expires:
                pending.pop(key, None)
            elif _qpiri_values_match(qpiri.get(key), value):
                pending.pop(key, None)
            else:
                qpiri[key] = value
        if not pending:
            self._pending_qpiri.pop(device_id, None)

    def section_failures(self, device_id: str, section: str) -> int:
        """Consecutive failures for the command that feeds *section*."""
        cmd = self._cmd_by_section.get(section)
        return self._failures.count(device_id, cmd) if cmd else 0

    async def get_active_devices(self):
        # Explicit targets (EyBond hub children) take precedence.
        if self._targets is not None:
            return list(self._targets)

        device = self.config_entry.options.get(CONF_DEVICE, None)
        if not device:
            # No device URI configured (entry created but never finished setup,
            # or options got wiped). Returning an empty list lets the
            # coordinator complete without crashing in `_async_update_data`
            # where dispatcher code does ``device.startswith(...)``.
            _LOGGER.warning(
                "No device URI configured for entry %s; nothing to poll",
                self.config_entry.entry_id,
            )
            return []
        # Legacy single-device entry: id == uri preserves existing
        # entity unique_ids and HA device identifiers.
        protocol = self.config_entry.options.get(CONF_PROTOCOL, PROTOCOL_VOLTRONIC)
        name = self.config_entry.data.get(CONF_NAME) or "Inverter"
        return [DeviceTarget(id=device, uri=device, protocol=protocol, name=name)]

    async def _async_update_data(self):
        strict_crc = bool(
            self.config_entry.options.get(CONF_STRICT_CRC, DEFAULT_STRICT_CRC)
        )
        prev_data = self.data or {}

        async def fetch_with_retry(key: str, uri: str, cmd: str, section: str) -> dict:
            """Read a command with one fast retry, then apply the pure
            freeze/unavailable policy (see FailureTracker).

            ``key`` is the target's stable id (failure tracking + last-known
            lookup); ``uri`` is the transport address the command is sent to.
            """
            # EyBond children are serialized per-dongle inside the manager
            # (per-session send_lock), so routing them through the single
            # global CommandQueue would serialize across dongles too — making
            # the cycle the SUM of every child's command times and letting one
            # cycling dongle stall the rest. Send those directly so the
            # per-child gather actually polls the dongles in parallel. The
            # legacy single-device path keeps the queue (one socket, rate-limit).
            via_queue = not uri.startswith("eybond")
            for attempt in range(2):
                try:
                    if via_queue:
                        # One serialized queue per physical endpoint (host:port /
                        # serial path) — same device can't interleave, different
                        # devices poll in parallel.
                        queue = await get_command_queue(self.hass, uri)
                        result = await queue.enqueue(
                            lambda d=uri, c=cmd: get_direct_data(
                                d, c, 30, strict_crc=strict_crc
                            )
                        )
                    else:
                        result = await get_direct_data(
                            uri, cmd, 30, strict_crc=strict_crc
                        )
                except Exception as err:  # transport raised unexpectedly
                    _LOGGER.debug(
                        "%s/%s attempt %d raised %r", key, cmd, attempt + 1, err
                    )
                    result = None
                if result:
                    error = (
                        result.get("error")
                        if isinstance(result, dict)
                        else None
                    )
                    if is_rejected(cmd, error):
                        # A real NAK/exception is not a successful read. Fall
                        # through to the retry/failure path instead of
                        # resetting the counter and publishing the error dict.
                        result = None
                    elif error:
                        # Expected "not supported" reply (e.g. QPIGS2 on a
                        # single-MPPT inverter): count it as a clean empty
                        # section, not as a transport failure.
                        self._failures.on_success(key, cmd)
                        return {}
                    else:
                        self._failures.on_success(key, cmd)
                        if section == "qpiri" and isinstance(result, dict):
                            self._apply_qpiri_overrides(key, result)
                        return result
                if attempt == 0:
                    await asyncio.sleep(self._RETRY_DELAY_S)

            count = self._failures.on_failure(key, cmd)
            last_known = (prev_data.get(key) or {}).get(section) or {}
            data, outcome = self._failures.resolve(count, last_known)
            if outcome is FailureOutcome.FREEZE:
                _LOGGER.debug(
                    "%s/%s read failed (consecutive=%d/%d); freezing on last known data",
                    key, cmd, count, self._MAX_CONSECUTIVE_FAILURES,
                )
            elif outcome is FailureOutcome.UNAVAILABLE:
                _LOGGER.warning(
                    "%s/%s failed %d times in a row; flipping to unavailable",
                    key, cmd, count,
                )
            return data

        try:
            async with async_timeout.timeout(120):
                cycle = self._cycle
                # Consume the forced-section set once per cycle. A write
                # that happens while this cycle is running is picked up by
                # the next one (the set is not cleared later).
                forced = self._forced_sections
                self._forced_sections = set()

                async def fetch_device_data(target):
                    key = target.id
                    uri = target.uri
                    prev = prev_data.get(key) or {}
                    # Split cadence (see _CMD_SCHEDULE): poll live telemetry
                    # (QPIGS) every cycle so values stay fresh AND the per-cycle
                    # command count stays small enough to fit a cycling dongle's
                    # brief connection window; static/rare sections (ratings,
                    # faults, mode, PV2) are polled every Nth cycle and carried
                    # forward in between, so a skipped slow command never empties
                    # a section or trips its failure counter.
                    sections: dict = {"timestamp": datetime.now()}
                    for cmd, section, cadence in self._CMD_SCHEDULE:
                        if cycle % cadence == 0 or section in forced:
                            sections[section] = await fetch_with_retry(
                                key, uri, cmd, section
                            )
                        else:
                            sections[section] = prev.get(section) or {}
                    return key, sections
                    # return device, {
                    #     "timestamp": datetime.now(),
                    #     "qpigs": {
                    #         "grid_voltage": "239.7",
                    #         "grid_frequency": "50.0",
                    #         "ac_output_voltage": "230.2",
                    #         "ac_output_frequency": "50.0",
                    #         "output_apparent_power": "0095",
                    #         "output_active_power": "0095",
                    #         "load_percent": "002",
                    #         "bus_voltage": "399",
                    #         "battery_voltage": "26.50",
                    #         "battery_charging_current": "000",
                    #         "battery_capacity": "068",
                    #         "inverter_heat_sink_temperature": "0040",
                    #         "pv_input_current": "0000",
                    #         "pv_input_voltage": "000.0",
                    #         "scc_battery_voltage": "00.00",
                    #         "battery_discharge_current": "00003",
                    #         "device_status_bits_b7_b0": "00010000",
                    #         "battery_voltage_offset": "00",
                    #         "eeprom_version": "00",
                    #         "pv_charging_power": "00001",
                    #         "device_status_bits_b10_b8": "010"
                    #     },
                    #     "qpigs2": {
                    #         "error": "NAK response received. Command not accepted."
                    #     },
                    #     "qpiri": {
                    #         "rated_grid_voltage": "230.0",
                    #         "rated_input_current": "15.2",
                    #         "rated_ac_output_voltage": "230.0",
                    #         "rated_output_frequency": "50.0",
                    #         "rated_output_current": "15.2",
                    #         "rated_output_apparent_power": "3500",
                    #         "rated_output_active_power": "3500",
                    #         "rated_battery_voltage": "24.0",
                    #         "low_battery_to_ac_bypass_voltage": "24.0",
                    #         "shut_down_battery_voltage": "23.0",
                    #         "bulk_charging_voltage": "29.2",
                    #         "float_charging_voltage": "27.2",
                    #         "battery_type": "UserDefined",
                    #         "max_utility_charging_current": "30",
                    #         "max_charging_current": "050",
                    #         "ac_input_voltage_range": "UPS",
                    #         "output_source_priority": "SBU",
                    #         "charger_source_priority": "SolarFirst",
                    #         "parallel_max_number": "6",
                    #         "reserved_uu": "01",
                    #         "reserved_v": "0",
                    #         "parallel_mode": "Single",
                    #         "high_battery_voltage_to_battery_mode": "26.0",
                    #         "solar_work_condition_in_parallel": "0",
                    #         "solar_max_charging_power_auto_adjust": "1_"
                    #     }
                    # }

                # With multiple devices (hub children), bound each one so a
                # single stuck dongle can't blow the 120s cycle and starve the
                # others (see _PER_DEVICE_POLL_TIMEOUT). A device that exceeds
                # the bound freezes on its last-known data for this cycle.
                per_device_timeout = (
                    self._PER_DEVICE_POLL_TIMEOUT if len(self.devices) > 1 else None
                )

                async def fetch_device_guarded(target):
                    if per_device_timeout is None:
                        return await fetch_device_data(target)
                    key = target.id
                    try:
                        return await asyncio.wait_for(
                            fetch_device_data(target), per_device_timeout
                        )
                    except TimeoutError:
                        _LOGGER.warning(
                            "%s: poll exceeded %.0fs — freezing on last-known "
                            "data this cycle so other devices still update",
                            key, per_device_timeout,
                        )
                        return key, dict(prev_data.get(key) or {})

                _t0 = time.monotonic()
                data_map = dict(
                    await asyncio.gather(*map(fetch_device_guarded, self.devices))
                )
                if diag_hub.active():
                    diag_hub.publish({
                        "t": "cycle",
                        "dur_s": round(time.monotonic() - _t0, 2),
                        "n": cycle,
                        "children": self._child_failure_summary(),
                    })
                self._cycle += 1  # advance the split-cadence schedule
                return data_map
        except TimeoutError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise err
