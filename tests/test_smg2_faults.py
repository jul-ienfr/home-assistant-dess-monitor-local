"""Tests for the SMG-II fault/warning decode tables and snapshot projection."""
import asyncio

from custom_components.dess_monitor_local import smg2_faults
from custom_components.dess_monitor_local.api.protocols import modbus_rtu


class TestWarningBits:
    def test_bit_6_is_pv_low_voltage(self):
        # 0x40 is the alert the user saw at night: PV voltage below the
        # start threshold, not a hardware fault.
        keys = smg2_faults.warning_keys(0x40)
        assert keys == ["pv_low_voltage"]
        assert smg2_faults.warning_label(keys[0]) == "PV low voltage"
        assert smg2_faults.warning_label(keys[0], "fr") == "Tension PV trop basse"
        assert "night" in smg2_faults.warning_advice(keys[0])

    def test_multiple_bits_are_sorted(self):
        keys = smg2_faults.warning_keys((1 << 10) | (1 << 6))
        assert keys == ["pv_low_voltage", "overload"]

    def test_zero_and_unknown_bits(self):
        assert smg2_faults.warning_keys(0) == []
        # Bit 2 is not in the published warning map.
        assert smg2_faults.warning_keys(1 << 2) == []

    def test_french_fallback_to_english(self):
        assert smg2_faults.warning_label("pv_low_voltage", "de") == "PV low voltage"
        assert smg2_faults.normalize_language("fr-FR") == "fr"
        assert smg2_faults.normalize_language(None) == "en"


class TestFaultBits:
    def test_known_bit(self):
        assert smg2_faults.fault_keys(1 << 2) == ["battery_voltage_high"]
        label = smg2_faults.fault_label("battery_voltage_high")
        assert label == "Battery over voltage"
        assert smg2_faults.fault_advice("battery_voltage_high")

    def test_combined(self):
        code = (1 << 6) | (1 << 12)
        assert smg2_faults.fault_keys(code) == ["overload", "inverter_over_current"]


class TestSnapshotDecode:
    def _read(self, block_100):
        async def read_block(start, count):
            if start == 100:
                return block_100
            return [0] * count

        return asyncio.run(modbus_rtu.read_smg2_snapshot_via(read_block))

    def test_warning_code_decoded(self):
        block = [0] * 16
        block[8] = 0x0000  # warning DWORD high word
        block[9] = 0x0040  # warning DWORD low word
        _sensors, _config, faults = self._read(block)
        assert faults["warning_code"] == 0x40
        assert faults["warning_keys"] == ["pv_low_voltage"]
        assert faults["warning_description"] == "PV low voltage"
        assert faults["warn_pv_low_voltage"] is True
        assert faults["has_warning"] is True
        assert faults["has_fault"] is False

    def test_no_codes_means_empty_lists(self):
        _sensors, _config, faults = self._read([0] * 16)
        assert faults["fault_keys"] == []
        assert faults["warning_keys"] == []
        assert faults["fault_description"] is None
        assert faults["warning_description"] is None
        assert faults["has_fault"] is False
        assert faults["has_warning"] is False
