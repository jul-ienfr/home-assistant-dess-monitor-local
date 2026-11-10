"""Switch entities for toggleable vSoC behaviours.

Currently exposes the ``vSoC Float Deadband`` master toggle. When ON,
the SoC integrator suppresses quantisation-noise current samples while
the battery sits in float (see ``FloatVoltageWindowNumber`` /
``FloatNoiseFloorNumber`` for the thresholds). When OFF, every reported
current sample is integrated verbatim — useful if your inverter reports
fractional, un-quantised current and the deadband would only hide real
micro-discharge.
"""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
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
from custom_components.dess_monitor_local.coordinators.direct_coordinator import (
    DirectCoordinator,
)
from custom_components.dess_monitor_local.hub import InverterDevice
from custom_components.dess_monitor_local.smg2_settings import (
    async_write_smg2_register,
    ui_language,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HubConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub = config_entry.runtime_data
    entry_protocol = config_entry.options.get(CONF_PROTOCOL)
    new_entities = []
    for item in hub.items:
        new_entities.append(FloatDeadbandSwitch(item, hass))
        item_protocol = getattr(item, "protocol", None) or entry_protocol
        if item_protocol == PROTOCOL_MODBUS:
            for spec in _SMG2_SWITCH_SPECS:
                new_entities.append(
                    SMG2ConfigSwitch(item, hub.direct_coordinator, **spec)
                )
    if new_entities:
        async_add_entities(new_entities)


class FloatDeadbandSwitch(SwitchEntity, RestoreEntity):
    """Master enable for the SoC float-mode deadband.

    Defaults ON — preserves the behaviour shipped before the toggle
    existed. Restored across HA restarts. Filed under the device's
    Configuration section.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:sine-wave"
    _attr_has_entity_name = True
    _attr_translation_key = "float_deadband"

    def __init__(self, inverter_device: InverterDevice, hass: HomeAssistant):
        self._inverter_device = inverter_device
        self._hass = hass
        self._attr_unique_id = f"{inverter_device.inverter_id}_float_deadband"
        self._attr_is_on = True  # default: deadband active
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, inverter_device.inverter_id)},
            name=inverter_device.name,
            manufacturer="ESS",
            model=inverter_device.inverter_id,
            sw_version=inverter_device.firmware_version,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state in ("on", "off"):
            self._attr_is_on = state.state == "on"

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()


# Writable SMG-II configuration bits. Each register uses bit 0 only; the
# value is read back through the QPIRI projection.
_SMG2_SWITCH_SPECS: tuple[dict, ...] = (
    {
        "key": "lcd_auto_return",
        "address": 306,
        "data_key": "lcd_auto_return",
        "icon": "mdi:monitor",
        "description": {
            "en": "Returns the LCD to the home screen after inactivity.",
            "fr": "Ramène l'écran LCD à l'accueil après une période d'inactivité.",
        },
    },
    {
        "key": "energy_saving",
        "address": 307,
        "data_key": "energy_saving_mode",
        "icon": "mdi:leaf",
        "description": {
            "en": "Reduces standby consumption; may slow response to small loads.",
            "fr": "Réduit la consommation en veille ; peut ralentir la réponse aux petites charges.",
        },
    },
    {
        "key": "overload_auto_restart",
        "address": 308,
        "data_key": "overload_auto_restart",
        "icon": "mdi:restart",
        "description": {
            "en": "Restarts the output automatically after an overload clears.",
            "fr": "Redémarre automatiquement la sortie après disparition de la surcharge.",
        },
    },
    {
        "key": "overtemp_auto_restart",
        "address": 309,
        "data_key": "overtemp_auto_restart",
        "icon": "mdi:restart-alert",
        "description": {
            "en": "Restarts automatically after the inverter cools down.",
            "fr": "Redémarre automatiquement après refroidissement de l'onduleur.",
        },
    },
    {
        "key": "overload_bypass",
        "address": 310,
        "data_key": "overload_transfer_to_bypass",
        "icon": "mdi:bypass",
        "description": {
            "en": "Transfers the loads to grid bypass on overload.",
            "fr": "Bascule les charges sur le bypass réseau en cas de surcharge.",
        },
    },
    {
        "key": "battery_equalization",
        "address": 313,
        "data_key": "battery_eq_enabled",
        "icon": "mdi:battery-sync",
        "description": {
            "en": (
                "Periodic equalization charge for flooded/lead-acid batteries. "
                "Leave off for lithium."
            ),
            "fr": (
                "Charge d'égalisation périodique pour batteries plomb ouvertes. "
                "Laisser désactivé pour le lithium."
            ),
        },
    },
    {
        "key": "remote_output",
        "address": 420,
        "data_key": "remote_output_enable",
        "icon": "mdi:remote",
        "description": {
            "en": (
                "0 = output off, 1 = output on. Turning this off can cut "
                "power to the loads."
            ),
            "fr": (
                "0 = sortie coupée, 1 = sortie activée. Couper cette sortie "
                "peut priver les charges de courant."
            ),
        },
    },
)


class SMG2ConfigSwitch(CoordinatorEntity, SwitchEntity):
    """Writable SMG-II on/off register."""

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
        description: dict[str, str],
    ):
        super().__init__(coordinator)
        self._inverter_device = inverter_device
        self._key = key
        self._address = address
        self._data_key = data_key
        self._description = description
        self._pending_on: bool | None = None
        self._attr_unique_id = f"{inverter_device.inverter_id}_smg2_{key}"
        self._attr_translation_key = f"smg2_{key}"
        self._attr_icon = icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, inverter_device.inverter_id)},
            name=inverter_device.name,
            manufacturer="ESS",
            model=inverter_device.inverter_id,
            sw_version=inverter_device.firmware_version,
        )

    @property
    def _qpiri(self) -> dict:
        return (self.coordinator.data or {}).get(
            self._inverter_device.inverter_id, {}
        ).get("qpiri") or {}

    @property
    def is_on(self) -> bool | None:
        if self._pending_on is not None:
            return self._pending_on
        raw = self._qpiri.get(self._data_key)
        try:
            return bool(int(float(raw)))
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict:
        raw = self._qpiri.get(self._data_key)
        attrs = {}
        if raw is not None:
            try:
                attrs["raw_value"] = int(float(raw))
            except (TypeError, ValueError):
                pass
        attrs["description"] = self._description[ui_language(self.hass)]
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        self._pending_on = None
        self.async_write_ha_state()

    async def _write(self, value: int) -> None:
        result = await async_write_smg2_register(
            self.hass,
            self._inverter_device.device_data,
            self._address,
            value,
        )
        if isinstance(result, dict) and result.get("error"):
            _LOGGER.warning(
                "SMG-II setting %s write failed for %s: %s",
                self._key, self._inverter_device.name, result["error"],
            )
            return
        self._pending_on = bool(value)
        self.async_write_ha_state()
        self.coordinator.force_section("qpiri")
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        await self._write(1)

    async def async_turn_off(self, **kwargs) -> None:
        await self._write(0)
