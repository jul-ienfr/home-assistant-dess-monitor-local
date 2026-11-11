"""SMG-II fault and warning bit maps.

The SMG-II Modbus map exposes two 32-bit status words:

* register ``100`` (2 words) — latched faults
* register ``108`` (2 words) — warnings

The bit assignment below comes from the published SMG-II register map
(the same map used by the ``syssi`` SMG-II reference).  Keeping the
keys stable lets the Home Assistant entities and automations refer to
``pv_low_voltage`` instead of a firmware-specific hex code, while the
translation tables provide a human-readable label and an actionable hint
in the user's Home Assistant language.

Only English and French are bundled for the dynamic (state) text.  Home
Assistant entity names use the regular ``strings.json`` translations and
fall back to English for other languages.
"""
from __future__ import annotations

# bit -> (stable key, English label)
WARNING_BITS: dict[int, tuple[str, str]] = {
    1: ("mains_waveform_abnormal", "Mains waveform abnormal"),
    3: ("mains_low_voltage", "Mains low voltage"),
    4: ("mains_over_frequency", "Mains over frequency"),
    5: ("mains_low_frequency", "Mains low frequency"),
    6: ("pv_low_voltage", "PV low voltage"),
    7: ("over_temperature", "Over temperature"),
    8: ("battery_low_alarm", "Battery low voltage"),
    9: ("battery_open", "Battery is not connected"),
    10: ("overload", "Overload"),
    11: ("battery_eq_charging", "Battery equalize charging"),
    12: ("battery_undervoltage", "Battery undervoltage"),
    13: ("power_limit", "Output power derating"),
    14: ("fan_locked", "Fan blocked"),
    15: ("pv_energy_low", "PV energy too low to be used"),
    16: ("parallel_comm_interrupted", "Parallel communication interrupted"),
    17: (
        "parallel_mode_inconsistent",
        "Output mode inconsistent between single and parallel systems",
    ),
    18: (
        "parallel_battery_diff",
        "Battery voltage difference in parallel system too large",
    ),
}

# bit -> (stable key, English label)
FAULT_BITS: dict[int, tuple[str, str]] = {
    0: ("inverter_over_temperature", "Over temperature of inverter module"),
    1: ("dcdc_over_temperature", "Over temperature of DC-DC module"),
    2: ("battery_voltage_high", "Battery over voltage"),
    3: ("pv_over_temperature", "PV module over temperature"),
    4: ("opv_short", "Output short circuit"),
    5: ("inverter_voltage_too_high", "Inverter over voltage"),
    6: ("overload", "Output overload"),
    7: ("bus_over", "Bus over voltage"),
    8: ("bus_soft_fail", "Bus soft start timed out"),
    9: ("pv_over_current", "PV over current"),
    10: ("pv_voltage_high", "PV over voltage"),
    11: ("battery_over_current", "Battery over current"),
    12: ("inverter_over_current", "Inverter over current"),
    13: ("bus_under", "Bus low voltage"),
    15: ("inverter_dc_component_high", "Inverter DC component too high"),
    17: ("output_current_bias", "Output current zero bias too large"),
    18: ("inverter_current_bias", "Inverter current zero bias too large"),
    19: ("battery_current_bias", "Battery current zero bias too large"),
    20: ("pv_current_bias", "PV current zero bias too large"),
    21: ("inverter_voltage_too_low", "Inverter low voltage"),
    22: ("inverter_negative_power", "Inverter negative power protection"),
    23: ("parallel_host_lost", "Host in parallel system lost"),
    24: (
        "parallel_sync_abnormal",
        "Synchronization signal abnormal in parallel system",
    ),
    25: ("battery_type_incompatible", "Battery type incompatible"),
    26: ("parallel_version_incompatible", "Parallel versions incompatible"),
}

WARNING_BY_KEY: dict[str, tuple[int, str]] = {
    key: (bit, english) for bit, (key, english) in WARNING_BITS.items()
}
FAULT_BY_KEY: dict[str, tuple[int, str]] = {
    key: (bit, english) for bit, (key, english) in FAULT_BITS.items()
}

# French labels for the dynamic state text / attributes.  The English
# labels live in the bit maps above and are the fallback for any language
# that is not translated yet.
WARNING_FR: dict[str, str] = {
    "mains_waveform_abnormal": "Forme d'onde du réseau anormale",
    "mains_low_voltage": "Tension réseau trop basse",
    "mains_over_frequency": "Fréquence réseau trop élevée",
    "mains_low_frequency": "Fréquence réseau trop basse",
    "pv_low_voltage": "Tension PV trop basse",
    "over_temperature": "Surchauffe",
    "battery_low_alarm": "Tension batterie trop basse",
    "battery_open": "Batterie non connectée",
    "overload": "Surcharge",
    "battery_eq_charging": "Charge d'égalisation batterie",
    "battery_undervoltage": "Sous-tension batterie",
    "power_limit": "Réduction de puissance de sortie",
    "fan_locked": "Ventilateur bloqué",
    "pv_energy_low": "Énergie PV trop faible pour être utilisée",
    "parallel_comm_interrupted": "Communication parallèle interrompue",
    "parallel_mode_inconsistent": (
        "Mode de sortie incohérent entre systèmes simple et parallèle"
    ),
    "parallel_battery_diff": (
        "Écart de tension batterie trop important dans le système parallèle"
    ),
}

FAULT_FR: dict[str, str] = {
    "inverter_over_temperature": "Surchauffe du module onduleur",
    "dcdc_over_temperature": "Surchauffe du module DC-DC",
    "battery_voltage_high": "Surtension batterie",
    "pv_over_temperature": "Surchauffe du module PV",
    "opv_short": "Court-circuit de sortie",
    "inverter_voltage_too_high": "Surtension onduleur",
    "overload": "Surcharge de sortie",
    "bus_over": "Surtension du bus",
    "bus_soft_fail": "Démarrage progressif du bus expiré",
    "pv_over_current": "Surintensité PV",
    "pv_voltage_high": "Surtension PV",
    "battery_over_current": "Surintensité batterie",
    "inverter_over_current": "Surintensité onduleur",
    "bus_under": "Sous-tension du bus",
    "inverter_dc_component_high": "Composante DC de l'onduleur trop élevée",
    "output_current_bias": "Décalage zéro du courant de sortie trop important",
    "inverter_current_bias": "Décalage zéro du courant onduleur trop important",
    "battery_current_bias": "Décalage zéro du courant batterie trop important",
    "pv_current_bias": "Décalage zéro du courant PV trop important",
    "inverter_voltage_too_low": "Sous-tension onduleur",
    "inverter_negative_power": "Protection puissance négative de l'onduleur",
    "parallel_host_lost": "Perte de l'hôte du système parallèle",
    "parallel_sync_abnormal": (
        "Signal de synchronisation anormal dans le système parallèle"
    ),
    "battery_type_incompatible": "Type de batterie incompatible",
    "parallel_version_incompatible": "Versions parallèles incompatibles",
}

WARNING_ADVICE: dict[str, dict[str, str]] = {
    "mains_waveform_abnormal": {
        "en": "Check the grid supply and AC input wiring; the inverter may switch to battery.",
        "fr": "Vérifiez l'alimentation secteur et le câblage d'entrée AC ; l'onduleur peut passer sur batterie.",
    },
    "mains_low_voltage": {
        "en": "Grid voltage is below the accepted range. The inverter may switch to battery or bypass; check the grid supply.",
        "fr": "La tension secteur est sous la plage acceptée. L'onduleur peut passer sur batterie ou en bypass ; vérifiez l'alimentation réseau.",
    },
    "mains_over_frequency": {
        "en": "Grid frequency is too high. Check the grid supply; the inverter may switch to battery or bypass.",
        "fr": "La fréquence secteur est trop élevée. Vérifiez le réseau ; l'onduleur peut passer sur batterie ou en bypass.",
    },
    "mains_low_frequency": {
        "en": "Grid frequency is too low. Check the grid supply; the inverter may switch to battery or bypass.",
        "fr": "La fréquence secteur est trop basse. Vérifiez le réseau ; l'onduleur peut passer sur batterie ou en bypass.",
    },
    "pv_low_voltage": {
        "en": "PV voltage is below the start threshold. This is normal at night or in deep shade; check the PV strings and wiring if it persists in daylight.",
        "fr": "La tension PV est sous le seuil de démarrage. C'est normal la nuit ou par ombrage fort ; vérifiez les chaînes PV et le câblage si cela persiste en plein jour.",
    },
    "over_temperature": {
        "en": "Reduce the load or improve ventilation and clean the airflow path around the inverter.",
        "fr": "Réduisez la charge ou améliorez la ventilation et nettoyez le passage d'air autour de l'onduleur.",
    },
    "battery_low_alarm": {
        "en": "Battery voltage is low. Recharge from grid or solar and check the low-voltage cutoff setting.",
        "fr": "La tension batterie est basse. Rechargez depuis le réseau ou le solaire et vérifiez le seuil de coupure basse.",
    },
    "battery_open": {
        "en": "The inverter does not see the battery. Check the battery breaker, fuse and DC cables.",
        "fr": "L'onduleur ne voit pas la batterie. Vérifiez le disjoncteur batterie, le fusible et les câbles DC.",
    },
    "overload": {
        "en": "The load exceeds the inverter rating. Reduce the load or move some circuits to the grid.",
        "fr": "La charge dépasse la capacité de l'onduleur. Réduisez la charge ou basculez certains circuits sur le réseau.",
    },
    "battery_eq_charging": {
        "en": "Equalisation charging is active; this is normal for lead-acid batteries.",
        "fr": "La charge d'égalisation est active ; c'est normal pour des batteries plomb-acide.",
    },
    "battery_undervoltage": {
        "en": "Battery voltage is below the warning threshold. Recharge and check the battery or BMS.",
        "fr": "La tension batterie est sous le seuil d'alerte. Rechargez et vérifiez la batterie ou le BMS.",
    },
    "power_limit": {
        "en": "Output power is being limited (temperature or overload). Reduce the load and check ventilation.",
        "fr": "La puissance de sortie est limitée (température ou surcharge). Réduisez la charge et vérifiez la ventilation.",
    },
    "fan_locked": {
        "en": "The fan is blocked or failed. Clean or replace it before running at high load.",
        "fr": "Le ventilateur est bloqué ou en panne. Nettoyez-le ou remplacez-le avant de fonctionner à forte charge.",
    },
    "pv_energy_low": {
        "en": "PV production is too low to be used. This is normal at night or in low light.",
        "fr": "La production PV est trop faible pour être utilisée. C'est normal la nuit ou par faible ensoleillement.",
    },
    "parallel_comm_interrupted": {
        "en": "Check the parallel communication cable between the inverters.",
        "fr": "Vérifiez le câble de communication parallèle entre les onduleurs.",
    },
    "parallel_mode_inconsistent": {
        "en": "All parallel inverters must use the same output mode. Check their settings.",
        "fr": "Tous les onduleurs en parallèle doivent utiliser le même mode de sortie. Vérifiez leurs réglages.",
    },
    "parallel_battery_diff": {
        "en": "Battery voltages in the parallel system differ too much. Check battery wiring and breakers.",
        "fr": "Les tensions des batteries du système parallèle diffèrent trop. Vérifiez le câblage et les disjoncteurs.",
    },
}

FAULT_ADVICE: dict[str, dict[str, str]] = {
    "inverter_over_temperature": {
        "en": "Stop the inverter, reduce the load and clean or check the ventilation. Restart after it cools. Service the unit if the fault returns.",
        "fr": "Arrêtez l'onduleur, réduisez la charge et nettoyez ou vérifiez la ventilation. Redémarrez après refroidissement. Faites réviser l'appareil si le défaut revient.",
    },
    "dcdc_over_temperature": {
        "en": "Reduce the load and improve ventilation around the DC-DC stage. Service the unit if the fault returns.",
        "fr": "Réduisez la charge et améliorez la ventilation autour de l'étage DC-DC. Faites réviser l'appareil si le défaut revient.",
    },
    "battery_voltage_high": {
        "en": "Stop charging and check the battery voltage and charger settings. Disconnect the battery if the voltage keeps rising.",
        "fr": "Arrêtez la charge et vérifiez la tension batterie et les réglages du chargeur. Déconnectez la batterie si la tension continue de monter.",
    },
    "pv_over_temperature": {
        "en": "Reduce PV input or improve ventilation. Check that the PV array is within the inverter limits.",
        "fr": "Réduisez l'entrée PV ou améliorez la ventilation. Vérifiez que le champ PV respecte les limites de l'onduleur.",
    },
    "opv_short": {
        "en": "Remove the load and check the AC output wiring for a short circuit before resetting the fault.",
        "fr": "Retirez la charge et vérifiez le câblage de sortie AC avant de réarmer le défaut.",
    },
    "inverter_voltage_too_high": {
        "en": "Internal inverter fault. Restart the unit; service it if the fault returns.",
        "fr": "Défaut interne de l'onduleur. Redémarrez l'appareil ; faites-le réviser si le défaut revient.",
    },
    "overload": {
        "en": "Reduce the load immediately. Check for a shorted appliance before restarting.",
        "fr": "Réduisez immédiatement la charge. Vérifiez qu'aucun appareil n'est en court-circuit avant de redémarrer.",
    },
    "bus_over": {
        "en": "Internal bus fault. Restart the inverter; service it if the fault returns.",
        "fr": "Défaut interne du bus. Redémarrez l'onduleur ; faites-le réviser si le défaut revient.",
    },
    "bus_soft_fail": {
        "en": "The internal bus did not start correctly. Restart the inverter; service it if the fault returns.",
        "fr": "Le bus interne n'a pas démarré correctement. Redémarrez l'onduleur ; faites-le réviser si le défaut revient.",
    },
    "pv_over_current": {
        "en": "Check the PV string current and orientation against the inverter limit. Disconnect PV before servicing.",
        "fr": "Vérifiez le courant des chaînes PV et leur orientation par rapport à la limite de l'onduleur. Déconnectez le PV avant toute intervention.",
    },
    "pv_voltage_high": {
        "en": "The PV string voltage exceeds the inverter limit. Disconnect PV and reconfigure the strings.",
        "fr": "La tension des chaînes PV dépasse la limite de l'onduleur. Déconnectez le PV et reconfigurez les chaînes.",
    },
    "battery_over_current": {
        "en": "Check the battery wiring and reduce the load or charge current.",
        "fr": "Vérifiez le câblage batterie et réduisez la charge ou le courant de charge.",
    },
    "inverter_over_current": {
        "en": "Reduce the load. Service the inverter if the fault returns at low load.",
        "fr": "Réduisez la charge. Faites réviser l'onduleur si le défaut revient à faible charge.",
    },
    "bus_under": {
        "en": "Internal bus fault. Restart the inverter; service it if the fault returns.",
        "fr": "Défaut interne du bus. Redémarrez l'onduleur ; faites-le réviser si le défaut revient.",
    },
    "inverter_dc_component_high": {
        "en": "Internal inverter fault. Service the unit.",
        "fr": "Défaut interne de l'onduleur. Faites réviser l'appareil.",
    },
    "output_current_bias": {
        "en": "Internal current-sensor calibration fault. Service the unit.",
        "fr": "Défaut d'étalonnage du capteur de courant de sortie. Faites réviser l'appareil.",
    },
    "inverter_current_bias": {
        "en": "Internal current-sensor calibration fault. Service the unit.",
        "fr": "Défaut d'étalonnage du capteur de courant onduleur. Faites réviser l'appareil.",
    },
    "battery_current_bias": {
        "en": "Internal current-sensor calibration fault. Service the unit.",
        "fr": "Défaut d'étalonnage du capteur de courant batterie. Faites réviser l'appareil.",
    },
    "pv_current_bias": {
        "en": "Internal current-sensor calibration fault. Service the unit.",
        "fr": "Défaut d'étalonnage du capteur de courant PV. Faites réviser l'appareil.",
    },
    "inverter_voltage_too_low": {
        "en": "Internal inverter fault. Restart the unit; service it if the fault returns.",
        "fr": "Défaut interne de l'onduleur. Redémarrez l'appareil ; faites-le réviser si le défaut revient.",
    },
    "inverter_negative_power": {
        "en": "Internal inverter fault. Service the unit.",
        "fr": "Défaut interne de l'onduleur. Faites réviser l'appareil.",
    },
    "parallel_host_lost": {
        "en": "Check the parallel communication cables and that the host inverter is powered.",
        "fr": "Vérifiez les câbles de communication parallèle et que l'onduleur maître est alimenté.",
    },
    "parallel_sync_abnormal": {
        "en": "Check the parallel communication cables between all inverters.",
        "fr": "Vérifiez les câbles de communication parallèle entre tous les onduleurs.",
    },
    "battery_type_incompatible": {
        "en": "Set the correct battery type in the inverter settings.",
        "fr": "Sélectionnez le bon type de batterie dans les réglages de l'onduleur.",
    },
    "parallel_version_incompatible": {
        "en": "Update all parallel inverters to the same firmware version.",
        "fr": "Mettez à jour tous les onduleurs parallèles avec la même version de firmware.",
    },
}

SUPPORTED_LANGUAGES = ("en", "fr")


def normalize_language(language: str | None) -> str:
    """Return a supported two-letter language code, defaulting to English."""
    code = (language or "en").replace("_", "-").split("-", 1)[0].lower()
    return code if code in SUPPORTED_LANGUAGES else "en"


def decode_bits(code: int, bits: dict[int, tuple[str, str]]) -> list[str]:
    """Return the stable keys of every set bit, in ascending bit order."""
    return [
        key
        for bit, (key, _english) in sorted(bits.items())
        if code & (1 << bit)
    ]


def warning_keys(code: int | None) -> list[str]:
    return decode_bits(int(code or 0), WARNING_BITS)


def fault_keys(code: int | None) -> list[str]:
    return decode_bits(int(code or 0), FAULT_BITS)


def warning_label(key: str, language: str | None = None) -> str:
    if normalize_language(language) == "fr":
        return WARNING_FR.get(key, WARNING_BY_KEY.get(key, (0, key))[1])
    return WARNING_BY_KEY.get(key, (0, key))[1]


def fault_label(key: str, language: str | None = None) -> str:
    if normalize_language(language) == "fr":
        return FAULT_FR.get(key, FAULT_BY_KEY.get(key, (0, key))[1])
    return FAULT_BY_KEY.get(key, (0, key))[1]


def warning_advice(key: str, language: str | None = None) -> str | None:
    return WARNING_ADVICE.get(key, {}).get(normalize_language(language))


def fault_advice(key: str, language: str | None = None) -> str | None:
    return FAULT_ADVICE.get(key, {}).get(normalize_language(language))
