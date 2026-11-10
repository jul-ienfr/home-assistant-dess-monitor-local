# Contrat — Carte de registres SMG-II

**Version** : 1.0.0

**Portée** : Anenji / EASUN / ISolar SMG-II 4,2 kW et 6,2 kW, firmware SMG-II
(protocole RS232 V1.0.1). Les modèles 11 kW et 6 kW USB sont explicitement hors
contrat.

**Sources** :
- `syssi/esphome-smg-ii`, `esp32-example.yaml` et README ;
- `jul-ienfr/esphome-anenji-4.2kw-wifi`, `anenji_4kw.yaml` et PDF
  `SMG-RS232+Communication+Protocol+V1.0.1.pdf` ;
- `janas-karol/esphome-anenji-6.2kw`, `esp32-example.yaml` ;
- `PreK/esphome-anenji-11kw-native-modbus` (pour la distinction 11 kW).

## 1. Transport

| Paramètre | Valeur |
|-----------|--------|
| Physique | RS232 (MAX3232) ou RS485 (MAX485/SP3485) selon le port |
| Débit | 9600 bauds |
| Données | 8 bits |
| Parité | aucune |
| Stop | 1 bit |
| Esclave | 0x01 |
| Lecture | fonction 03 (holding registers) |
| Écriture | fonction 16 (write multiple registers) |
| Octet de poids fort | en premier (big-endian) |

## 2. Mesures

| Adresse | Entité | Type | Échelle | Unité | Accès | Notes |
|--------:|--------|------|---------|-------|:-----:|-------|
| 100 | Fault Code | U_DWORD | 1 | — | R | 2 registres |
| 108 | Warning Code | U_DWORD | 1 | — | R | 2 registres |
| 201 | Operation Mode ID | U_WORD | 1 | — | R | 0-6 |
| 202 | AC Input Voltage | S_WORD | 0,1 | V | R | |
| 203 | AC Input Frequency | S_WORD | 0,01 | Hz | R | |
| 204 | AC Input Power | S_WORD | 1 | W | R | |
| 205 | Inverter Voltage | S_WORD | 0,1 | V | R | |
| 206 | Inverter Current | S_WORD | 0,1 | A | R | |
| 207 | Inverter Frequency | S_WORD | 0,01 | Hz | R | |
| 208 | Inverter Power | S_WORD | 1 | W | R | positif = sortie |
| 209 | Inverter Charging Power | S_WORD | 1 | W | R | |
| 210 | AC Output Voltage | S_WORD | 0,1 | V | R | |
| 211 | AC Output Current | S_WORD | 0,1 | A | R | |
| 212 | AC Output Frequency | S_WORD | 0,01 | Hz | R | |
| 213 | AC Output Active Power | S_WORD | 1 | W | R | |
| 214 | AC Output Apparent Power | S_WORD | 1 | VA | R | |
| 215 | Battery Voltage | S_WORD | 0,1 | V | R | |
| 216 | Battery Current | S_WORD | 0,1 | A | R | |
| 217 | Battery Power | S_WORD | 1 | W | R | positif = charge, négatif = décharge |
| 219 | PV Voltage | S_WORD | 0,1 | V | R | |
| 220 | PV Current | S_WORD | 0,1 | A | R | |
| 223 | PV Power | S_WORD | 1 | W | R | source de l'énergie quotidienne |
| 224 | PV Charging Power | S_WORD | 1 | W | R | |
| 225 | Load | S_WORD | 1 | % | R | |
| 226 | DCDC Temperature | S_WORD | 1 | °C | R | pas de facteur |
| 227 | Inverter Temperature | S_WORD | 1 | °C | R | pas de facteur |
| 229 | Battery SOC | U_WORD | 1 | % | R | |
| 232 | Battery Current (BMS) | S_WORD | 0,1 | A | R | diagnostic |
| 233 | Inverter Charging Current | S_WORD | 0,1 | A | R | diagnostic |
| 234 | PV Charging Current | S_WORD | 0,1 | A | R | diagnostic |
| 643 | Rated Power | U_WORD | 1 | W | R | diagnostic |

## 3. Commandes

Toutes les commandes utilisent `use_write_multiple: true` (FC16). Les colonnes
« défaut 24 V » sont des valeurs de référence, pas des valeurs imposées.

| Adresse | Entité | Type | Échelle | Plage 24 V | Défaut 24 V | Notes |
|--------:|--------|------|---------|------------|-------------|-------|
| 300 | Output Mode | U_WORD | 1 | 0-4 | 0 | Single/Parallel/Phase |
| 301 | Output Priority | U_WORD | 1 | 0-3 | 2 | UTI/SOL/SBU/SUB |
| 302 | Input Voltage Range | U_WORD | 1 | 0-1 | 0 | Wide/Narrow |
| 303 | Buzzer Mode | U_WORD | 1 | 0-3 | 1 | |
| 305 | LCD Backlight | U_WORD | 1 | 0-1 | 1 | |
| 306 | LCD Auto Home | U_WORD bit0 | 1 | 0-1 | 0 | |
| 307 | Energy Saving | U_WORD bit0 | 1 | 0-1 | 0 | |
| 308 | Overload Auto Restart | U_WORD bit0 | 1 | 0-1 | 1 | |
| 309 | Over Temperature Auto Restart | U_WORD bit0 | 1 | 0-1 | 1 | |
| 310 | Overload Transfer To Bypass | U_WORD bit0 | 1 | 0-1 | 1 | |
| 313 | Battery Equalization | U_WORD bit0 | 1 | 0-1 | 0 | |
| 320 | Output Voltage Setting | U_WORD | 0,1 | 200-240 V | 230,0 V | |
| 321 | Output Frequency Setting | U_WORD | 0,01 | 50-60 Hz | 50,00 Hz | |
| 322 | Battery Type | U_WORD | 1 | 0-8 | 0 | AGM/Flooded/User/Li… |
| 323 | Battery OVP | U_WORD | 0,1 | 24-32 V | 29,2 V | à adapter 48 V |
| 324 | Max Charging Voltage | U_WORD | 0,1 | 24-30 V | 28,8 V | à adapter 48 V |
| 325 | Float Charging Voltage | U_WORD | 0,1 | 24-30 V | 27,6 V | à adapter 48 V |
| 326 | Recovery Voltage (mains) | U_WORD | 0,1 | 20-26 V | 24,0 V | à adapter 48 V |
| 327 | Low DC Cut-off (mains) | U_WORD | 0,1 | 20-26 V | 22,0 V | à adapter 48 V |
| 329 | Low DC Cut-off (off-grid) | U_WORD | 0,1 | 20-26 V | 21,0 V | à adapter 48 V |
| 331 | Charging Priority | U_WORD | 1 | 0-3 | 1 | |
| 332 | Max Charging Current | U_WORD | 0,1 | 0-120 A | 60,0 A | dépend du modèle |
| 333 | Max Mains Charging Current | U_WORD | 0,1 | 0-80 A | 30,0 A | dépend du modèle |
| 334 | Equalization Voltage | U_WORD | 0,1 | 24-30 V | 29,2 V | |
| 335 | Equalization Time | U_WORD | 1 | 0-900 min | 60 | |
| 336 | Equalization Timeout | U_WORD | 1 | 0-900 min | 120 | |
| 337 | Equalization Interval | U_WORD | 1 | 1-90 j | 30 | |
| 420 | Remote Switch | U_WORD bit0 | 1 | 0-1 | 0 | |
| 426 | Exit Fault State | U_WORD | 1 | écrire 1 | — | bouton uniquement |

## 4. Décodage des défauts (registre 100, 32 bits)

| Bit | Libellé |
|----:|---------|
| 0 | Over temperature of inverter module |
| 1 | Over temperature of DCDC module |
| 2 | Battery over voltage |
| 3 | PV module over temperature |
| 4 | Output short circuit |
| 5 | Inverter over voltage |
| 6 | Output over load |
| 7 | Bus over voltage |
| 8 | Bus soft start timed out |
| 9 | PV over current |
| 10 | PV over voltage |
| 11 | Battery over current |
| 12 | Inverter over current |
| 13 | Bus low voltage |
| 14 | Reserve |
| 15 | Inverter DC component too high |
| 16 | Reserve |
| 17 | Output current zero bias too large |
| 18 | Inverter current zero bias too large |
| 19 | Battery current zero bias too large |
| 20 | PV current zero bias too large |
| 21 | Inverter low voltage |
| 22 | Inverter negative power protection |
| 23 | Parallel host lost |
| 24 | Parallel sync signal abnormal |
| 25 | Battery type incompatible |
| 26 | Parallel versions incompatible |

## 5. Décodage des avertissements (registre 108, 32 bits)

| Bit | Libellé |
|----:|---------|
| 0 | Reserve |
| 1 | Mains waveform abnormal |
| 2 | Reserve |
| 3 | Mains low voltage |
| 4 | Mains over frequency |
| 5 | Mains low frequency |
| 6 | PV low voltage |
| 7 | Over temperature |
| 8 | Battery low voltage |
| 9 | Battery not connected |
| 10 | Overload |
| 11 | Battery Eq charging |
| 12 | Battery undervoltage |
| 13 | Output power derating |
| 14 | Fan blocked |
| 15 | PV energy too low |
| 16 | Parallel communication interrupted |
| 17 | Output mode inconsistent |
| 18 | Parallel battery voltage difference |

## 6. Cartes refusées

| Modèle | Registres distinctifs | Décision |
|--------|-----------------------|----------|
| Anenji 11 kW hybride | 338 (mains V), 254 (sortie W), 277 (batterie V), 278 (A), 280 (SOC), 351/389 (PV1/PV2) | Refusé : utiliser `PreK/esphome-anenji-11kw-native-modbus`. |
| SMG-II 6 kW variante USB-A | 80-345 | Refusé : port et carte différents ; voir syssi. |
| Axpert/Voltronic MKS | 200/201, 250-259 | Refusé : ce ne sont pas les registres SMG-II. |

## 7. Critères de conformité

- Toute mesure publiée doit provenir d'un registre de la section 2.
- Toute écriture doit provenir de la section 3 et utiliser FC16.
- Tout ajout de registre doit être accompagné d'une source et d'un test.
- Les échelles ne peuvent pas être dupliquées différemment entre lecture et
  écriture.
