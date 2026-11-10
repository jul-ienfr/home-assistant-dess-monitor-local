"""Tests for the writable SMG-II settings metadata and projection."""
import asyncio

from custom_components.dess_monitor_local import smg2_settings
from custom_components.dess_monitor_local.api.protocols import modbus_rtu


class TestUtilityCurrentOptions:
    def test_never_offers_more_than_80_a(self):
        options = smg2_settings.max_utility_charging_current_options(
            {"max_charging_current": "100"}
        )
        assert options[-1] == "80"
        assert "120" not in options
        assert "110" not in options
        assert "100" not in options

    def test_lower_total_limit_wins(self):
        options = smg2_settings.max_utility_charging_current_options(
            {"max_charging_current": "60"}
        )
        assert options[-1] == "60"

    def test_missing_or_garbage_total_uses_hardware_cap(self):
        assert smg2_settings.max_utility_charging_current_options({})[-1] == "80"
        assert smg2_settings.max_utility_charging_current_options(
            {"max_charging_current": "n/a"}
        )[-1] == "80"


class TestTotalChargeCurrentFloor:
    def test_floor_follows_max_mains_current(self):
        assert smg2_settings.min_total_charge_current(
            {"max_utility_charging_current": "80"}
        ) == 80.0
        assert smg2_settings.min_total_charge_current(
            {"max_utility_charging_current": "60.0"}
        ) == 60.0

    def test_floor_is_zero_without_usable_data(self):
        assert smg2_settings.min_total_charge_current({}) == 0.0
        assert smg2_settings.min_total_charge_current(
            {"max_utility_charging_current": "n/a"}
        ) == 0.0
        assert smg2_settings.min_total_charge_current(
            {"max_utility_charging_current": None}
        ) == 0.0


class TestSnapshotConfig:
    def _read(self, block_300, block_400=None):
        async def read_block(start, count):
            if start == 100:
                return [0] * count
            if start == 300:
                return list(block_300)
            if start == 400:
                return list(block_400) if block_400 is not None else [0] * count
            return [0] * count

        return asyncio.run(modbus_rtu.read_smg2_snapshot_via(read_block))

    def test_soc_thresholds_and_remote_controls(self):
        block_300 = [0] * 44
        block_300[22] = 2   # reg 322: battery type User
        block_300[41] = 40  # reg 341: back to utility
        block_300[42] = 80  # reg 342: back to battery
        block_300[43] = 10  # reg 343: low cut-off
        block_400 = [0] * 27
        block_400[6] = 1    # reg 406: turn-on mode
        block_400[20] = 1   # reg 420: remote output

        _sensors, config, _faults = self._read(block_300, block_400)

        assert config["battery_type"] == 2
        assert config["soc_back_to_utility"] == 40
        assert config["soc_back_to_battery"] == 80
        assert config["soc_low_cutoff"] == 10
        assert config["turn_on_mode"] == 1
        assert config["remote_output_enable"] == 1

    def test_projection_exposes_writable_keys(self):
        block_300 = [0] * 44
        block_300[2] = 1    # reg 302: narrow input range
        block_300[3] = 2    # reg 303: warnings + faults
        block_300[20] = 2300  # reg 320: 230 V
        block_300[21] = 5000  # reg 321: 50 Hz
        block_300[22] = 3   # reg 322: Li1
        block_300[23] = 290  # reg 323: 29.0 V
        block_300[24] = 280  # reg 324: 28.0 V
        block_300[25] = 270  # reg 325: 27.0 V
        block_300[26] = 250  # reg 326: 25.0 V
        block_300[27] = 240  # reg 327: 24.0 V
        block_300[29] = 230  # reg 329: 23.0 V
        block_300[32] = 1000  # reg 332: 100.0 A
        block_300[33] = 800   # reg 333: 80.0 A
        block_300[34] = 290   # reg 334: 29.0 V
        block_300[35] = 60    # reg 335: 60 min
        block_300[36] = 120   # reg 336: 120 min
        block_300[37] = 30    # reg 337: 30 d
        block_300[41] = 40
        block_300[42] = 80
        block_300[43] = 10
        block_400 = [0] * 27
        block_400[6] = 1
        block_400[20] = 1

        _sensors, config, _faults = self._read(block_300, block_400)
        qpiri = modbus_rtu.smg2_to_qpiri(config)

        assert qpiri["input_voltage_range_code"] == 1
        assert qpiri["buzzer_mode"] == 2
        assert qpiri["output_voltage_setting_code"] == 2300
        assert qpiri["output_frequency_setting_code"] == 5000
        assert qpiri["battery_type_code"] == 3
        assert qpiri["battery_ovp"] == 29.0
        assert qpiri["max_charge_voltage"] == 28.0
        assert qpiri["float_charge_voltage"] == 27.0
        assert qpiri["battery_discharge_recovery_mains"] == 25.0
        assert qpiri["battery_low_protection_mains"] == 24.0
        assert qpiri["battery_low_protection_offgrid"] == 23.0
        assert qpiri["max_charging_current"] == "100"
        assert qpiri["max_utility_charging_current"] == "80"
        assert qpiri["eq_charging_voltage"] == 29.0
        assert qpiri["eq_time_minutes"] == 60
        assert qpiri["eq_timeout"] == 120
        assert qpiri["eq_interval_days"] == 30
        assert qpiri["soc_back_to_utility"] == 40
        assert qpiri["soc_back_to_battery"] == 80
        assert qpiri["soc_low_cutoff"] == 10
        assert qpiri["turn_on_mode"] == 1
        assert qpiri["remote_output_enable"] == 1
