"""Tests for update-interval resolution (timing.py).

EyBond dongles reopen their TCP session every few seconds, so the generic
1 s floor produces mostly-empty polls. The helpers below centralize the
transport detection so the coordinator, the config flow and the options
flow all clamp identically.
"""
import pytest

from custom_components.dess_monitor_local import timing
from custom_components.dess_monitor_local.const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    LEGACY_DEFAULT_UPDATE_INTERVAL,
    MAX_UPDATE_INTERVAL,
    MIN_EYBOND_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
)


class TestEybondDetection:
    @pytest.mark.parametrize("kwargs", [
        {"transport": "eybond"},
        {"protocol": "eybond"},
        {"uri": "eybond://192.168.1.5:8899/1?pn=PN1"},
        {"transport": "eybond", "protocol": "voltronic"},
    ])
    def test_eybond_sources(self, kwargs):
        assert timing.is_eybond_transport(**kwargs) is True
        assert timing.min_update_interval(**kwargs) == MIN_EYBOND_UPDATE_INTERVAL

    @pytest.mark.parametrize("kwargs", [
        {},
        {"transport": "tcp_elfin", "protocol": "voltronic"},
        {"uri": "tcp://10.0.0.7:8899"},
        {"uri": "serial:///dev/ttyUSB0"},
        {"uri": None},
    ])
    def test_other_transports(self, kwargs):
        assert timing.is_eybond_transport(**kwargs) is False
        assert timing.min_update_interval(**kwargs) == MIN_UPDATE_INTERVAL


class TestClamp:
    def test_below_minimum_raises_to_floor(self):
        assert timing.clamp_update_interval(0, minimum=5) == 5
        assert timing.clamp_update_interval(-3, minimum=5) == 5

    def test_above_maximum_caps(self):
        assert timing.clamp_update_interval(9_999) == MAX_UPDATE_INTERVAL

    def test_valid_value_passes_through(self):
        assert timing.clamp_update_interval(30) == 30
        assert timing.clamp_update_interval("15") == 15

    @pytest.mark.parametrize("value", [None, "n/a", object()])
    def test_invalid_falls_back_to_default(self, value):
        assert timing.clamp_update_interval(value) == DEFAULT_UPDATE_INTERVAL

    def test_eybond_default_is_raised_to_floor(self):
        # A 1 s stored option (from before the floor existed) must not be
        # scheduled as-is on an EyBond entry.
        assert timing.clamp_update_interval(
            1, minimum=MIN_EYBOND_UPDATE_INTERVAL
        ) == MIN_EYBOND_UPDATE_INTERVAL


class TestMigration:
    def test_default_is_five_seconds(self):
        assert DEFAULT_UPDATE_INTERVAL == 5
        assert MIN_EYBOND_UPDATE_INTERVAL == 5

    def test_eybond_legacy_default_moves_to_five(self):
        options = {CONF_UPDATE_INTERVAL: LEGACY_DEFAULT_UPDATE_INTERVAL}
        migrated = timing.migrate_legacy_update_interval(
            options, is_eybond=True
        )
        assert migrated[CONF_UPDATE_INTERVAL] == 5
        # The input mapping itself is not mutated.
        assert options[CONF_UPDATE_INTERVAL] == LEGACY_DEFAULT_UPDATE_INTERVAL

    @pytest.mark.parametrize("interval", [1, 6, 30])
    def test_other_eybond_values_are_preserved(self, interval):
        options = {CONF_UPDATE_INTERVAL: interval}
        assert timing.migrate_legacy_update_interval(
            options, is_eybond=True
        )[CONF_UPDATE_INTERVAL] == interval

    def test_non_eybond_is_never_rewritten(self):
        options = {CONF_UPDATE_INTERVAL: LEGACY_DEFAULT_UPDATE_INTERVAL}
        migrated = timing.migrate_legacy_update_interval(
            options, is_eybond=False
        )
        assert migrated[CONF_UPDATE_INTERVAL] == LEGACY_DEFAULT_UPDATE_INTERVAL
