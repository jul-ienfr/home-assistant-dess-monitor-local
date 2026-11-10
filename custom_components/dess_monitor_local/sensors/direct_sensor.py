import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import (
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.dess_monitor_local import DirectCoordinator
from custom_components.dess_monitor_local.api.commands.direct_commands import (
    ACInputVoltageRange,
    BatteryType,
    ChargerSourcePriority,
    DeviceStatusBitsB7B0,
    OperatingMode,
    OutputSourcePriority,
    ParallelMode,
    parse_device_status_bits_b7_b0,
)
from custom_components.dess_monitor_local.api.decoders.enums import (
    # PI18 direction/status enums come straight from their real home
    # rather than being re-exported through direct_commands (a re-export
    # there reads as an unused import and gets stripped by linters).
    PI18BatteryPowerDirection,
    PI18DCACPowerDirection,
    PI18LinePowerDirection,
    PI18MPPTStatus,
    parallel_mode_name,
)
from custom_components.dess_monitor_local.const import DOMAIN
from custom_components.dess_monitor_local.hub import InverterDevice
from custom_components.dess_monitor_local.sanity import (
    is_plausible_battery_current,
    is_plausible_battery_voltage,
    is_plausible_power,
)
from custom_components.dess_monitor_local.smg2_faults import (
    FAULT_ADVICE,
    WARNING_ADVICE,
    WARNING_BY_KEY,
    fault_label,
    normalize_language,
    warning_label,
)

_LOGGER = logging.getLogger(__name__)


class DirectSensorBase(CoordinatorEntity, SensorEntity):

    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._inverter_device = inverter_device

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._inverter_device.inverter_id)},
            "name": self._inverter_device.name,
            "sw_version": self._inverter_device.firmware_version,
            "model": self._inverter_device.inverter_id,
            "manufacturer": 'ESS'
        }

    @property
    def available(self) -> bool:
        """Return True if the coordinator has fetched data for this inverter.

        Without this check the ``data`` property below dereferences
        ``coordinator.data[id]`` on every state update; if the very first
        poll fails (or HA restarts and we haven't completed a poll yet),
        that raises TypeError/KeyError and corrupts the entity update
        fan-out for every sibling entity on the same coordinator.
        """
        return (
            self.coordinator.data is not None
            and self._inverter_device.inverter_id in self.coordinator.data
        )

    @property
    def data(self):
        return self.coordinator.data[self._inverter_device.inverter_id]


class DirectTypedSensorBase(DirectSensorBase):
    """Абстрактный базовый класс для сенсоров, получающих значение по ключу."""

    _attr_has_entity_name = True

    def __init__(
            self,
            inverter_device: InverterDevice,
            coordinator: DirectCoordinator,
            data_section: str,
            data_key: str,
            sensor_suffix: str = "",
            name_suffix: str = ""
    ):
        super().__init__(inverter_device, coordinator)
        self.data_section = data_section
        self.data_key = data_key

        suffix = sensor_suffix or data_key

        # Names live in translations/<lang>.json (entity.sensor.direct_*)
        # so the whole entity list follows the Home Assistant UI language.
        # Do not set ``_attr_name``: HA gives it precedence over the
        # translation key when the attribute exists.
        self._attr_unique_id = f"{self._inverter_device.inverter_id}_direct_{suffix}"
        self._attr_translation_key = f"direct_{suffix}"

    @property
    def extra_state_attributes(self):
        """Expose whether this section is currently frozen on stale data.

        ``getattr`` rather than a direct ``_attr_extra_state_attributes``
        access is deliberate: many entities never define it, and raising
        here makes Home Assistant mark the whole entity unavailable (the
        K3rn3l fork hit this on 58 of 91 entities).
        """
        attrs = dict(getattr(self, "_attr_extra_state_attributes", None) or {})
        coordinator = getattr(self, "coordinator", None)
        device = getattr(self, "_inverter_device", None)
        section = getattr(self, "data_section", None)
        if (
            coordinator is not None
            and device is not None
            and section
            and hasattr(coordinator, "section_failures")
        ):
            stale = coordinator.section_failures(device.inverter_id, section)
            attrs["stale_cycles"] = stale
            attrs["stale"] = stale > 0
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        section = self.data.get(self.data_section, {})
        raw_value = section.get(self.data_key)
        if raw_value is not None:
            try:
                self._attr_native_value = float(raw_value)
            except (ValueError, TypeError):
                self._attr_native_value = None
        else:
            self._attr_native_value = None
        self.async_write_ha_state()


# All numeric base classes below get ``state_class = MEASUREMENT``.
# This enables HA's long-term statistics: a row is written every 5 minutes
# regardless of state-change frequency. Without it, sensors that pin at a
# steady value (battery full → power 0 W for hours; load idle → current 0 A;
# temperature steady) stop emitting ``state_changed`` events, so the History
# card / Apex / mini-graph render a frozen line at the moment of the last
# change. With MEASUREMENT, the graph extends to ``now`` even when the
# underlying value hasn't moved.


class DirectWattSensorBase(DirectTypedSensorBase):
    device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unit_of_measurement = UnitOfPower.WATT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_suggested_display_precision = 0
    _sensor_option_display_precision = 0


class DirectTemperatureSensorBase(DirectTypedSensorBase):
    device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 0
    _sensor_option_display_precision = 0


class DirectVoltageSensorBase(DirectTypedSensorBase):
    device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_suggested_display_precision = 1
    _sensor_option_display_precision = 1


class DirectCurrentSensorBase(DirectTypedSensorBase):
    """Базовый сенсор силы тока (A) для direct-протокола."""

    device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_suggested_display_precision = 0
    _sensor_option_display_precision = 0


class DirectApparentPowerSensorBase(DirectTypedSensorBase):
    device_class = SensorDeviceClass.APPARENT_POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unit_of_measurement = UnitOfApparentPower.VOLT_AMPERE
    _attr_native_unit_of_measurement = UnitOfApparentPower.VOLT_AMPERE
    _attr_suggested_display_precision = 0
    _sensor_option_display_precision = 0


class DirectBatteryCapacitySensorBase(DirectTypedSensorBase):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unit_of_measurement = "Ah"
    _attr_native_unit_of_measurement = "Ah"
    _attr_suggested_display_precision = 0
    _sensor_option_display_precision = 0


class DirectFrequencySensorBase(DirectTypedSensorBase):
    device_class = SensorDeviceClass.FREQUENCY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unit_of_measurement = UnitOfFrequency.HERTZ
    _attr_native_unit_of_measurement = UnitOfFrequency.HERTZ
    _attr_suggested_display_precision = 1
    _sensor_option_display_precision = 1


class DirectEnumSensorBase(DirectTypedSensorBase):
    """Базовый класс для сенсоров с перечислимым значением (ENUM)."""

    enum_class = None  # Подкласс обязан переопределить
    device_class = SensorDeviceClass.ENUM
    _attr_device_class = SensorDeviceClass.ENUM

    @property
    def options(self) -> list[str]:
        return [e.name for e in self.enum_class] if self.enum_class else []

    @callback
    def _handle_coordinator_update(self) -> None:
        section = self.data.get(self.data_section, {})
        raw_value = section.get(self.data_key)

        if raw_value in self.options:
            self._attr_native_value = raw_value
        else:
            self._attr_native_value = None

        self.async_write_ha_state()


class BatteryTypeSensor(DirectEnumSensorBase):
    enum_class = BatteryType


class ACInputVoltageRangeSensor(DirectEnumSensorBase):
    enum_class = ACInputVoltageRange


class OutputSourcePrioritySensor(DirectEnumSensorBase):
    enum_class = OutputSourcePriority


class ChargerSourcePrioritySensor(DirectEnumSensorBase):
    enum_class = ChargerSourcePriority


class ParallelModeSensor(DirectEnumSensorBase):
    enum_class = ParallelMode

    @callback
    def _handle_coordinator_update(self) -> None:
        # The PI30 decoder already emits names; transports that pass QPIRI
        # through verbatim (agent) may still carry the raw output-mode code.
        section = self.data.get(self.data_section, {})
        raw_value = section.get(self.data_key)
        name = parallel_mode_name(raw_value) if raw_value is not None else None
        self._attr_native_value = name if name in self.options else None
        self.async_write_ha_state()


class DirectPVPowerSensor(DirectWattSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device,
            coordinator,
            data_section="qpigs",
            data_key="pv_charging_power",
            sensor_suffix="pv_power",
            name_suffix="PV Power"
        )

class DirectACGridInPowerSensor(DirectWattSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device,
            coordinator,
            data_section="qpigs",
            data_key="grid_ac_in_power",
            sensor_suffix="grid_ac_in_power",
            name_suffix="Grid AC In Power"
        )


class DirectPV2PowerSensor(DirectWattSensorBase):  # можно и от DirectSensorBase, если не нужен unit/class
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device,
            coordinator,
            data_section="unused",  # не используется, можно передать любой
            data_key="unused",
            sensor_suffix="pv2_power",
            name_suffix="PV2 Power"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        try:
            qpigs2 = self.data["qpigs2"]
            self._attr_native_value = float(qpigs2["pv_current"]) * float(qpigs2["pv_voltage"])
        except (KeyError, ValueError, TypeError):
            self._attr_native_value = None

        self.async_write_ha_state()


class DirectPVVoltageSensor(DirectVoltageSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device,
            coordinator,
            data_section="qpigs",
            data_key="pv_input_voltage",
            sensor_suffix="pv_voltage",
            name_suffix="PV Voltage"
        )


class DirectPV2VoltageSensor(DirectVoltageSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device,
            coordinator,
            data_section="qpigs2",
            data_key="pv_voltage",
            sensor_suffix="pv2_voltage",
            name_suffix="PV2 Voltage"
        )


class DirectPV2CurrentSensor(DirectCurrentSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device,
            coordinator,
            data_section="qpigs2",
            data_key="pv_current",
            sensor_suffix="pv2_current",
            name_suffix="PV2 Current"
        )


class DirectBatteryVoltageSensor(DirectVoltageSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device,
            coordinator,
            data_section="qpigs",
            data_key="battery_voltage",
            sensor_suffix="battery",
            name_suffix="Battery Voltage"
        )


class DirectInverterOutputPowerSensor(DirectWattSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device,
            coordinator,
            data_section="qpigs",
            data_key="output_active_power",
            sensor_suffix="inverter_out_power",
            name_suffix="Inverter Out Power"
        )


class DirectInverterTemperatureSensor(DirectTemperatureSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device,
            coordinator,
            data_section="qpigs",
            data_key="inverter_heat_sink_temperature",
            sensor_suffix="inverter_temperature",
            name_suffix="Inverter Temperature"
        )

class DirectInverterDCModuleTemperatureSensor(DirectTemperatureSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device,
            coordinator,
            data_section="qpigs",
            data_key="inverter_dcdc_module_temperature",
            sensor_suffix="inverter_dc_dc_temperature",
            name_suffix="Inverter DC-DC Module Temperature"
        )


class DirectGridVoltageSensor(DirectVoltageSensorBase):
    def __init__(self, inverter_device, coordinator):
        super().__init__(inverter_device, coordinator, "qpigs", "grid_voltage", "grid_voltage", "Grid Voltage")


class DirectGridFrequencySensor(DirectTypedSensorBase):
    device_class = SensorDeviceClass.FREQUENCY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unit_of_measurement = "Hz"
    _attr_native_unit_of_measurement = "Hz"
    _attr_suggested_display_precision = 1
    _sensor_option_display_precision = 1

    def __init__(self, inverter_device, coordinator):
        super().__init__(inverter_device, coordinator, "qpigs", "grid_frequency", "grid_freq", "Grid Frequency")


class DirectACOutputVoltageSensor(DirectVoltageSensorBase):
    def __init__(self, inverter_device, coordinator):
        super().__init__(inverter_device, coordinator, "qpigs", "ac_output_voltage", "ac_output_voltage",
                         "AC Output Voltage")


class DirectACOutputFrequencySensor(DirectTypedSensorBase):
    device_class = SensorDeviceClass.FREQUENCY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unit_of_measurement = "Hz"
    _attr_native_unit_of_measurement = "Hz"
    _attr_suggested_display_precision = 1
    _sensor_option_display_precision = 1

    def __init__(self, inverter_device, coordinator):
        super().__init__(inverter_device, coordinator, "qpigs", "ac_output_frequency", "ac_output_freq",
                         "AC Output Frequency")


class DirectOutputApparentPowerSensor(DirectApparentPowerSensorBase):
    def __init__(self, inverter_device, coordinator):
        super().__init__(inverter_device, coordinator, "qpigs", "output_apparent_power", "output_apparent_power",
                         "Apparent Power")


class DirectLoadPercentSensor(DirectTypedSensorBase):
    # A percentage is not a power factor. POWER_FACTOR made HA render the
    # value with the wrong semantics (and reject the "%" unit on some
    # versions); leave the device class unset.
    device_class = None
    _attr_device_class = None
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unit_of_measurement = "%"
    _attr_native_unit_of_measurement = "%"
    _attr_suggested_display_precision = 0
    _sensor_option_display_precision = 0

    def __init__(self, inverter_device, coordinator):
        super().__init__(inverter_device, coordinator, "qpigs", "load_percent", "load_percent", "Load Percent")


class DirectBusVoltageSensor(DirectVoltageSensorBase):
    def __init__(self, inverter_device, coordinator):
        super().__init__(inverter_device, coordinator, "qpigs", "bus_voltage", "bus_voltage", "Bus Voltage")


class DirectBatteryChargingCurrentSensor(DirectCurrentSensorBase):
    def __init__(self, inverter_device, coordinator):
        super().__init__(inverter_device, coordinator, "qpigs", "battery_charging_current", "battery_charging_current",
                         "Battery Charging Current")


class DirectBatteryDischargeCurrentSensor(DirectCurrentSensorBase):
    def __init__(self, inverter_device, coordinator):
        super().__init__(inverter_device, coordinator, "qpigs", "battery_discharge_current",
                         "battery_discharge_current", "Battery Discharge Current")

class DirectBatteryPowerSensor(DirectWattSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device,
            coordinator,
            data_section="qpigs",
            data_key="_battery_power",
            sensor_suffix="battery_power",
            name_suffix="Battery Power"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        qpigs = self.data.get('qpigs', {})
        if not qpigs:
            self._attr_native_value = None
            self.async_write_ha_state()
            return
        # SMG-II reports the signed battery power directly (register 217,
        # positive = charging). Prefer it over re-deriving from the two
        # integer-truncated current fields.
        raw_power = qpigs.get('battery_power')
        if raw_power is not None:
            try:
                value = float(raw_power)
            except (TypeError, ValueError):
                value = None
            self._attr_native_value = (
                value if value is not None and is_plausible_power(value) else None
            )
            self.async_write_ha_state()
            return
        try:
            battery_charging_current = float(qpigs.get('battery_charging_current', 0))
            battery_discharge_current = float(qpigs.get('battery_discharge_current', 0))
            battery_voltage = float(qpigs.get('battery_voltage', 0))
        except (TypeError, ValueError):
            self._attr_native_value = None
            self.async_write_ha_state()
            return

        # All-zeros == "no data" (bridge offline, empty payload, missing keys
        # falling back to default 0). Silently skip — not a parser anomaly.
        if (
            battery_charging_current == 0.0
            and battery_discharge_current == 0.0
            and battery_voltage == 0.0
        ):
            self._attr_native_value = None
            self.async_write_ha_state()
            return

        if (
            not is_plausible_battery_current(battery_charging_current)
            or not is_plausible_battery_current(battery_discharge_current)
            or not is_plausible_battery_voltage(battery_voltage)
        ):
            _LOGGER.debug(
                "%s: implausible reading "
                "(I_chg=%.2f A, I_dis=%.2f A, V=%.2f V); dropping sample",
                self.entity_id or self._attr_unique_id,
                battery_charging_current,
                battery_discharge_current,
                battery_voltage,
            )
            self._attr_native_value = None
            self.async_write_ha_state()
            return

        raw_value = (battery_charging_current - battery_discharge_current) * battery_voltage

        if is_plausible_power(raw_value):
            self._attr_native_value = float(raw_value)
        else:
            self._attr_native_value = None

        self.async_write_ha_state()


class DirectBatteryCapacitySensor(DirectTypedSensorBase):
    # Inverter-reported SoC% (BMS-sourced on Li-CAN setups, internal
    # estimate on lead-acid). Treat as a continuous measurement so the
    # History card extends the line when the battery is pegged at 100/0.
    device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_unit_of_measurement = "%"
    _attr_native_unit_of_measurement = "%"
    _attr_suggested_display_precision = 0
    _sensor_option_display_precision = 0

    def __init__(self, inverter_device, coordinator):
        super().__init__(inverter_device, coordinator, "qpigs", "battery_capacity", "battery_capacity",
                         "Battery Capacity")


class DirectPVInputCurrentSensor(DirectCurrentSensorBase):
    def __init__(self, inverter_device, coordinator):
        super().__init__(inverter_device, coordinator, "qpigs", "pv_input_current", "pv_input_current",
                         "PV Input Current")


class DirectSCCBatteryVoltageSensor(DirectVoltageSensorBase):
    def __init__(self, inverter_device, coordinator):
        super().__init__(inverter_device, coordinator, "qpigs", "scc_battery_voltage", "scc_batt_voltage",
                         "SCC Battery Voltage")


class DirectDiagnosticSensorBase(DirectTypedSensorBase):
    _attr_entity_category = EntityCategory.DIAGNOSTIC


QPIRI_SENSOR_MAPPING = {
    "rated_grid_voltage": (DirectVoltageSensorBase, "Rated Grid Voltage"),
    "rated_input_current": (DirectCurrentSensorBase, "Rated Input Current"),
    "rated_ac_output_voltage": (DirectVoltageSensorBase, "Rated AC Output Voltage"),
    "rated_output_frequency": (DirectFrequencySensorBase, "Rated Output Frequency"),
    "rated_output_current": (DirectCurrentSensorBase, "Rated Output Current"),
    "rated_output_apparent_power": (DirectApparentPowerSensorBase, "Rated Output Apparent Power"),
    "rated_output_active_power": (DirectWattSensorBase, "Rated Output Active Power"),
    "rated_battery_voltage": (DirectVoltageSensorBase, "Rated Battery Voltage"),
    "low_battery_to_ac_bypass_voltage": (DirectVoltageSensorBase, "Low Battery to AC Bypass Voltage"),
    "shut_down_battery_voltage": (DirectVoltageSensorBase, "Shut Down Battery Voltage"),
    "bulk_charging_voltage": (DirectVoltageSensorBase, "Bulk Charging Voltage"),
    "float_charging_voltage": (DirectVoltageSensorBase, "Float Charging Voltage"),
    "battery_type": (BatteryTypeSensor, "Battery Type"),
    "max_utility_charging_current": (DirectCurrentSensorBase, "Max Utility Charging Current"),
    "max_charging_current": (DirectCurrentSensorBase, "Max Charging Current"),
    "ac_input_voltage_range": (ACInputVoltageRangeSensor, "AC Input Voltage Range"),
    "output_source_priority": (OutputSourcePrioritySensor, "Output Source Priority"),
    "charger_source_priority": (ChargerSourcePrioritySensor, "Charger Source Priority"),
    "parallel_max_number": (DirectDiagnosticSensorBase, "Parallel Max Number"),
    "reserved_uu": (DirectDiagnosticSensorBase, "Reserved UU"),
    "reserved_v": (DirectDiagnosticSensorBase, "Reserved V"),
    "parallel_mode": (ParallelModeSensor, "Parallel Mode"),
    "high_battery_voltage_to_battery_mode": (DirectVoltageSensorBase, "High Battery Voltage to Battery Mode"),
    "solar_work_condition_in_parallel": (DirectDiagnosticSensorBase, "Solar Work Condition In Parallel"),
    "solar_max_charging_power_auto_adjust": (DirectDiagnosticSensorBase, "Solar Max Charging Power Auto Adjust"),
    "rated_battery_capacity": (DirectBatteryCapacitySensorBase, "Rated Battery Capacity"),
    "reserved_b": (DirectDiagnosticSensorBase, "Reserved B"),
    "reserved_ccc": (DirectDiagnosticSensorBase, "Reserved CCC")
}


# QPIRI keys the SMG-II Modbus map does not provide. The projection fills
# them with constants (4000 W, "UserDefined", 24 V, ...) to keep the
# Voltronic-shaped dict complete, but exposing those constants as sensors
# is misleading. Modbus deployments skip these entities entirely.
MODBUS_UNSUPPORTED_QPIRI_KEYS = frozenset({
    "rated_grid_voltage",
    "rated_input_current",
    "rated_ac_output_voltage",
    "rated_output_frequency",
    "rated_output_current",
    "rated_output_apparent_power",
    "rated_output_active_power",
    "rated_battery_voltage",
    "battery_type",
    "parallel_max_number",
    "reserved_uu",
    "reserved_v",
    "parallel_mode",
    "solar_work_condition_in_parallel",
    "solar_max_charging_power_auto_adjust",
    "rated_battery_capacity",
    "reserved_b",
    "reserved_ccc",
})


def generate_qpiri_sensors(inverter_device, coordinator, *, skip_keys=()):
    """Create QPIRI-backed sensors, optionally omitting fabricated fields.

    ``skip_keys`` lets protocol paths (SMG-II/Modbus) hide keys the
    inverter never reports instead of exposing constants as if they were
    measurements.
    """
    return [
        sensor_class(
            inverter_device=inverter_device,
            coordinator=coordinator,
            data_section="qpiri",
            data_key=data_key,
            name_suffix=name_suffix,
        )
        for data_key, (sensor_class, name_suffix) in QPIRI_SENSOR_MAPPING.items()
        if data_key not in skip_keys
    ]


class DirectDeviceStatusSensor(DirectSensorBase):
    """Главный сенсор с битами как атрибутами."""
    _attr_has_entity_name = True
    _attr_translation_key = "direct_device_status"
    _attr_icon = "mdi:information-outline"

    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        """Initialize the sensor."""
        super().__init__(inverter_device, coordinator)
        self._attr_unique_id = f"{self._inverter_device.inverter_id}_direct_device_status"
        # self._inverter_device = inverter_device

    @callback
    def _handle_coordinator_update(self) -> None:
        # ``.get`` (not ``[]``) so an offline child without a qpigs section
        # doesn't raise KeyError across the coordinator update fan-out — which
        # otherwise aborted the in-place reconcile and forced a full reload.
        qpigs = self.data.get("qpigs", {})
        flags = int(qpigs.get("device_status_bits_b7_b0", 0))
        if flags & DeviceStatusBitsB7B0.FAULT:
            self._attr_native_value = 'FAULT'
        elif flags & DeviceStatusBitsB7B0.LINE_FAIL:
            self._attr_native_value = 'LINE_FAIL'
        elif flags & DeviceStatusBitsB7B0.INVERTER_OVERLOAD:
            self._attr_native_value = 'INVERTER_OVERLOAD'
        elif flags & DeviceStatusBitsB7B0.BATTERY_LOW:
            self._attr_native_value = 'BATTERY_LOW'
        else:
            self._attr_native_value = 'OK'
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        qpigs = self.data.get("qpigs", {})
        bits = qpigs.get("device_status_bits_b7_b0", 0)
        attrs = parse_device_status_bits_b7_b0(bits)
        return attrs


class DirectOperatingModeSensor(DirectEnumSensorBase):
    """Inverter operating mode from QMOD: PowerOn / Standby / Line /
    Battery / ShutdownApproaching / Fault.

    Useful as an automation trigger ("battery active → notify",
    "fault → alarm") without having to template-parse status bit strings.

    The decoder returns the field as an ``OperatingMode`` enum instance
    (or the literal string ``"Unknown"`` when the code didn't match any
    known mode). Coerce to ``.name`` so HA's ENUM-class validation
    accepts the value.
    """

    enum_class = OperatingMode

    def __init__(self, inverter_device, coordinator):
        super().__init__(
            inverter_device, coordinator,
            data_section="qmod", data_key="operating_mode",
            sensor_suffix="operating_mode", name_suffix="Operating Mode",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        section = self.data.get("qmod", {})
        raw = section.get("operating_mode")
        if hasattr(raw, "name"):
            value = raw.name
        elif isinstance(raw, str):
            value = raw
        else:
            value = None
        if value in self.options:
            self._attr_native_value = value
        else:
            self._attr_native_value = None
        self.async_write_ha_state()


# ---------------------------------------------------------------------------
# Inverter Warning / Fault summary sensor — combines PI30 QPIWS and PI18 FWS
# into a single human-readable status text, with every individual flag
# preserved as an attribute for granular automations.
# ---------------------------------------------------------------------------


# Severity order for the summary text. Higher index = lower priority. The
# first set bit found in this list becomes the displayed state; the
# state shows "OK" when no bit is set.
#
# Each entry is a *base name* — the lookup tries both ``flags[name]``
# (PI30 QPIWS) and ``flags["warn_" + name]`` (PI18 QFWS + the agent's
# postgen flat snapshot), so all three transports share one severity
# table without duplicate entries.
_WARNING_SEVERITY_ORDER: tuple[tuple[str, str], ...] = (
    ("fault_active",                  "Fault Active"),                # agent only
    ("inverter_fault",                "Inverter Fault"),
    ("battery_under_shutdown",        "Battery Shutdown"),
    ("battery_open",                  "Battery Disconnected"),
    ("battery_short",                 "Battery Short Circuit"),
    ("battery_over_current",          "Battery Overcurrent"),         # agent
    ("self_test_fail",                "Self-test Fail"),
    ("inverter_over_current",         "Inverter Overcurrent"),
    ("inverter_negative_power",       "Inverter Negative Power"),     # agent
    ("bus_over",                      "Bus Overvoltage"),
    ("bus_under",                     "Bus Undervoltage"),
    ("bus_soft_fail",                 "Bus Soft-start Fail"),
    ("over_temperature",              "Over Temperature"),
    ("inverter_over_temperature",     "Inverter Over Temperature"),   # agent
    ("dcdc_over_temperature",         "DC-DC Over Temperature"),      # agent
    ("pv_over_temperature",           "PV Over Temperature"),         # agent
    ("eeprom_fault",                  "EEPROM Fault"),
    ("current_sensor_fail",           "Current Sensor Fail"),
    ("fan_locked",                    "Fan Locked"),
    ("overload",                      "Overload"),
    ("battery_voltage_high",          "Battery Overvoltage"),
    ("battery_low_alarm",             "Battery Low"),
    ("battery_too_low_to_charge",     "Battery Too Low to Charge"),
    ("battery_type_incompatible",     "Battery Type Mismatch"),       # agent
    ("inverter_voltage_too_high",     "Inverter Output Overvoltage"),
    ("inverter_voltage_too_low",      "Inverter Output Undervoltage"),
    ("op_dc_voltage_over",            "Output DC Overvoltage"),
    ("pv_voltage_high",               "PV Overvoltage"),
    ("pv_low_voltage",                "PV Voltage Too Low"),          # agent
    ("pv_over_current",               "PV Overcurrent"),              # agent
    ("mppt_overload_fault",           "MPPT Overload"),
    ("opv_short",                     "Output Short"),
    ("inverter_soft_fail",            "Inverter Soft-start Fail"),
    ("mains_low_frequency",           "Grid Low Frequency"),          # agent
    ("mains_over_frequency",          "Grid Over Frequency"),         # agent
    ("mains_waveform_abnormal",       "Grid Waveform Abnormal"),      # agent
    ("parallel_host_lost",            "Parallel Host Lost"),          # agent
    ("parallel_sync_abnormal",        "Parallel Sync Lost"),          # agent
    ("parallel_battery_diff",         "Parallel Battery Mismatch"),   # agent
    ("parallel_mode_inconsistent",    "Parallel Mode Mismatch"),      # agent
    ("parallel_version_incompatible", "Parallel Version Mismatch"),   # agent
    ("parallel_comm_interrupted",     "Parallel Comm Lost"),          # agent
    ("battery_eq_charging",           "Battery Equalize Charging"),   # agent (info)
    ("pv_energy_low",                 "PV Energy Low"),               # agent (info)
    ("power_limit",                   "Power Limiting"),
    ("mppt_overload_warning",         "MPPT Overload Warning"),
    ("line_fail",                     "Line Fail"),
    # Sensor-calibration warnings — diagnostic, lowest priority.
    ("battery_current_bias",          "Battery Current Bias"),        # agent
    ("inverter_current_bias",         "Inverter Current Bias"),       # agent
    ("output_current_bias",           "Output Current Bias"),         # agent
    ("pv_current_bias",               "PV Current Bias"),             # agent
)


def _flag_set(flags: dict, base_name: str) -> bool:
    """Test whether a warning flag is set under either of its two
    naming conventions: bare (PI30 QPIWS) or ``warn_``-prefixed (PI18
    QFWS + agent postgen). Used by the severity walk so a single
    base-name table works across all transports."""
    return bool(flags.get(base_name)) or bool(flags.get(f"warn_{base_name}"))


def _ui_language(hass) -> str:
    """Return the two-letter HA UI language, defaulting to English.

    Entity callbacks are also exercised by the HA-free unit tests, where
    ``self.hass`` is not populated yet, so this helper must tolerate a
    missing config object.
    """
    config = getattr(hass, "config", None)
    return normalize_language(getattr(config, "language", None))


def _join_advice(keys: list[str], table: dict, language: str) -> str | None:
    """Join the non-empty advice strings for the active keys."""
    seen: list[str] = []
    for key in keys:
        text = table.get(key, {}).get(language)
        if text and text not in seen:
            seen.append(text)
    return " ".join(seen) if seen else None


class DirectInverterFaultSummarySensor(DirectSensorBase):
    """Single-glance "what's wrong with the inverter" sensor.

    State machine: walks the warning bits in severity order, displays
    the worst active one as text. ``"OK"`` when nothing is flagged.
    Surfaces *every* flag (set or clear) plus the active count as
    state attributes for granular template / automation use.

    Works for both PI30 (via QPIWS dict) and PI18 (via QFWS dict with
    its richer ``fault_code`` / ``fault_description`` semantics). If the
    inverter doesn't report a section, the sensor falls back to the
    other. Effectively unavailable only when *both* sections are empty.
    """

    _attr_icon = "mdi:alert-circle-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_translation_key = "direct_fault_summary"

    def __init__(self, inverter_device, coordinator):
        super().__init__(inverter_device, coordinator)
        self._attr_unique_id = (
            f"{inverter_device.inverter_id}_direct_fault_summary"
        )

    def _merged_warnings(self) -> dict:
        """Pick the populated warning section (PI30 ``qpiws`` or PI18
        ``qfws``) — they share enough field names that downstream
        consumers can treat the result as a single namespace."""
        qpiws = self.data.get("qpiws", {}) or {}
        qfws = self.data.get("qfws", {}) or {}
        # Prefer whichever is populated; if both, merge with PI18 fields
        # only adding non-overlapping warn_* keys.
        merged = dict(qpiws)
        for k, v in qfws.items():
            merged.setdefault(k, v)
        return merged

    @callback
    def _handle_coordinator_update(self) -> None:
        flags = self._merged_warnings()

        # PI18 / SMG-II carry an explicit fault_code — if non-zero, it
        # takes absolute priority over individual warning bits because
        # it represents an active hardware fault. SMG-II additionally
        # exposes warning_code as a separate DWORD; non-zero there is a
        # "warning state" rather than fault but still warrants summary.
        fault_code = flags.get("fault_code")
        fault_description = flags.get("fault_description")
        warning_code = flags.get("warning_code")
        language = _ui_language(getattr(self, "hass", None))
        fault_prefix = "Défaut" if language == "fr" else "Fault"
        warning_prefix = "Alerte" if language == "fr" else "Warning"

        if isinstance(fault_code, (int, float)) and fault_code != 0:
            active_faults = list(flags.get("fault_keys") or [])
            labels = [fault_label(key, language) for key in active_faults]
            if labels:
                self._attr_native_value = (
                    f"{fault_prefix}: {', '.join(labels)}"
                )
            else:
                self._attr_native_value = (
                    f"{fault_prefix}: "
                    f"{fault_description or f'code 0x{int(fault_code):08X}'}"
                )
            attrs = _flag_attrs(flags)
            if labels:
                attrs["active_faults"] = labels
                attrs["fault_keys"] = active_faults
                advice = _join_advice(active_faults, FAULT_ADVICE, language)
                if advice:
                    attrs["fault_advice"] = advice
            self._attr_extra_state_attributes = attrs
            self.async_write_ha_state()
            return

        if isinstance(warning_code, (int, float)) and warning_code != 0:
            active_warnings = list(flags.get("warning_keys") or [])
            if active_warnings:
                severity = {
                    key: index
                    for index, (key, _display) in enumerate(
                        _WARNING_SEVERITY_ORDER
                    )
                }
                active_warnings.sort(
                    key=lambda key: severity.get(key, len(severity))
                )
                labels = [
                    warning_label(key, language) for key in active_warnings
                ]
                suffix = ""
                if len(labels) > 1:
                    suffix = (
                        f" (+{len(labels) - 1} de plus)"
                        if language == "fr"
                        else f" (+{len(labels) - 1} more)"
                    )
                self._attr_native_value = (
                    f"{warning_prefix}: {labels[0]}{suffix}"
                )
                attrs = _flag_attrs(flags)
                attrs["active_warnings"] = labels
                attrs["warning_keys"] = active_warnings
                advice = _join_advice(
                    active_warnings, WARNING_ADVICE, language
                )
                if advice:
                    attrs["warning_advice"] = advice
            else:
                # A code outside the published map (or an older payload
                # without decoded keys) still gets a readable fallback.
                self._attr_native_value = (
                    f"{warning_prefix}: code 0x{int(warning_code):08X}"
                )
                attrs = _flag_attrs(flags)
            self._attr_extra_state_attributes = attrs
            self.async_write_ha_state()
            return

        # Walk severity-ordered list; first set bit wins. The helper
        # transparently handles both naming conventions (bare vs warn_).
        first_active = None
        for key, display in _WARNING_SEVERITY_ORDER:
            if _flag_set(flags, key):
                first_active = (
                    warning_label(key, language)
                    if key in WARNING_BY_KEY
                    else display
                )
                break

        # Count total unique active bits across both conventions to size
        # the "(+N more)" suffix. De-duplicate so an agent setting both
        # ``overload`` and ``warn_overload`` (theoretically) only counts
        # once.
        active_keys: set[str] = set()
        for key, _ in _WARNING_SEVERITY_ORDER:
            if _flag_set(flags, key):
                active_keys.add(key)
        # Plus any warn_* flags we haven't catalogued in the severity
        # table (unknown agent/firmware extensions) — surface them as
        # "+N more" so they're at least counted.
        cataloged_warn = {f"warn_{k}" for k, _ in _WARNING_SEVERITY_ORDER}
        for k, v in flags.items():
            if k.startswith("warn_") and v and k not in cataloged_warn:
                active_keys.add(k)
        total_active = len(active_keys)

        if total_active == 0:
            self._attr_native_value = "OK"
        elif first_active is None:
            # Only uncataloged warn_* bits set — name the count.
            self._attr_native_value = (
                f"{warning_prefix}: {total_active} active"
            )
        elif total_active > 1:
            suffix = (
                f" (+{total_active - 1} de plus)"
                if language == "fr"
                else f" (+{total_active - 1} more)"
            )
            self._attr_native_value = (
                f"{warning_prefix}: {first_active}{suffix}"
            )
        else:
            self._attr_native_value = f"{warning_prefix}: {first_active}"

        self._attr_extra_state_attributes = _flag_attrs(flags)
        self.async_write_ha_state()


def _flag_attrs(flags: dict) -> dict:
    """Produce the attribute dict for the fault summary sensor.

    Keeps booleans as booleans (HA renders them as on/off in the UI),
    drops the internal ``_reserved_*`` bits, and adds a derived
    ``active_count`` for easy template use.
    """
    attrs: dict = {}
    active = 0
    for key, value in flags.items():
        if key.startswith("_reserved_"):
            continue
        if key in ("has_fault", "has_warning"):
            # Meta-flags: useful for templates, but they are not one of
            # the individual active conditions counted by active_count.
            attrs[key] = value
            continue
        if isinstance(value, bool):
            attrs[key] = value
            if value:
                active += 1
        else:
            # Non-boolean fields (fault_code, warning_code, lists,
            # descriptions) pass through verbatim.
            attrs[key] = value
    attrs["active_count"] = active
    return attrs


class DirectFaultAdviceSensor(DirectSensorBase):
    """Actionable advice for the active fault or warning.

    The fault-summary sensor answers *what* is active; this one answers
    *what to do about it*. Its state is the plain-language advice for the
    active SMG-II fault/warning bits, translated to the HA UI language.
    """

    _attr_icon = "mdi:lightbulb-alert-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_translation_key = "direct_fault_advice"

    def __init__(self, inverter_device, coordinator):
        super().__init__(inverter_device, coordinator)
        self._attr_unique_id = (
            f"{inverter_device.inverter_id}_direct_fault_advice"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        qpiws = self.data.get("qpiws", {}) or {}
        qfws = self.data.get("qfws", {}) or {}
        merged = dict(qpiws)
        for key, value in qfws.items():
            merged.setdefault(key, value)

        language = _ui_language(getattr(self, "hass", None))
        active_faults = list(merged.get("fault_keys") or [])
        active_warnings = list(merged.get("warning_keys") or [])

        advice = _join_advice(active_faults, FAULT_ADVICE, language)
        if advice is None:
            advice = _join_advice(active_warnings, WARNING_ADVICE, language)

        has_active_bit = any(
            bool(value)
            for key, value in merged.items()
            if isinstance(value, bool)
            and value
            and key not in ("has_fault", "has_warning")
            and not key.startswith("_reserved_")
        )
        fault_code = merged.get("fault_code")
        warning_code = merged.get("warning_code")
        has_code = (
            isinstance(fault_code, (int, float)) and fault_code != 0
        ) or (
            isinstance(warning_code, (int, float)) and warning_code != 0
        )

        if advice is None:
            if has_code or has_active_bit:
                advice = (
                    "No detailed advice is available for this code. "
                    "Check the fault-summary attributes and the inverter manual."
                    if language == "en"
                    else "Aucun conseil détaillé n'est disponible pour ce code. "
                    "Consultez les attributs du résumé des défauts et la notice "
                    "de l'onduleur."
                )
            else:
                advice = (
                    "No active fault or warning."
                    if language == "en"
                    else "Aucun défaut ni alerte active."
                )

        self._attr_native_value = advice
        attrs: dict = {}
        if active_faults:
            attrs["fault_keys"] = active_faults
        if active_warnings:
            attrs["warning_keys"] = active_warnings
        self._attr_extra_state_attributes = attrs
        self.async_write_ha_state()


# Sensors that depend on QPIGS/QPIGS2 fields SMG-II does not report. They
# are hidden for Modbus entries instead of publishing constants ("OK",
# 400 V bus, mirrored SCC voltage) or permanently-empty values.
MODBUS_UNSUPPORTED_SENSORS = frozenset({
    DirectPV2PowerSensor,
    DirectPV2VoltageSensor,
    DirectPV2CurrentSensor,
    DirectBusVoltageSensor,
    DirectSCCBatteryVoltageSensor,
    DirectDeviceStatusSensor,
})


DIRECT_SENSORS = [
    DirectPVPowerSensor,
    DirectPV2PowerSensor,
    DirectPVVoltageSensor,
    DirectPV2VoltageSensor,
    DirectPVInputCurrentSensor,
    DirectPV2CurrentSensor,
    DirectBatteryVoltageSensor,
    DirectBatteryChargingCurrentSensor,
    DirectBatteryDischargeCurrentSensor,
    DirectBatteryCapacitySensor,
    DirectInverterOutputPowerSensor,
    DirectInverterTemperatureSensor,
    DirectInverterDCModuleTemperatureSensor,
    DirectGridVoltageSensor,
    DirectGridFrequencySensor,
    DirectACGridInPowerSensor,
    DirectACOutputVoltageSensor,
    DirectACOutputFrequencySensor,
    DirectOutputApparentPowerSensor,
    DirectLoadPercentSensor,
    DirectBusVoltageSensor,
    DirectSCCBatteryVoltageSensor,
    DirectDeviceStatusSensor,
    DirectBatteryPowerSensor,
    DirectOperatingModeSensor,
    DirectInverterFaultSummarySensor,
    DirectFaultAdviceSensor,
]


# ---------------------------------------------------------------------------
# PI18-only sensors. Wired up *in addition* to DIRECT_SENSORS when the user
# selected PI18 in the config flow (registered conditionally in sensor.py).
# All read from the ``qpigs`` section because the PI18 decoder folds every
# GS field — including the PI18-specific extras — into a single dict.
# ---------------------------------------------------------------------------


class DirectPV2InputPowerSensor(DirectWattSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device, coordinator,
            data_section="qpigs", data_key="pv2_input_power",
            sensor_suffix="pv2_input_power", name_suffix="PV2 Input Power",
        )


class DirectPV2InputVoltageSensor(DirectVoltageSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device, coordinator,
            data_section="qpigs", data_key="pv2_input_voltage",
            sensor_suffix="pv2_input_voltage", name_suffix="PV2 Input Voltage",
        )


class DirectPV2InputCurrentSensor(DirectCurrentSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device, coordinator,
            data_section="qpigs", data_key="pv2_input_current",
            sensor_suffix="pv2_input_current", name_suffix="PV2 Input Current",
        )


class DirectMPPT1TemperatureSensor(DirectTemperatureSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device, coordinator,
            data_section="qpigs", data_key="mppt1_temperature",
            sensor_suffix="mppt1_temperature", name_suffix="MPPT1 Temperature",
        )


class DirectMPPT2TemperatureSensor(DirectTemperatureSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device, coordinator,
            data_section="qpigs", data_key="mppt2_temperature",
            sensor_suffix="mppt2_temperature", name_suffix="MPPT2 Temperature",
        )


class DirectSCC2BatteryVoltageSensor(DirectVoltageSensorBase):
    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device, coordinator,
            data_section="qpigs", data_key="scc2_battery_voltage",
            sensor_suffix="scc2_battery_voltage", name_suffix="SCC2 Battery Voltage",
        )


class DirectMPPT1StatusSensor(DirectEnumSensorBase):
    enum_class = PI18MPPTStatus

    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device, coordinator,
            data_section="qpigs", data_key="mppt1_status",
            sensor_suffix="mppt1_status", name_suffix="MPPT1 Status",
        )


class DirectMPPT2StatusSensor(DirectEnumSensorBase):
    enum_class = PI18MPPTStatus

    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device, coordinator,
            data_section="qpigs", data_key="mppt2_status",
            sensor_suffix="mppt2_status", name_suffix="MPPT2 Status",
        )


class DirectBatteryPowerDirectionSensor(DirectEnumSensorBase):
    enum_class = PI18BatteryPowerDirection

    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device, coordinator,
            data_section="qpigs", data_key="battery_power_direction",
            sensor_suffix="battery_power_direction", name_suffix="Battery Power Direction",
        )


class DirectDCACPowerDirectionSensor(DirectEnumSensorBase):
    enum_class = PI18DCACPowerDirection

    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device, coordinator,
            data_section="qpigs", data_key="dcac_power_direction",
            sensor_suffix="dcac_power_direction", name_suffix="DC-AC Power Direction",
        )


class DirectLinePowerDirectionSensor(DirectEnumSensorBase):
    enum_class = PI18LinePowerDirection

    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(
            inverter_device, coordinator,
            data_section="qpigs", data_key="line_power_direction",
            sensor_suffix="line_power_direction", name_suffix="Line Power Direction",
        )


PI18_SENSORS = [
    DirectPV2InputPowerSensor,
    DirectPV2InputVoltageSensor,
    DirectPV2InputCurrentSensor,
    DirectMPPT1TemperatureSensor,
    DirectMPPT2TemperatureSensor,
    DirectSCC2BatteryVoltageSensor,
    DirectMPPT1StatusSensor,
    DirectMPPT2StatusSensor,
    DirectBatteryPowerDirectionSensor,
    DirectDCACPowerDirectionSensor,
    DirectLinePowerDirectionSensor,
]
