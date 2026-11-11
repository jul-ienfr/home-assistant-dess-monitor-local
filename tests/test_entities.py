"""Entity-level tests — run only where Home Assistant is importable.

These exercise the thin adapter layer between the coordinator data and
HA state: the fault-summary severity machine, status-bit binary sensors,
operating-mode enum coercion, and the time-to-* projections.

Strategy: construct the entity with a fake coordinator/device, neutralise
``async_write_ha_state`` (it needs a live HA platform), then drive
``_handle_coordinator_update`` and assert the computed attributes. No HA
event loop or hass fixture required, so it stays fast and version-robust.

CI runners without Home Assistant (the 3.12/3.13 pure matrix) skip this
whole module via ``importorskip``. A separate CI job installs HA to run it.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

pytest.importorskip("homeassistant")

# Importing the real platform modules (no sys.modules stubs here) also
# acts as a smoke test: it would have caught the missing PI18-enum
# re-export that broke integration load.
from custom_components.dess_monitor_local import binary_sensor as bs  # noqa: E402
from custom_components.dess_monitor_local.sensors import (  # noqa: E402
    direct_energy_sensors as des,
)
from custom_components.dess_monitor_local.sensors import direct_sensor as ds  # noqa: E402


class _Dev:
    inverter_id = "easun_4200"
    name = "easun 4200"
    firmware_version = "0.0.1"


class _Coord:
    """Minimal stand-in for the DataUpdateCoordinator."""
    def __init__(
        self,
        data,
        *,
        interval=10,
        failures=None,
        last_success=None,
        last_success_age=None,
    ):
        self.data = {"easun_4200": data}
        self.update_interval = timedelta(seconds=interval) if interval else None
        self._failures = dict(failures or {})
        self._last_success = last_success
        self._last_success_age = last_success_age

    # CoordinatorEntity registers a listener on add; never called here.
    def async_add_listener(self, *a, **k):
        return lambda: None

    def section_failures(self, device_id, section):
        return self._failures.get(section, 0)

    def last_success(self, device_id):
        return self._last_success

    def last_success_age(self, device_id):
        return self._last_success_age


def _neutralise_write(entity):
    # async_write_ha_state needs a live platform; replace with a no-op so
    # we can call _handle_coordinator_update synchronously.
    entity.async_write_ha_state = lambda: None
    return entity


def _make(cls, data, *args):
    ent = cls(_Dev(), _Coord(data), *args)
    return _neutralise_write(ent)


# ---------------------------------------------------------------------------
# Smoke: every platform module imports (regression guard for load failures)
# ---------------------------------------------------------------------------
def test_all_platforms_import():
    from custom_components.dess_monitor_local import (  # noqa: F401
        binary_sensor,
        button,
        number,
        select,
        sensor,
        switch,
    )


# ---------------------------------------------------------------------------
# DirectOperatingModeSensor
# ---------------------------------------------------------------------------
class TestOperatingModeSensor:
    def test_enum_instance_coerced_to_name(self):
        from custom_components.dess_monitor_local.api.decoders.enums import OperatingMode
        ent = _make(ds.DirectOperatingModeSensor, {"qmod": {"operating_mode": OperatingMode.Battery}})
        ent._handle_coordinator_update()
        assert ent._attr_native_value == "Battery"

    def test_unknown_string_becomes_none(self):
        ent = _make(ds.DirectOperatingModeSensor, {"qmod": {"operating_mode": "Nonsense"}})
        ent._handle_coordinator_update()
        assert ent._attr_native_value is None

    def test_missing_section(self):
        ent = _make(ds.DirectOperatingModeSensor, {"qmod": {}})
        ent._handle_coordinator_update()
        assert ent._attr_native_value is None


# ---------------------------------------------------------------------------
# DirectInverterFaultSummarySensor — severity machine
# ---------------------------------------------------------------------------
class TestFaultSummary:
    def _make(self, qpiws=None, qfws=None):
        return _make_summary({"qpiws": qpiws or {}, "qfws": qfws or {}})

    def test_ok_when_clear(self):
        ent = self._make(qpiws={"overload": False, "inverter_fault": False})
        ent._handle_coordinator_update()
        assert ent._attr_native_value == "OK"

    def test_single_warning(self):
        ent = self._make(qpiws={"overload": True})
        ent._handle_coordinator_update()
        assert ent._attr_native_value == "Warning: Overload"

    def test_multiple_warnings_shows_count(self):
        ent = self._make(qpiws={"overload": True, "fan_locked": True})
        ent._handle_coordinator_update()
        # Highest severity (fan_locked is above overload) + "+1 more".
        assert "more" in ent._attr_native_value

    def test_pi18_fault_code_takes_priority(self):
        ent = self._make(qfws={"fault_code": 2, "fault_description": "Over temperature"})
        ent._handle_coordinator_update()
        assert ent._attr_native_value == "Fault: Over temperature"

    def test_agent_warn_prefix_recognised(self):
        # Agent uses warn_* naming; the summary must see it via _flag_set.
        ent = self._make(qfws={"warn_pv_low_voltage": True})
        ent._handle_coordinator_update()
        assert ent._attr_native_value.startswith("Warning")

    def test_active_count_attribute(self):
        ent = self._make(qpiws={"overload": True, "fan_locked": True})
        ent._handle_coordinator_update()
        assert ent._attr_extra_state_attributes["active_count"] == 2


def _make_summary(data):
    ent = ds.DirectInverterFaultSummarySensor(_Dev(), _Coord(data))
    return _neutralise_write(ent)


# ---------------------------------------------------------------------------
# Status-bit binary sensors
# ---------------------------------------------------------------------------
class TestStatusBitBinarySensors:
    def _bit(self, raw_field, parser, flag_key, qpigs):
        ent = bs._StatusBitBinarySensor(
            _Dev(), _Coord(qpigs),
            raw_field=raw_field, parser=parser, flag_key=flag_key,
            sensor_suffix=flag_key, name=flag_key, device_class=None,
        )
        _neutralise_write(ent)
        ent._handle_coordinator_update()
        return ent._attr_is_on

    def test_inverter_on_true(self):
        from custom_components.dess_monitor_local.api.decoders.enums import (
            parse_device_status_bits_b7_b0,
        )
        on = self._bit(
            "device_status_bits_b7_b0", parse_device_status_bits_b7_b0,
            "inverter_on", {"qpigs": {"device_status_bits_b7_b0": "00000001"}},
        )
        assert on is True

    def test_fault_false(self):
        from custom_components.dess_monitor_local.api.decoders.enums import (
            parse_device_status_bits_b7_b0,
        )
        on = self._bit(
            "device_status_bits_b7_b0", parse_device_status_bits_b7_b0,
            "fault", {"qpigs": {"device_status_bits_b7_b0": "00000001"}},
        )
        assert on is False

    def test_missing_field_is_none(self):
        from custom_components.dess_monitor_local.api.decoders.enums import (
            parse_device_status_bits_b7_b0,
        )
        on = self._bit(
            "device_status_bits_b7_b0", parse_device_status_bits_b7_b0,
            "fault", {"qpigs": {}},
        )
        assert on is None


class TestAnyWarning:
    def _make(self, data):
        ent = bs._AnyWarningBinarySensor(_Dev(), _Coord(data))
        return _neutralise_write(ent)

    def test_off_when_all_clear(self):
        ent = self._make({"qpiws": {"overload": False}, "qfws": {}})
        ent._handle_coordinator_update()
        assert ent._attr_is_on is False

    def test_on_via_qpiws_bit(self):
        ent = self._make({"qpiws": {"overload": True}, "qfws": {}})
        ent._handle_coordinator_update()
        assert ent._attr_is_on is True

    def test_on_via_pi18_fault_code(self):
        ent = self._make({"qpiws": {}, "qfws": {"fault_code": 5}})
        ent._handle_coordinator_update()
        assert ent._attr_is_on is True

    def test_on_via_agent_warn_flag(self):
        ent = self._make({"qpiws": {}, "qfws": {"warn_overload": True}})
        ent._handle_coordinator_update()
        assert ent._attr_is_on is True


# ---------------------------------------------------------------------------
# Time-to-* sensors (use a stub SoC sensor exposing native_value/capacity_ah)
# ---------------------------------------------------------------------------
class _StubSoc:
    def __init__(self, soc, capacity):
        self.native_value = soc
        self.capacity_ah = capacity


class TestTimeToFull:
    def test_hours_to_full(self):
        soc = _StubSoc(50.0, 100.0)
        ent = ds_energy_time_to_full(soc, qpigs={"battery_charging_current": "10"})
        ent._handle_coordinator_update()
        # (100-50)/100 * 100 Ah / 10 A = 5 h.
        assert ent._attr_native_value == pytest.approx(5.0, abs=0.01)

    def test_none_when_not_charging(self):
        soc = _StubSoc(50.0, 100.0)
        ent = ds_energy_time_to_full(soc, qpigs={"battery_charging_current": "0"})
        ent._handle_coordinator_update()
        assert ent._attr_native_value is None


def ds_energy_time_to_full(soc_sensor, qpigs):
    ent = des.DirectBatteryTimeToFullSensor(_Dev(), _Coord({"qpigs": qpigs}), soc_sensor)
    return _neutralise_write(ent)


# ---------------------------------------------------------------------------
# DirectLastSampleSensor — freshness / age of the live telemetry
# ---------------------------------------------------------------------------
class TestLastSampleSensor:
    TS = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def _make(self, **kwargs):
        ent = ds.DirectLastSampleSensor(_Dev(), _Coord({}, **kwargs))
        return _neutralise_write(ent)

    def test_exposes_timestamp_and_age(self):
        ent = self._make(last_success=self.TS, last_success_age=12.3)
        ent._handle_coordinator_update()
        assert ent._attr_native_value == self.TS
        attrs = ent.extra_state_attributes
        assert attrs["age_seconds"] == 12.3
        assert attrs["stale_cycles"] == 0
        assert attrs["stale"] is False

    def test_marks_stale_after_failed_qpigs(self):
        ent = self._make(
            last_success=self.TS,
            last_success_age=95.0,
            failures={"qpigs": 3},
        )
        ent._handle_coordinator_update()
        attrs = ent.extra_state_attributes
        assert attrs["age_seconds"] == 95.0
        assert attrs["stale_cycles"] == 3
        assert attrs["stale"] is True

    def test_no_sample_yet(self):
        ent = self._make()
        ent._handle_coordinator_update()
        assert ent._attr_native_value is None
        attrs = ent.extra_state_attributes
        assert attrs["age_seconds"] is None
        assert attrs["stale"] is False


# ---------------------------------------------------------------------------
# Energy integration guard — no accumulation across stale data or outages
# ---------------------------------------------------------------------------
class TestEnergyIntegrationGuard:
    def _make(self, failures=None, interval=10):
        coord = _Coord(
            {"qpigs": {"pv_charging_power": "1000"}},
            interval=interval,
            failures=failures,
        )
        return _neutralise_write(des.DirectPVEnergySensor(_Dev(), coord))

    def test_accumulates_normal_cycle(self):
        ent = self._make()
        with patch.object(des.time, "monotonic", return_value=1000.0):
            ent._prev_power = 1000.0
            ent._prev_ts = 990.0
            ent.update_energy_value(1000.0)
        assert ent._attr_native_value == pytest.approx(2000.0 * 10.0 / 3600.0)
        assert ent._prev_power == 1000.0

    def test_pauses_when_qpigs_is_stale(self):
        ent = self._make(failures={"qpigs": 1})
        with patch.object(des.time, "monotonic", return_value=1000.0):
            ent._prev_power = 1000.0
            ent._prev_ts = 990.0
            ent.update_energy_value(1000.0)
        assert ent._attr_native_value == 0.0
        assert ent._prev_power is None

    def test_pauses_after_long_gap(self):
        ent = self._make(interval=10)
        with patch.object(des.time, "monotonic", return_value=1000.0):
            ent._prev_power = 1000.0
            ent._prev_ts = 1000.0 - 120.0
            ent.update_energy_value(1000.0)
        assert ent._attr_native_value == 0.0
        assert ent._prev_power is None

    def test_recovery_starts_a_fresh_trapezoid(self):
        ent = self._make(failures={"qpigs": 2})
        with patch.object(des.time, "monotonic", return_value=1000.0):
            ent._prev_power = 1000.0
            ent._prev_ts = 990.0
            ent.update_energy_value(1000.0)
            # Source is healthy again on the next tick.
            ent.coordinator._failures["qpigs"] = 0
            ent.update_energy_value(1000.0)
        # First healthy tick only seeds the integrator; the outage was not
        # bridged by a trapezoid.
        assert ent._attr_native_value == 0.0
        assert ent._prev_power == 1000.0


class TestOfflineChildCrashSafety:
    """Offline hub children have no qpigs/qpiri yet — entity setup and the
    coordinator update fan-out must not crash, otherwise the in-place child
    reconcile aborts and forces a full reload (bouncing the listener)."""

    def test_device_status_survives_missing_qpigs(self):
        ent = _make(ds.DirectDeviceStatusSensor, {})  # device data has no qpigs
        ent._handle_coordinator_update()              # must not raise
        assert ent._attr_native_value == "OK"
        assert ent.extra_state_attributes is not None

    def test_select_resolvers_safe_without_qpiri(self):
        from custom_components.dess_monitor_local import select as sel
        assert sel.resolve_output_priority({}) is None
        assert sel.resolve_chrage_source_priority({}) is None
        assert sel.resolve_max_utility_charging_current({}) is None


# ---------------------------------------------------------------------------
# Utility charging current cap (register 333 is 80 A on the 4.2 kW model)
# ---------------------------------------------------------------------------
class TestUtilityCurrentOptions:
    def test_default_cap_is_80(self):
        from custom_components.dess_monitor_local import select as sel
        options = sel.max_utility_charging_current_options(None)
        assert options[-1] == "80"
        assert "100" not in options
        assert "110" not in options
        assert "120" not in options

    def test_lower_reported_limit_wins(self):
        from custom_components.dess_monitor_local import select as sel
        options = sel.max_utility_charging_current_options(
            {"max_charging_current": "60"}
        )
        assert options[-1] == "60"

    def test_zero_or_garbage_falls_back_to_80(self):
        from custom_components.dess_monitor_local import select as sel
        for value in (0, None, "n/a"):
            options = sel.max_utility_charging_current_options(
                {"max_charging_current": value}
            )
            assert options[-1] == "80"

    def test_entity_caps_options_from_qpiri(self):
        from custom_components.dess_monitor_local import select as sel
        ent = sel.InverterMaxUtilityChargingCurrentNumber(
            _Dev(), _Coord({"qpiri": {"max_charging_current": 50}})
        )
        assert ent.options[-1] == "50"
        assert ent.extra_state_attributes["max_allowed_amps"] == 50


class TestPriorityChoices:
    def test_charge_select_offers_only_solar(self):
        from custom_components.dess_monitor_local import select as sel
        raw = [choice[0] for choice in sel._CHARGE_SOURCE_CHOICES]
        assert "OnlySolar" in raw
        assert raw == ["UtilityFirst", "SolarFirst", "SolarAndUtility", "OnlySolar"]

    def test_output_labels_are_explicit(self):
        from custom_components.dess_monitor_local import select as sel
        ent = sel.InverterOutputPrioritySelect(_Dev(), _Coord({}))
        assert "SBU (battery before grid)" in ent.options
        assert "SUB (grid before battery)" in ent.options
        # French labels follow the HA language.
        ent.hass = type("H", (), {"config": type("C", (), {"language": "fr"})()})()
        assert "SBU (batterie avant réseau)" in ent.options

    def test_raw_alias_keeps_old_solarfirst_readable(self):
        from custom_components.dess_monitor_local import select as sel
        ent = sel.InverterOutputPrioritySelect(
            _Dev(), _Coord({"qpiri": {"output_source_priority": "SolarFirst"}})
        )
        assert ent.extra_state_attributes.get("raw_value") == "Solar"


class TestFaultAdviceSensor:
    def test_pv_low_voltage_gives_actionable_advice(self):
        ent = _make(ds.DirectFaultAdviceSensor, {
            "qfws": {
                "warning_code": 0x40,
                "warning_keys": ["pv_low_voltage"],
                "warn_pv_low_voltage": True,
            },
        })
        ent._handle_coordinator_update()
        assert "night" in ent._attr_native_value
        assert ent._attr_extra_state_attributes["warning_keys"] == ["pv_low_voltage"]

    def test_fault_advice_takes_priority(self):
        ent = _make(ds.DirectFaultAdviceSensor, {
            "qfws": {
                "fault_code": 1 << 2,
                "fault_keys": ["battery_voltage_high"],
                "warning_code": 0x40,
                "warning_keys": ["pv_low_voltage"],
            },
        })
        ent._handle_coordinator_update()
        assert "Stop charging" in ent._attr_native_value

    def test_no_active_condition(self):
        ent = _make(ds.DirectFaultAdviceSensor, {"qpiws": {}, "qfws": {}})
        ent._handle_coordinator_update()
        assert ent._attr_native_value == "No active fault or warning."

    def test_unmapped_code_is_honest(self):
        ent = _make(ds.DirectFaultAdviceSensor, {
            "qfws": {"fault_code": 2},
        })
        ent._handle_coordinator_update()
        assert "No detailed advice" in ent._attr_native_value


class TestSMG2ConfigEntities:
    def test_battery_type_select_reads_register_code(self):
        from custom_components.dess_monitor_local import select as sel

        spec = next(
            item for item in sel._SMG2_SELECT_SPECS
            if item["key"] == "battery_type"
        )
        ent = sel.SMG2ConfigSelect(
            _Dev(), _Coord({"qpiri": {"battery_type_code": 2}}), **spec
        )
        ent.hass = type("H", (), {"config": type("C", (), {"language": "fr"})()})()
        assert ent.current_option == "Utilisateur"
        assert ent.extra_state_attributes["raw_value"] == 2

    def test_output_voltage_select_uses_raw_register_value(self):
        from custom_components.dess_monitor_local import select as sel

        spec = next(
            item for item in sel._SMG2_SELECT_SPECS
            if item["key"] == "output_voltage"
        )
        ent = sel.SMG2ConfigSelect(
            _Dev(), _Coord({"qpiri": {"output_voltage_setting_code": 2300}}), **spec
        )
        assert ent.current_option == "230 V"
        assert ent._raw_for_option("230 V") == 2300

    def test_numeric_setting_reads_scaled_value(self):
        from custom_components.dess_monitor_local import number as num

        spec = next(
            item for item in num._SMG2_NUMBER_SPECS
            if item["key"] == "battery_ovp"
        )
        ent = num.SMG2ConfigNumber(
            _Dev(), _Coord({"qpiri": {"battery_ovp": 29.4}}), **spec
        )
        assert ent.native_value == 29.4
        assert ent._attr_native_max_value == 32.0

    def test_switch_reads_register_bit(self):
        from custom_components.dess_monitor_local import switch as sw

        spec = next(
            item for item in sw._SMG2_SWITCH_SPECS
            if item["key"] == "battery_equalization"
        )
        ent = sw.SMG2ConfigSwitch(
            _Dev(), _Coord({"qpiri": {"battery_eq_enabled": 1}}), **spec
        )
        assert ent.is_on is True
        ent._pending_on = False
        assert ent.is_on is False
