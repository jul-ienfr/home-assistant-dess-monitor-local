import logging

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.dess_monitor_local import HubConfigEntry
from custom_components.dess_monitor_local.api.commands.direct_command_queue import (
    get_command_queue,
)
from custom_components.dess_monitor_local.api.commands.direct_commands import (
    ChargeSourcePrioritySetting,
    OutputSourcePrioritySetting,
    set_charge_source_priority,
    set_max_utility_charge_current,
    set_output_source_priority,
)
from custom_components.dess_monitor_local.const import (
    CONF_PROTOCOL,
    DOMAIN,
    PROTOCOL_MODBUS,
)
from custom_components.dess_monitor_local.coordinators.direct_coordinator import DirectCoordinator
from custom_components.dess_monitor_local.hub import InverterDevice
from custom_components.dess_monitor_local.smg2_settings import (
    async_write_smg2_register,
    max_utility_charging_current_options,
)
from custom_components.dess_monitor_local.smg2_settings import (
    ui_language as _ui_language,
)

_LOGGER = logging.getLogger(__name__)

BATTERY_MODE_LI_VOLTAGE = "Lithium (Voltage)"
BATTERY_MODE_LI_BMS = "Lithium (BMS)"
BATTERY_MODE_LEAD_ACID = "Lead-acid"
BATTERY_MODES = (BATTERY_MODE_LI_VOLTAGE, BATTERY_MODE_LI_BMS, BATTERY_MODE_LEAD_ACID)


# (stable raw value, labels, description)
_OUTPUT_PRIORITY_CHOICES: tuple[
    tuple[str, dict[str, str], dict[str, str]], ...
] = (
    (
        "UtilityFirst",
        {"en": "Grid first", "fr": "Réseau d'abord"},
        {
            "en": (
                "Grid powers the loads. Solar and battery are backup; "
                "the battery stays charged."
            ),
            "fr": (
                "Le réseau alimente les charges. Le solaire et la batterie "
                "sont en secours ; la batterie reste chargée."
            ),
        },
    ),
    (
        "Solar",
        {"en": "Solar first", "fr": "Solaire d'abord"},
        {
            "en": (
                "Solar powers the loads, then the battery, then the grid. "
                "The grid takes over when solar is unavailable or the "
                "battery is low."
            ),
            "fr": (
                "Le solaire alimente les charges, puis la batterie, puis le "
                "réseau. Le réseau prend le relais quand le solaire manque "
                "ou que la batterie est basse."
            ),
        },
    ),
    (
        "SBU",
        {
            "en": "SBU (battery before grid)",
            "fr": "SBU (batterie avant réseau)",
        },
        {
            "en": (
                "Solar → battery → grid. The battery is used down to its "
                "low-voltage cutoff before switching to the grid."
            ),
            "fr": (
                "Solaire → batterie → réseau. La batterie est utilisée "
                "jusqu'à son seuil bas avant de passer au réseau."
            ),
        },
    ),
    (
        "SUB",
        {"en": "SUB (grid before battery)", "fr": "SUB (réseau avant batterie)"},
        {
            "en": (
                "Solar → grid → battery. The grid supplements solar; the "
                "battery is kept as reserve and used only without grid."
            ),
            "fr": (
                "Solaire → réseau → batterie. Le réseau complète le solaire ; "
                "la batterie est gardée en réserve et utilisée seulement "
                "sans réseau."
            ),
        },
    ),
)

_CHARGE_SOURCE_CHOICES: tuple[
    tuple[str, dict[str, str], dict[str, str]], ...
] = (
    (
        "UtilityFirst",
        {"en": "Grid first", "fr": "Réseau d'abord"},
        {
            "en": (
                "The grid charges the battery first; solar charges only "
                "when the grid is unavailable."
            ),
            "fr": (
                "Le réseau charge la batterie en priorité ; le solaire ne "
                "charge que lorsque le réseau est absent."
            ),
        },
    ),
    (
        "SolarFirst",
        {
            "en": "Solar first (grid backup)",
            "fr": "Solaire d'abord (réseau en secours)",
        },
        {
            "en": (
                "Solar charges the battery first; the grid charges only "
                "when solar production is unavailable."
            ),
            "fr": (
                "Le solaire charge la batterie en priorité ; le réseau ne "
                "charge que lorsque la production solaire est absente."
            ),
        },
    ),
    (
        "SolarAndUtility",
        {
            "en": "Solar + grid together",
            "fr": "Solaire + réseau ensemble",
        },
        {
            "en": "Solar and grid charge the battery at the same time.",
            "fr": "Le solaire et le réseau chargent la batterie en même temps.",
        },
    ),
    (
        "OnlySolar",
        {
            "en": "Solar only (no grid charging)",
            "fr": "Solaire uniquement (pas de charge réseau)",
        },
        {
            "en": (
                "Only solar charges the battery. The grid never charges it, "
                "even when available."
            ),
            "fr": (
                "Seul le solaire charge la batterie. Le réseau ne la charge "
                "jamais, même lorsqu'il est disponible."
            ),
        },
    ),
)

# Writable SMG-II configuration selects. The raw value in ``raw_value`` is
# the exact register value; the visible labels follow the HA UI language.
_SMG2_SELECT_SPECS: tuple[dict, ...] = (
    {
        "key": "input_voltage_range",
        "address": 302,
        "data_key": "input_voltage_range_code",
        "icon": "mdi:sine-wave",
        "choices": (
            (
                0,
                {"en": "Wide (appliance)", "fr": "Large (appareil)"},
                {
                    "en": "Accepts a wider, less stable grid voltage range.",
                    "fr": "Accepte une plage de tension réseau plus large et moins stable.",
                },
            ),
            (
                1,
                {"en": "Narrow (UPS)", "fr": "Étroit (UPS)"},
                {
                    "en": "Narrow, UPS-like input range for a stable grid.",
                    "fr": "Plage d'entrée étroite de type UPS, pour un réseau stable.",
                },
            ),
        ),
    },
    {
        "key": "buzzer_mode",
        "address": 303,
        "data_key": "buzzer_mode",
        "icon": "mdi:bell",
        "choices": (
            (
                0,
                {"en": "Silent", "fr": "Silencieux"},
                {"en": "No buzzer.", "fr": "Aucun signal sonore."},
            ),
            (
                1,
                {
                    "en": "Input changes + warnings + faults",
                    "fr": "Changements d'entrée + alertes + défauts",
                },
                {
                    "en": "Beeps on input changes, warnings and faults.",
                    "fr": "Bip sur changement d'entrée, alertes et défauts.",
                },
            ),
            (
                2,
                {"en": "Warnings + faults", "fr": "Alertes + défauts"},
                {
                    "en": "Beeps on warnings and faults only.",
                    "fr": "Bip uniquement sur alertes et défauts.",
                },
            ),
            (
                3,
                {"en": "Faults only", "fr": "Défauts uniquement"},
                {"en": "Beeps only on faults.", "fr": "Bip uniquement sur défauts."},
            ),
        ),
    },
    {
        "key": "lcd_backlight",
        "address": 305,
        "data_key": "lcd_backlight",
        "icon": "mdi:lightbulb",
        "choices": (
            (
                0,
                {"en": "Timed off", "fr": "Extinction temporisée"},
                {
                    "en": "Backlight turns off after the inactivity delay.",
                    "fr": "Le rétroéclairage s'éteint après le délai d'inactivité.",
                },
            ),
            (
                1,
                {"en": "Always on", "fr": "Toujours allumé"},
                {
                    "en": "Backlight stays on.",
                    "fr": "Le rétroéclairage reste allumé.",
                },
            ),
        ),
    },
    {
        "key": "output_voltage",
        "address": 320,
        "data_key": "output_voltage_setting_code",
        "icon": "mdi:power-plug",
        "choices": (
            (2200, {"en": "220 V", "fr": "220 V"}, {}),
            (2300, {"en": "230 V", "fr": "230 V"}, {}),
            (2400, {"en": "240 V", "fr": "240 V"}, {}),
        ),
    },
    {
        "key": "output_frequency",
        "address": 321,
        "data_key": "output_frequency_setting_code",
        "icon": "mdi:sine-wave",
        "choices": (
            (5000, {"en": "50 Hz", "fr": "50 Hz"}, {}),
            (6000, {"en": "60 Hz", "fr": "60 Hz"}, {}),
        ),
    },
    {
        "key": "battery_type",
        "address": 322,
        "data_key": "battery_type_code",
        "icon": "mdi:battery-sync",
        "choices": (
            (0, {"en": "AGM", "fr": "AGM"}, {}),
            (1, {"en": "Flooded", "fr": "Plomb ouvert"}, {}),
            (2, {"en": "User", "fr": "Utilisateur"}, {
                "en": "Custom voltage profile; use the battery voltage settings below.",
                "fr": "Profil de tension personnalisé ; utilisez les réglages de tension batterie ci-dessous.",
            }),
            (3, {"en": "Li1", "fr": "Li1"}, {}),
            (4, {"en": "Li2", "fr": "Li2"}, {}),
            (5, {"en": "Li3", "fr": "Li3"}, {}),
            (6, {"en": "Li4", "fr": "Li4"}, {}),
            (8, {"en": "Lib", "fr": "Lib"}, {}),
        ),
    },
    {
        "key": "turn_on_mode",
        "address": 406,
        "data_key": "turn_on_mode",
        "icon": "mdi:power-settings",
        "choices": (
            (
                0,
                {"en": "Local + remote", "fr": "Local + distant"},
                {
                    "en": "The front panel and the remote command both work.",
                    "fr": "La façade et la commande à distance fonctionnent.",
                },
            ),
            (
                1,
                {"en": "Local only", "fr": "Local uniquement"},
                {
                    "en": "Only the front panel can turn the inverter on.",
                    "fr": "Seule la façade peut allumer l'onduleur.",
                },
            ),
            (
                2,
                {"en": "Remote only", "fr": "Distant uniquement"},
                {
                    "en": "Only the remote command can turn the inverter on.",
                    "fr": "Seule la commande à distance peut allumer l'onduleur.",
                },
            ),
        ),
    },
)




#
# SCAN_INTERVAL = timedelta(seconds=30)
# PARALLEL_UPDATES = 1


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: HubConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    hub = config_entry.runtime_data
    coordinator = hub.direct_coordinator
    entry_protocol = config_entry.options.get(CONF_PROTOCOL)

    new_devices = []
    for item in hub.items:
        new_devices.append(InverterOutputPrioritySelect(item, coordinator))
        new_devices.append(InverterChargeSourcePrioritySelect(item, coordinator))
        new_devices.append(InverterMaxUtilityChargingCurrentNumber(item, coordinator))
        new_devices.append(BatteryModeSelect(item))

        # Raw-register settings only exist on the SMG-II Modbus map. A hub
        # can mix protocols, so use the per-item protocol when present.
        item_protocol = getattr(item, "protocol", None) or entry_protocol
        if item_protocol == PROTOCOL_MODBUS:
            for spec in _SMG2_SELECT_SPECS:
                new_devices.append(SMG2ConfigSelect(item, coordinator, **spec))

    if new_devices:
        async_add_entities(new_devices)


class BatteryModeSelect(SelectEntity, RestoreEntity):
    """User-selected battery chemistry / connection preset.

    Drives the SoC algorithm strategy:
      - "Lithium (Voltage)" — LFP-style voltage snap + Coulomb counter,
        eff=0.97, tail=0.05C, hysteresis=0.2V
      - "Lithium (BMS)"     — mirror battery_capacity field (BMS source)
      - "Lead-acid"         — wider hysteresis 0.5V, eff=0.85/0.90, tail=0.02C
    """

    _attr_options = list(BATTERY_MODES)
    _attr_icon = "mdi:battery-sync"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_translation_key = "battery_mode"

    def __init__(self, inverter_device: InverterDevice):
        self._inverter_device = inverter_device
        self._attr_unique_id = f"{inverter_device.inverter_id}_battery_mode"
        # Default preserves the existing (LFP voltage-based) behavior so
        # existing users don't see their SoC sensor change after upgrade.
        self._attr_current_option = BATTERY_MODE_LI_VOLTAGE
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
        if state and state.state in self._attr_options:
            self._attr_current_option = state.state

    async def async_select_option(self, option: str) -> None:
        if option in self._attr_options:
            self._attr_current_option = option
            self.async_write_ha_state()


class SelectBase(CoordinatorEntity, SelectEntity):
    # should_poll = True

    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._inverter_device = inverter_device

    # To link this entity to the cover device, this property must return an
    # identifiers value matching that used in the cover, but no other information such
    # as name. If name is returned, this entity will then also become a device in the
    # HA UI.
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
        # Safe: a freshly-added hub child isn't in coordinator.data until its
        # first poll. Returning {} avoids a KeyError that would crash select
        # setup / the in-place reconcile.
        return (self.coordinator.data or {}).get(
            self._inverter_device.inverter_id
        ) or {}

    # async def async_added_to_hass(self):
    #     """Run when this Entity has been added to HA."""
    #     # Sensors should also register callbacks to HA when their state changes
    #     self._inverter_device.register_callback(self.async_write_ha_state)
    #
    # async def async_will_remove_from_hass(self):
    #     """Entity being removed from hass."""
    #     # The opposite of async_added_to_hass. Remove any registered call backs here.
    #     self._inverter_device.remove_callback(self.async_write_ha_state)


def resolve_output_priority(device_data):
    # ``(... or {})`` so an offline child (no qpiri section yet) doesn't crash
    # select setup / reconcile with 'NoneType' has no attribute 'get'.
    return (device_data.get('qpiri') or {}).get('output_source_priority')


def resolve_chrage_source_priority(device_data):
    return (device_data.get('qpiri') or {}).get('charger_source_priority')


def resolve_max_utility_charging_current(device_data):
    return (device_data.get('qpiri') or {}).get('max_utility_charging_current')


class _LocalizedPrioritySelect(SelectBase):
    """Select whose options are translated for the HA UI language.

    The raw value (``UtilityFirst``, ``SBU``, …) stays available in the
    ``raw_value`` attribute so automations do not have to depend on the
    translated label.
    """

    _choices: tuple[tuple[str, dict[str, str], dict[str, str]], ...] = ()
    _raw_aliases: dict[str, str] = {}
    _attr_has_entity_name = True

    def __init__(self, inverter_device, coordinator):
        super().__init__(inverter_device, coordinator)
        self._raw_option: str | None = None

    def _language(self) -> str:
        return _ui_language(getattr(self, "hass", None))

    def _normalize_raw(self, raw) -> str | None:
        if raw is None:
            return None
        value = str(raw)
        value = self._raw_aliases.get(value, value)
        return value if any(choice[0] == value for choice in self._choices) else None

    @property
    def options(self) -> list[str]:
        language = self._language()
        return [labels[language] for _raw, labels, _desc in self._choices]

    @property
    def current_option(self) -> str | None:
        raw = self._normalize_raw(self._raw_option)
        if raw is None:
            return None
        language = self._language()
        for value, labels, _desc in self._choices:
            if value == raw:
                return labels[language]
        return None

    @property
    def extra_state_attributes(self) -> dict:
        raw = self._normalize_raw(self._raw_option)
        if raw is None:
            return {}
        language = self._language()
        for value, _labels, descriptions in self._choices:
            if value == raw:
                return {
                    "raw_value": raw,
                    "description": descriptions[language],
                }
        return {"raw_value": raw}

    def _raw_for_option(self, option: str) -> str | None:
        for value, labels, _desc in self._choices:
            if option == value or option in labels.values():
                return value
        return None


class InverterOutputPrioritySelect(_LocalizedPrioritySelect):
    _attr_translation_key = "output_priority"
    _choices = _OUTPUT_PRIORITY_CHOICES
    # Older releases exposed SolarFirst as "Solar"; keep existing YAML
    # automations working after the label/option rewrite.
    _raw_aliases = {"SolarFirst": "Solar"}

    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(inverter_device, coordinator)
        self._attr_unique_id = f"{self._inverter_device.inverter_id}_output_priority"

        if coordinator.data is not None:
            data = coordinator.data.get(self._inverter_device.inverter_id) or {}
            self._raw_option = self._normalize_raw(
                resolve_output_priority(data)
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        self._raw_option = self._normalize_raw(
            resolve_output_priority(self.data)
        )
        self.async_write_ha_state()

    async def async_select_option(self, option: str):
        raw = self._raw_for_option(option)
        if raw is None:
            return
        map_priority = {
            'UtilityFirst': OutputSourcePrioritySetting.UTILITY_FIRST,
            'SBU': OutputSourcePrioritySetting.SBU_PRIORITY,
            'Solar': OutputSourcePrioritySetting.SOLAR_FIRST,
            'SUB': OutputSourcePrioritySetting.SUB_PRIORITY,
        }
        queue = await get_command_queue(self.hass, self._inverter_device.device_data)
        result = await queue.enqueue(
            lambda: set_output_source_priority(
                self._inverter_device.device_data, map_priority[raw]
            )
        )
        if isinstance(result, dict) and result.get("error"):
            _LOGGER.warning(
                "Output priority write failed for %s: %s",
                self._inverter_device.name, result["error"],
            )
            return
        self._raw_option = raw
        self.async_write_ha_state()
        self.coordinator.force_section("qpiri")
        await self.coordinator.async_request_refresh()


class InverterChargeSourcePrioritySelect(_LocalizedPrioritySelect):
    _attr_translation_key = "charge_source_priority"
    _choices = _CHARGE_SOURCE_CHOICES

    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(inverter_device, coordinator)
        self._attr_unique_id = f"{self._inverter_device.inverter_id}_charge_source_priority"

        if coordinator.data is not None:
            data = coordinator.data.get(self._inverter_device.inverter_id) or {}
            self._raw_option = self._normalize_raw(
                resolve_chrage_source_priority(data)
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        self._raw_option = self._normalize_raw(
            resolve_chrage_source_priority(self.data)
        )
        self.async_write_ha_state()

    async def async_select_option(self, option: str):
        raw = self._raw_for_option(option)
        if raw is None:
            return
        map_priority = {
            'UtilityFirst': ChargeSourcePrioritySetting.UTILITY_FIRST,
            'SolarFirst': ChargeSourcePrioritySetting.SOLAR_FIRST,
            'SolarAndUtility': ChargeSourcePrioritySetting.SOLAR_AND_UTILITY,
            'OnlySolar': ChargeSourcePrioritySetting.ONLY_SOLAR,
        }
        queue = await get_command_queue(self.hass, self._inverter_device.device_data)
        result = await queue.enqueue(
            lambda: set_charge_source_priority(
                self._inverter_device.device_data, map_priority[raw]
            )
        )
        if isinstance(result, dict) and result.get("error"):
            _LOGGER.warning(
                "Charge source priority write failed for %s: %s",
                self._inverter_device.name, result["error"],
            )
            return
        self._raw_option = raw
        self.async_write_ha_state()
        self.coordinator.force_section("qpiri")
        await self.coordinator.async_request_refresh()


def _normalize_amps(raw) -> str | None:
    """Coerce firmware-reported current ('02.0', '030', '2.0') to canonical str(int)."""
    if raw is None:
        return None
    try:
        return str(int(float(raw)))
    except (TypeError, ValueError):
        return None


class InverterMaxUtilityChargingCurrentNumber(SelectBase):
    _attr_has_entity_name = True
    _attr_translation_key = "max_utility_charging_current"

    def __init__(self, inverter_device: InverterDevice, coordinator: DirectCoordinator):
        super().__init__(inverter_device, coordinator)
        self._attr_unique_id = f"{self._inverter_device.inverter_id}_max_utility_charging_current"
        self._raw_readback: str | None = None
        data = (coordinator.data or {}).get(
            self._inverter_device.inverter_id
        ) or {}
        self._attr_options = max_utility_charging_current_options(
            data.get("qpiri")
        )

        if coordinator.data is not None:
            raw = resolve_max_utility_charging_current(data)
            self._raw_readback = raw if raw is None else str(raw)
            normalized = _normalize_amps(raw)
            self._attr_current_option = (
                normalized if normalized in self._attr_options else None
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.data
        self._attr_options = max_utility_charging_current_options(
            data.get("qpiri")
        )
        raw = resolve_max_utility_charging_current(data)
        self._raw_readback = raw if raw is None else str(raw)
        normalized = _normalize_amps(raw)
        self._attr_current_option = (
            normalized if normalized in self._attr_options else None
        )
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "max_allowed_amps": max(
                (int(option) for option in self._attr_options), default=None
            )
        }

    async def async_select_option(self, option: str):
        if option in self._attr_options:
            amps = int(option)
            float_format = self._raw_readback is not None and '.' in self._raw_readback
            queue = await get_command_queue(self.hass, self._inverter_device.device_data)
            result = await queue.enqueue(
                lambda: set_max_utility_charge_current(
                    self._inverter_device.device_data, amps, float_format=float_format
                )
            )
            if isinstance(result, dict) and result.get("error"):
                _LOGGER.warning(
                    "Max utility charging current write failed for %s: %s",
                    self._inverter_device.name, result["error"],
                )
                return
            self._attr_current_option = option
            self.async_write_ha_state()
            # Register 333 is the lower bound of register 332: patch the
            # cached QPIRI so the number entity exposes the new minimum
            # immediately instead of after the next full poll.
            self.coordinator.update_cached_qpiri(
                self._inverter_device.inverter_id,
                max_utility_charging_current=option,
            )
            self.coordinator.force_section("qpiri")
        await self.coordinator.async_request_refresh()


class SMG2ConfigSelect(SelectBase):
    """Writable SMG-II register exposed as a translated select.

    ``data_key`` points at the QPIRI projection, ``address`` at the actual
    holding register. The raw register value is exposed as ``raw_value``
    so automations do not depend on the visible label.
    """

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
        choices: tuple,
    ):
        super().__init__(inverter_device, coordinator)
        self._key = key
        self._address = address
        self._data_key = data_key
        self._choices = choices
        self._pending_raw: int | None = None
        self._attr_unique_id = f"{self._inverter_device.inverter_id}_smg2_{key}"
        self._attr_translation_key = f"smg2_{key}"
        self._attr_icon = icon

    @property
    def _qpiri(self) -> dict:
        return self.data.get("qpiri") or {}

    def _raw(self) -> int | None:
        if self._pending_raw is not None:
            return self._pending_raw
        raw = self._qpiri.get(self._data_key)
        try:
            return int(round(float(raw)))
        except (TypeError, ValueError):
            return None

    def _label(self, value: int, language: str) -> str | None:
        for choice_value, labels, _description in self._choices:
            if choice_value == value:
                return labels[language]
        return None

    @property
    def options(self) -> list[str]:
        language = _ui_language(self.hass)
        return [labels[language] for _value, labels, _desc in self._choices]

    @property
    def current_option(self) -> str | None:
        raw = self._raw()
        if raw is None:
            return None
        return self._label(raw, _ui_language(self.hass))

    @property
    def extra_state_attributes(self) -> dict:
        raw = self._raw()
        if raw is None:
            return {}
        language = _ui_language(self.hass)
        for value, _labels, descriptions in self._choices:
            if value == raw:
                attrs = {"raw_value": raw}
                if descriptions:
                    attrs["description"] = descriptions[language]
                return attrs
        return {"raw_value": raw}

    def _raw_for_option(self, option: str) -> int | None:
        for value, labels, _description in self._choices:
            if option == str(value) or option in labels.values():
                return value
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        self._pending_raw = None
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        raw = self._raw_for_option(option)
        if raw is None:
            return
        result = await async_write_smg2_register(
            self.hass,
            self._inverter_device.device_data,
            self._address,
            raw,
        )
        if isinstance(result, dict) and result.get("error"):
            _LOGGER.warning(
                "SMG-II setting %s write failed for %s: %s",
                self._key, self._inverter_device.name, result["error"],
            )
            return
        self._pending_raw = raw
        self.async_write_ha_state()
        self.coordinator.force_section("qpiri")
        await self.coordinator.async_request_refresh()
