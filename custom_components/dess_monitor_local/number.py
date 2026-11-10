import logging

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.dess_monitor_local import HubConfigEntry
from custom_components.dess_monitor_local.const import (
    CONF_PROTOCOL,
    DOMAIN,
    PROTOCOL_MODBUS,
)
from custom_components.dess_monitor_local.coordinators.direct_coordinator import DirectCoordinator
from custom_components.dess_monitor_local.hub import InverterDevice
from custom_components.dess_monitor_local.smg2_settings import (
    SMG2_MAX_CHARGE_CURRENT,
    async_write_smg2_register,
    min_total_charge_current,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: HubConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    hub = config_entry.runtime_data
    entry_protocol = config_entry.options.get(CONF_PROTOCOL)
    new_devices = []

    for item in hub.items:
        new_devices.extend([
            BatteryCapacityNumber(item, hass),
            FullChargeSyncVoltageNumber(item, hass),
            DischargeFloorSoCNumber(item, hass),
            FloatVoltageWindowNumber(item, hass),
            FloatNoiseFloorNumber(item, hass),
        ])
        item_protocol = getattr(item, "protocol", None) or entry_protocol
        if item_protocol == PROTOCOL_MODBUS:
            for spec in _SMG2_NUMBER_SPECS:
                new_devices.append(
                    SMG2ConfigNumber(item, hub.direct_coordinator, **spec)
                )
    if new_devices:
        async_add_entities(new_devices)


class NumberBase(CoordinatorEntity, NumberEntity):
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
        """Return True if inverter_device and hub is available."""
        return True
        # return self._inverter_device.online and self._inverter_device.hub.online

    @property
    def data(self):
        # Safe for a freshly-added hub child not yet in coordinator.data.
        return (self.coordinator.data or {}).get(
            self._inverter_device.inverter_id
        ) or {}


class _VSocConfigNumber(NumberEntity, RestoreEntity):
    """Base for the user-tunable vSoC parameters.

    Common behavior: value restored across HA restarts, BOX input mode,
    and ``EntityCategory.CONFIG`` so HA files them under the device's
    "Configuration" section instead of cluttering the main dashboard.

    Subclasses set the class attributes below plus the standard
    ``_attr_native_*`` range / unit / icon fields.
    """

    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    # Subclass contract:
    _id_suffix: str = ""        # unique_id tail == translation key tail
    _name_suffix: str = ""      # English fallback, unused when translated
    _default_value: float | None = 0.0

    def __init__(self, inverter_device, hass):
        self._inverter_device = inverter_device
        self._hass = hass
        self._attr_unique_id = f"{inverter_device.inverter_id}_{self._id_suffix}"
        self._attr_translation_key = self._id_suffix
        self._value = self._default_value
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, inverter_device.inverter_id)},
            name=inverter_device.name,
            manufacturer="ESS",
            model=inverter_device.inverter_id,
            sw_version=inverter_device.firmware_version,
        )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state and state.state not in ("unknown", "unavailable"):
            try:
                self._value = float(state.state)
            except ValueError:
                self._value = self._default_value

    @property
    def native_value(self):
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        self._value = value
        self.async_write_ha_state()


class BatteryCapacityNumber(_VSocConfigNumber):
    """Nominal battery capacity in **ampere-hours**.

    Ah is the unit you can read directly off the battery label or BMS
    datasheet — no need to multiply by a guessed nominal voltage (LFP
    banks in particular are often labelled "48 V" but actually run at
    ~51.2 V nominal, a 6-7% capacity error trap).

    Coulomb counting in the SoC sensor uses this value directly:
    ``SoC% = (accumulated_charge_ah / capacity_ah) × 100``.
    """

    # Stays None until the user enters their nameplate value — the SoC
    # sensor reports unavailable until then.
    _id_suffix = "battery_capacity_ah"
    _name_suffix = "vSoC Battery Capacity (Ah)"
    _default_value = None

    # Residential banks 50–600 Ah; cap at 2000 for commercial / parallel.
    _attr_native_min_value = 0
    _attr_native_max_value = 2000
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "Ah"
    _attr_icon = "mdi:battery"


class FullChargeSyncVoltageNumber(_VSocConfigNumber):
    """Battery voltage at which vSoC snaps to 100%.

    Overrides the inverter's bulk_charging_voltage for SoC-reset purposes.
    Useful for LiFePO4 packs that are effectively full at, say, 27.4 V
    while the inverter's bulk target sits at 28.0 V. ``0`` disables the
    override and falls back to the inverter's bulk voltage.
    """

    _id_suffix = "full_charge_sync_voltage"
    _name_suffix = "vSoC Full Charge Sync Voltage"
    _default_value = 0.0

    _attr_native_min_value = 0.0
    _attr_native_max_value = 120.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = "V"
    _attr_icon = "mdi:battery-charging-100"


class DischargeFloorSoCNumber(_VSocConfigNumber):
    """Floor SoC for the "time to discharge floor" / backup-time sensors.

    Common values: 15-20% for LFP (cycle-life preservation), 50% for
    lead-acid (DoD limit), 0% for "until empty".
    """

    _id_suffix = "discharge_floor_soc"
    _name_suffix = "vSoC Discharge Floor"
    _default_value = 15.0

    _attr_native_min_value = 0.0
    _attr_native_max_value = 80.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:battery-low"


class FloatVoltageWindowNumber(_VSocConfigNumber):
    """Float-mode deadband — voltage window.

    Half-width of the dead-zone around the inverter's float setpoint
    within which the SoC integrator treats the tick as "in float".
    Together with the noise floor it cancels the SoC drift caused by
    inverters that quantise discharge current to integer Amperes.
    See ``vSoC Float Noise Floor`` and the ``vSoC Float Deadband`` switch.
    """

    _id_suffix = "float_voltage_window"
    _name_suffix = "vSoC Float Voltage Window"
    _default_value = 0.5

    _attr_native_min_value = 0.0
    _attr_native_max_value = 2.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = "V"
    _attr_icon = "mdi:sine-wave"


class FloatNoiseFloorNumber(_VSocConfigNumber):
    """Float-mode deadband — current noise floor.

    Reported battery current at or below this magnitude (while voltage is
    within the float window) is treated as quantisation noise and not
    integrated. Raise it for larger banks whose firmware quantises in
    2-3 A steps; lower it toward 0 to make the deadband stricter.
    """

    _id_suffix = "float_noise_floor"
    _name_suffix = "vSoC Float Noise Floor"
    _default_value = 1.5

    _attr_native_min_value = 0.0
    _attr_native_max_value = 10.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = "A"
    _attr_icon = "mdi:current-dc"


# Writable SMG-II configuration registers. Voltage and current registers
# use a 0.1 scale; times and SOC values are raw integers.
_SMG2_NUMBER_SPECS: tuple[dict, ...] = (
    {
        "key": "battery_ovp",
        "address": 323,
        "data_key": "battery_ovp",
        "icon": "mdi:battery-alert",
        "min": 28.0,
        "max": 32.0,
        "step": 0.1,
        "scale": 10,
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": NumberDeviceClass.VOLTAGE,
        "mode": NumberMode.BOX,
        "precision": 1,
    },
    {
        "key": "max_charge_voltage",
        "address": 324,
        "data_key": "max_charge_voltage",
        "icon": "mdi:battery-charging",
        "min": 24.0,
        "max": 30.0,
        "step": 0.1,
        "scale": 10,
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": NumberDeviceClass.VOLTAGE,
        "mode": NumberMode.BOX,
        "precision": 1,
    },
    {
        "key": "float_charge_voltage",
        "address": 325,
        "data_key": "float_charge_voltage",
        "icon": "mdi:battery-charging-50",
        "min": 24.0,
        "max": 30.0,
        "step": 0.1,
        "scale": 10,
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": NumberDeviceClass.VOLTAGE,
        "mode": NumberMode.BOX,
        "precision": 1,
    },
    {
        "key": "battery_recovery_voltage",
        "address": 326,
        "data_key": "battery_discharge_recovery_mains",
        "icon": "mdi:battery-sync",
        "min": 20.0,
        "max": 26.0,
        "step": 0.1,
        "scale": 10,
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": NumberDeviceClass.VOLTAGE,
        "mode": NumberMode.BOX,
        "precision": 1,
    },
    {
        "key": "battery_low_cutoff_mains",
        "address": 327,
        "data_key": "battery_low_protection_mains",
        "icon": "mdi:battery-off",
        "min": 20.0,
        "max": 26.0,
        "step": 0.1,
        "scale": 10,
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": NumberDeviceClass.VOLTAGE,
        "mode": NumberMode.BOX,
        "precision": 1,
    },
    {
        "key": "battery_low_cutoff_offgrid",
        "address": 329,
        "data_key": "battery_low_protection_offgrid",
        "icon": "mdi:battery-off-outline",
        "min": 20.0,
        "max": 26.0,
        "step": 0.1,
        "scale": 10,
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": NumberDeviceClass.VOLTAGE,
        "mode": NumberMode.BOX,
        "precision": 1,
    },
    {
        "key": "max_charge_current",
        "address": 332,
        "data_key": "max_charging_current",
        "icon": "mdi:current-ac",
        "min": 0.0,
        "max": SMG2_MAX_CHARGE_CURRENT,
        "step": 0.1,
        "scale": 10,
        "unit": UnitOfElectricCurrent.AMPERE,
        "device_class": NumberDeviceClass.CURRENT,
        "mode": NumberMode.SLIDER,
        "precision": 1,
    },
    {
        "key": "equalization_voltage",
        "address": 334,
        "data_key": "eq_charging_voltage",
        "icon": "mdi:battery-sync",
        "min": 24.0,
        "max": 30.0,
        "step": 0.1,
        "scale": 10,
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": NumberDeviceClass.VOLTAGE,
        "mode": NumberMode.BOX,
        "precision": 1,
    },
    {
        "key": "equalization_time",
        "address": 335,
        "data_key": "eq_time_minutes",
        "icon": "mdi:timer",
        "min": 0,
        "max": 900,
        "step": 1,
        "scale": 1,
        "unit": UnitOfTime.MINUTES,
        "device_class": NumberDeviceClass.DURATION,
        "mode": NumberMode.BOX,
        "precision": 0,
    },
    {
        "key": "equalization_timeout",
        "address": 336,
        "data_key": "eq_timeout",
        "icon": "mdi:timer-outline",
        "min": 0,
        "max": 900,
        "step": 1,
        "scale": 1,
        "unit": UnitOfTime.MINUTES,
        "device_class": NumberDeviceClass.DURATION,
        "mode": NumberMode.BOX,
        "precision": 0,
    },
    {
        "key": "equalization_interval",
        "address": 337,
        "data_key": "eq_interval_days",
        "icon": "mdi:calendar-repeat",
        "min": 1,
        "max": 90,
        "step": 1,
        "scale": 1,
        "unit": UnitOfTime.DAYS,
        "device_class": NumberDeviceClass.DURATION,
        "mode": NumberMode.BOX,
        "precision": 0,
    },
    {
        "key": "soc_back_to_utility",
        "address": 341,
        "data_key": "soc_back_to_utility",
        "icon": "mdi:battery-alert",
        "min": 31,
        "max": 100,
        "step": 1,
        "scale": 1,
        "unit": PERCENTAGE,
        "device_class": None,
        "mode": NumberMode.BOX,
        "precision": 0,
    },
    {
        "key": "soc_back_to_battery",
        "address": 342,
        "data_key": "soc_back_to_battery",
        "icon": "mdi:battery-high",
        "min": 60,
        "max": 100,
        "step": 1,
        "scale": 1,
        "unit": PERCENTAGE,
        "device_class": None,
        "mode": NumberMode.BOX,
        "precision": 0,
    },
    {
        "key": "soc_low_cutoff",
        "address": 343,
        "data_key": "soc_low_cutoff",
        "icon": "mdi:battery-low",
        "min": 3,
        "max": 30,
        "step": 1,
        "scale": 1,
        "unit": PERCENTAGE,
        "device_class": None,
        "mode": NumberMode.BOX,
        "precision": 0,
    },
)


class SMG2ConfigNumber(NumberBase):
    """Writable SMG-II numeric setting."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        inverter_device: InverterDevice,
        coordinator: DirectCoordinator,
        *,
        key: str,
        address: int,
        data_key: str,
        icon: str,
        min: float,
        max: float,
        step: float,
        scale: int,
        unit: str,
        device_class,
        mode: NumberMode,
        precision: int,
    ):
        super().__init__(inverter_device, coordinator)
        self._key = key
        self._address = address
        self._data_key = data_key
        self._scale = scale
        self._pending_value: float | None = None
        self._attr_unique_id = f"{inverter_device.inverter_id}_smg2_{key}"
        self._attr_translation_key = f"smg2_{key}"
        self._attr_icon = icon
        self._attr_native_min_value = min
        self._attr_native_max_value = max
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_mode = mode
        self._attr_suggested_display_precision = precision

    @property
    def _qpiri(self) -> dict:
        return self.data.get("qpiri") or {}

    @property
    def native_min_value(self) -> float:
        """Return the lower bound accepted by the inverter.

        Register 332 is the total solar + mains charging current, and the
        SMG-II firmware requires it to be at least register 333 (max mains
        charging current). Without this dynamic bound the UI would let the
        user pick a value the firmware rejects with Modbus exception 03.
        """
        if getattr(self, "_key", None) == "max_charge_current":
            return min_total_charge_current(self._qpiri)
        return self._attr_native_min_value

    @property
    def native_value(self):
        if self._pending_value is not None:
            return self._pending_value
        raw = self._qpiri.get(self._data_key)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        if self._scale == 1:
            return int(round(value))
        return round(value, 1)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._pending_value = None
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        if value < self.native_min_value or value > self._attr_native_max_value:
            _LOGGER.warning(
                "SMG-II setting %s rejected %s: outside %s..%s",
                self._key,
                value,
                self.native_min_value,
                self._attr_native_max_value,
            )
            if (
                self._key == "max_charge_current"
                and value < self.native_min_value
            ):
                _LOGGER.warning(
                    "Lower the max mains charging current (register 333) "
                    "to %s A or less before lowering the total limit",
                    value,
                )
            return
        register_value = int(round(value * self._scale))
        register_value = max(0, min(0xFFFF, register_value))
        result = await async_write_smg2_register(
            self.hass,
            self._inverter_device.device_data,
            self._address,
            register_value,
        )
        if isinstance(result, dict) and result.get("error"):
            _LOGGER.warning(
                "SMG-II setting %s write failed for %s: %s",
                self._key, self._inverter_device.name, result["error"],
            )
            return
        self._pending_value = value
        self.async_write_ha_state()
        self.coordinator.force_section("qpiri")
        await self.coordinator.async_request_refresh()
