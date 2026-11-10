"""Binary sensors derived from QPIGS device-status bit fields.

The inverter packs several status flags into two ASCII bit-strings in
QPIGS — ``device_status_bits_b7_b0`` (8 bits) and
``device_status_bits_b10_b8`` (3 bits). The existing
``DirectDeviceStatusSensor`` exposes a coarse single-state summary, but
automations need per-flag triggers ("fault → alarm", "battery_low →
notify", etc.). Each binary_sensor here maps to one specific bit so HA
automations can listen on a clean entity-id.

All entities live on the same coordinator as the rest of the
integration and update on every poll.
"""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.dess_monitor_local import HubConfigEntry
from custom_components.dess_monitor_local.api.commands.direct_commands import (
    parse_device_status_bits_b7_b0,
    parse_device_status_bits_b10_b8,
)
from custom_components.dess_monitor_local.const import (
    CONF_PROTOCOL,
    DOMAIN,
    PROTOCOL_MODBUS,
)
from custom_components.dess_monitor_local.coordinators.direct_coordinator import (
    DirectCoordinator,
)
from custom_components.dess_monitor_local.hub import InverterDevice
from custom_components.dess_monitor_local.smg2_faults import (
    fault_label,
    normalize_language,
    warning_label,
)
from custom_components.dess_monitor_local.smg2_settings import (
    SMG2_MAX_CHARGE_CURRENT,
    SMG2_MAX_UTILITY_CHARGE_CURRENT,
    ui_language,
)


def _ui_language(hass) -> str:
    config = getattr(hass, "config", None)
    return normalize_language(getattr(config, "language", None))

# (status-key, sensor-suffix, human name, device_class). The parser
# normalises bits to True/False, so we just look them up by key.
_B7_B0_FLAGS: tuple[tuple[str, str, str, BinarySensorDeviceClass | None], ...] = (
    ("fault",              "fault",             "Fault",              BinarySensorDeviceClass.PROBLEM),
    ("line_fail",          "line_fail",         "Line Fail",          BinarySensorDeviceClass.PROBLEM),
    ("bus_over",           "bus_over",          "Bus Over",           BinarySensorDeviceClass.PROBLEM),
    ("battery_low",        "battery_low",       "Battery Low",        BinarySensorDeviceClass.BATTERY),
    ("battery_high",       "battery_high",      "Battery High",       BinarySensorDeviceClass.PROBLEM),
    ("inverter_overload",  "inverter_overload", "Inverter Overload",  BinarySensorDeviceClass.PROBLEM),
    ("inverter_on",        "inverter_on",       "Inverter On",        BinarySensorDeviceClass.RUNNING),
)

_B10_B8_FLAGS: tuple[tuple[str, str, str, BinarySensorDeviceClass | None], ...] = (
    ("charging_to_battery", "charging_to_battery", "Charging to Battery", BinarySensorDeviceClass.BATTERY_CHARGING),
    ("charging_ac_active",  "charging_ac_active",  "AC Charging Active",  BinarySensorDeviceClass.RUNNING),
    ("charging_scc_active", "charging_scc_active", "SCC Charging Active", BinarySensorDeviceClass.RUNNING),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HubConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub = config_entry.runtime_data
    coordinator = hub.direct_coordinator
    entry_protocol = config_entry.options.get(CONF_PROTOCOL)

    new_entities: list[BinarySensorEntity] = []
    for item in hub.items:
        item_protocol = getattr(item, "protocol", None) or entry_protocol
        is_modbus = item_protocol == PROTOCOL_MODBUS

        if not is_modbus:
            # QPIGS status bits do not exist on SMG-II; the projection used
            # to invent "00010000"/"010". Don't create entities for data the
            # inverter never sent.
            for key, suffix, name, dc in _B7_B0_FLAGS:
                new_entities.append(
                    _StatusBitBinarySensor(
                        item, coordinator,
                        raw_field="device_status_bits_b7_b0",
                        parser=parse_device_status_bits_b7_b0,
                        flag_key=key,
                        sensor_suffix=suffix,
                        name=name,
                        device_class=dc,
                    )
                )
            for key, suffix, name, dc in _B10_B8_FLAGS:
                new_entities.append(
                    _StatusBitBinarySensor(
                        item, coordinator,
                        raw_field="device_status_bits_b10_b8",
                        parser=parse_device_status_bits_b10_b8,
                        flag_key=key,
                        sensor_suffix=suffix,
                        name=name,
                        device_class=dc,
                    )
                )

        # Aggregate warning sensor works for every protocol: SMG-II feeds
        # fault_code/warning_code through the QPIWS/QFWS projections.
        new_entities.append(_AnyWarningBinarySensor(item, coordinator))

        if is_modbus:
            new_entities.append(
                SMG2ConfigurationCoherenceSensor(item, coordinator)
            )

        if not is_modbus:
            # The per-bit QPIWS/QFWS flags are not decoded for SMG-II (the
            # published map only defines raw 32-bit codes), so those
            # entities would stay unknown forever.
            for key, suffix, name, dc in _QPIWS_WARNINGS:
                new_entities.append(
                    _WarningFlagBinarySensor(
                        item, coordinator,
                        flag_key=key, sensor_suffix=suffix,
                        name=name, device_class=dc,
                    )
                )

    if new_entities:
        async_add_entities(new_entities)


# Subset of QPIWS / QFWS bits surfaced as dedicated binary_sensors —
# the actionable ones for typical residential automations. Everything
# else lives on the fault-summary sensor as attributes.
_QPIWS_WARNINGS: tuple[tuple[str, str, str, BinarySensorDeviceClass | None], ...] = (
    ("inverter_fault",         "inverter_fault",         "Inverter Fault",      BinarySensorDeviceClass.PROBLEM),
    ("overload",               "overload",               "Overload",            BinarySensorDeviceClass.PROBLEM),
    ("over_temperature",       "over_temperature",       "Over Temperature",    BinarySensorDeviceClass.PROBLEM),
    ("fan_locked",             "fan_locked",             "Fan Locked",          BinarySensorDeviceClass.PROBLEM),
    ("battery_under_shutdown", "battery_under_shutdown", "Battery Shutdown",    BinarySensorDeviceClass.PROBLEM),
    ("eeprom_fault",           "eeprom_fault",           "EEPROM Fault",        BinarySensorDeviceClass.PROBLEM),
)


class _StatusBitBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """One bit of the QPIGS status field, exposed as binary_sensor.

    The bit-string parser is invoked on each tick rather than caching
    because the same parser feeds the legacy ``DirectDeviceStatusSensor``
    diagnostic — keeping a single decode point avoids divergence if the
    parser semantics ever change.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        inverter_device: InverterDevice,
        coordinator: DirectCoordinator,
        *,
        raw_field: str,
        parser,
        flag_key: str,
        sensor_suffix: str,
        name: str,
        device_class: BinarySensorDeviceClass | None,
    ):
        super().__init__(coordinator)
        self._inverter_device = inverter_device
        self._raw_field = raw_field
        self._parser = parser
        self._flag_key = flag_key
        self._attr_unique_id = (
            f"{inverter_device.inverter_id}_direct_{sensor_suffix}"
        )
        self._attr_translation_key = f"direct_status_{sensor_suffix}"
        if device_class is not None:
            self._attr_device_class = device_class

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._inverter_device.inverter_id)},
            "name": self._inverter_device.name,
            "sw_version": self._inverter_device.firmware_version,
            "model": self._inverter_device.inverter_id,
            "manufacturer": "ESS",
        }

    @property
    def available(self) -> bool:
        return (
            self.coordinator.data is not None
            and self._inverter_device.inverter_id in self.coordinator.data
        )

    @property
    def _qpigs(self) -> dict:
        try:
            return self.coordinator.data[self._inverter_device.inverter_id].get("qpigs", {})
        except (KeyError, TypeError):
            return {}

    @callback
    def _handle_coordinator_update(self) -> None:
        raw = self._qpigs.get(self._raw_field)
        if raw is None or raw == "":
            self._attr_is_on = None
        else:
            try:
                parsed = self._parser(raw)
                value = parsed.get(self._flag_key)
                self._attr_is_on = bool(value) if value is not None else None
            except Exception:
                self._attr_is_on = None
        self.async_write_ha_state()


class _WarningFlagBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """One bit from QPIWS (PI30) or QFWS (PI18). Reads from whichever
    section is populated — both are checked, the warning is ON if either
    reports it."""

    _attr_has_entity_name = True

    def __init__(
        self,
        inverter_device: InverterDevice,
        coordinator: DirectCoordinator,
        *,
        flag_key: str,
        sensor_suffix: str,
        name: str,
        device_class: BinarySensorDeviceClass | None,
    ):
        super().__init__(coordinator)
        self._inverter_device = inverter_device
        self._flag_key = flag_key
        self._attr_unique_id = (
            f"{inverter_device.inverter_id}_direct_warning_{sensor_suffix}"
        )
        self._attr_translation_key = f"direct_warning_{sensor_suffix}"
        if device_class is not None:
            self._attr_device_class = device_class

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._inverter_device.inverter_id)},
            "name": self._inverter_device.name,
            "sw_version": self._inverter_device.firmware_version,
            "model": self._inverter_device.inverter_id,
            "manufacturer": "ESS",
        }

    @property
    def available(self) -> bool:
        return (
            self.coordinator.data is not None
            and self._inverter_device.inverter_id in self.coordinator.data
        )

    @property
    def _flags(self) -> dict:
        try:
            dev = self.coordinator.data[self._inverter_device.inverter_id]
        except (KeyError, TypeError):
            return {}
        # PI30 lives in qpiws; PI18 in qfws. Merge so a single flag_key
        # lookup works for either protocol.
        merged = dict(dev.get("qpiws", {}) or {})
        for k, v in (dev.get("qfws", {}) or {}).items():
            merged.setdefault(k, v)
        return merged

    @callback
    def _handle_coordinator_update(self) -> None:
        # Accept either naming convention: bare (PI30 QPIWS) or
        # warn_-prefixed (PI18 QFWS + agent postgen). Whichever is
        # populated wins. None only if neither is present at all.
        bare = self._flags.get(self._flag_key)
        prefixed = self._flags.get(f"warn_{self._flag_key}")
        if bare is not None or prefixed is not None:
            self._attr_is_on = bool(bare) or bool(prefixed)
        else:
            self._attr_is_on = None
        self.async_write_ha_state()


class _AnyWarningBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Aggregate: True iff *any* known QPIWS / QFWS bit is set. Useful
    as a single automation trigger for "the inverter has something to
    say". For the specific issue, read the fault summary sensor or one
    of the per-flag binary_sensors."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert"
    _attr_has_entity_name = True
    _attr_translation_key = "direct_any_warning"

    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(coordinator)
        self._inverter_device = inverter_device
        self._attr_unique_id = (
            f"{inverter_device.inverter_id}_direct_any_warning"
        )

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._inverter_device.inverter_id)},
            "name": self._inverter_device.name,
            "sw_version": self._inverter_device.firmware_version,
            "model": self._inverter_device.inverter_id,
            "manufacturer": "ESS",
        }

    @property
    def available(self) -> bool:
        return (
            self.coordinator.data is not None
            and self._inverter_device.inverter_id in self.coordinator.data
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        try:
            dev = self.coordinator.data[self._inverter_device.inverter_id]
        except (KeyError, TypeError):
            self._attr_is_on = None
            self._attr_extra_state_attributes = {}
            self.async_write_ha_state()
            return

        qpiws = dev.get("qpiws", {}) or {}
        qfws = dev.get("qfws", {}) or {}
        language = _ui_language(getattr(self, "hass", None))

        # SMG-II/Modbus exposes decoded stable keys; translate them for
        # the user while keeping the machine-readable keys in attributes.
        active_faults = list(qfws.get("fault_keys") or [])
        active_warnings = list(qfws.get("warning_keys") or [])
        attrs: dict = {}
        if active_faults:
            attrs["active_faults"] = [
                fault_label(key, language) for key in active_faults
            ]
            attrs["fault_keys"] = active_faults
        if active_warnings:
            attrs["active_warnings"] = [
                warning_label(key, language) for key in active_warnings
            ]
            attrs["warning_keys"] = active_warnings
        self._attr_extra_state_attributes = attrs

        # PI18 / SMG-II explicit fault_code or warning_code wins immediately.
        fault_code = qfws.get("fault_code")
        warning_code = qfws.get("warning_code")
        if (
            (isinstance(fault_code, (int, float)) and fault_code != 0)
            or (isinstance(warning_code, (int, float)) and warning_code != 0)
            or bool(qfws.get("has_fault"))
            or bool(qfws.get("has_warning"))
        ):
            self._attr_is_on = True
            self.async_write_ha_state()
            return

        any_set = any(
            bool(v) for k, v in qpiws.items()
            if isinstance(v, bool) and not k.startswith("_reserved_")
        ) or any(
            bool(v) for k, v in qfws.items()
            if isinstance(v, bool) and k.startswith("warn_")
        )
        self._attr_is_on = any_set
        self.async_write_ha_state()


_PROBLEM_TEXT = {
    "battery_voltage_order": {
        "en": (
            "Battery thresholds must satisfy OVP > bulk > float > "
            "recovery > low cut-off."
        ),
        "fr": (
            "Les seuils batterie doivent respecter OVP > bulk > float > "
            "reprise > coupure basse."
        ),
    },
    "soc_order": {
        "en": (
            "SOC thresholds must satisfy low cut-off < back to utility "
            "< back to battery."
        ),
        "fr": (
            "Les seuils SOC doivent respecter coupure basse < retour réseau "
            "< retour batterie."
        ),
    },
    "soc_back_to_battery_min": {
        "en": "Back-to-battery SOC must be at least 60 %.",
        "fr": "Le SOC de retour batterie doit être au moins 60 %.",
    },
    "max_charge_current": {
        "en": "Max charging current exceeds 100 A.",
        "fr": "Le courant de charge max dépasse 100 A.",
    },
    "max_utility_current": {
        "en": "Max mains charging current exceeds 80 A.",
        "fr": "Le courant de charge secteur max dépasse 80 A.",
    },
}


class SMG2ConfigurationCoherenceSensor(CoordinatorEntity, BinarySensorEntity):
    """Diagnostic: are the interdependent SMG-II thresholds consistent?

    The individual number entities enforce their own min/max, but they
    cannot prevent a physically incoherent combination such as OVP 28 V
    with a 30 V bulk target. This sensor mirrors the ESPHome interlock and
    lists every violated rule in ``violations``.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "smg2_configuration_incoherent"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clipboard-check-outline"

    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(coordinator)
        self._inverter_device = inverter_device
        self._attr_unique_id = (
            f"{inverter_device.inverter_id}_smg2_configuration_incoherent"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, inverter_device.inverter_id)},
            name=inverter_device.name,
            manufacturer="ESS",
            model=inverter_device.inverter_id,
            sw_version=inverter_device.firmware_version,
        )

    def _qpiri(self) -> dict:
        return (self.coordinator.data or {}).get(
            self._inverter_device.inverter_id, {}
        ).get("qpiri") or {}

    @staticmethod
    def _number(qpiri: dict, key: str) -> float | None:
        try:
            value = float(qpiri.get(key))
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    def _evaluate(self) -> tuple[bool | None, dict]:
        qpiri = self._qpiri()
        ovp = self._number(qpiri, "battery_ovp")
        bulk = self._number(qpiri, "max_charge_voltage")
        float_v = self._number(qpiri, "float_charge_voltage")
        recovery = self._number(qpiri, "battery_discharge_recovery_mains")
        cutoff = self._number(qpiri, "battery_low_protection_mains")
        soc_cut = self._number(qpiri, "soc_low_cutoff")
        soc_util = self._number(qpiri, "soc_back_to_utility")
        soc_batt = self._number(qpiri, "soc_back_to_battery")
        max_charge = self._number(qpiri, "max_charging_current")
        max_mains = self._number(qpiri, "max_utility_charging_current")

        required = (ovp, bulk, float_v, recovery, cutoff, soc_cut, soc_util, soc_batt)
        if any(value is None for value in required):
            return None, {}

        violations: list[str] = []
        if not (ovp > bulk > float_v > recovery > cutoff):
            violations.append("battery_voltage_order")
        if not (soc_cut < soc_util < soc_batt):
            violations.append("soc_order")
        if soc_batt < 60:
            violations.append("soc_back_to_battery_min")
        if max_charge is not None and max_charge > SMG2_MAX_CHARGE_CURRENT:
            violations.append("max_charge_current")
        if max_mains is not None and max_mains > SMG2_MAX_UTILITY_CHARGE_CURRENT:
            violations.append("max_utility_current")

        language = ui_language(getattr(self, "hass", None))
        attrs = {
            "violations": violations,
            "battery_voltage_order": (
                "ovp>bulk>float>recovery>cutoff"
                if "battery_voltage_order" not in violations
                else "violated"
            ),
            "soc_order": (
                "cutoff<utility<battery"
                if "soc_order" not in violations
                else "violated"
            ),
        }
        if violations:
            attrs["problem"] = " ".join(
                _PROBLEM_TEXT[key][language] for key in violations
            )
        return bool(violations), attrs

    @property
    def is_on(self) -> bool | None:
        return self._evaluate()[0]

    @property
    def extra_state_attributes(self) -> dict:
        return self._evaluate()[1]
