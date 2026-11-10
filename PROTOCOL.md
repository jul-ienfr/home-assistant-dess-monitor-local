# Protocole Modbus — Anenji SMG-II

**Version** : 1.1.0 — 2026-11-10

Ce document décrit la carte de registres utilisée par `anenji.yaml`. Il est la
référence du dépôt : toute modification du YAML doit être cohérente avec cette
page.

> **Modèles concernés** : Anenji / EASUN / ISolar SMG-II 4,2 kW et 6,2 kW.
> **Non concernés** : Anenji 11 kW (registres 277+), variante 6 kW USB-A
> (registres 80-345), Axpert/Voltronic MKS (registres 200/250-259).

## 1. Liaison

| Paramètre | Valeur |
|-----------|--------|
| Type | Modbus RTU |
| Physique | RS232 (MAX3232) ou RS485 (MAX485/SP3485) selon le port de l'onduleur |
| Débit | 9600 bauds |
| Format | 8N1 |
| Esclave | `0x01` |
| Lecture | fonction 03 (holding registers) |
| Écriture | fonction 16 (write multiple registers) |
| Ordre des octets | big-endian (poids fort en premier) |
| Délai | `send_wait_time: 200ms`, `command_throttle: 200ms` |

L'onduleur peut exposer un port RJ45 (RS232), un port USB-A (variante 6 kW) ou
des bornes RS485. Vérifier le modèle avant de câbler. Voir [WIRING.md](WIRING.md).

## 2. Mesures

| Adresse | Entité | Type | Échelle | Unité |
|--------:|--------|------|---------|-------|
| 100 | Fault Code (2 regs) | U_DWORD | 1 | — |
| 108 | Warning Code (2 regs) | U_DWORD | 1 | — |
| 201 | Operation Mode | U_WORD | 1 | — |
| 202 | AC Input Voltage | S_WORD | 0,1 | V |
| 203 | AC Input Frequency | S_WORD | 0,01 | Hz |
| 204 | AC Input Power | S_WORD | 1 | W |
| 205 | Inverter Voltage | S_WORD | 0,1 | V |
| 206 | Inverter Current | S_WORD | 0,1 | A |
| 207 | Inverter Frequency | S_WORD | 0,01 | Hz |
| 208 | Inverter Power | S_WORD | 1 | W |
| 209 | Inverter Charging Power | S_WORD | 1 | W |
| 210 | AC Output Voltage | S_WORD | 0,1 | V |
| 211 | AC Output Current | S_WORD | 0,1 | A |
| 212 | AC Output Frequency | S_WORD | 0,01 | Hz |
| 213 | AC Output Active Power | S_WORD | 1 | W |
| 214 | AC Output Apparent Power | S_WORD | 1 | VA |
| 215 | Battery Voltage | S_WORD | 0,1 | V |
| 216 | Battery Current | S_WORD | 0,1 | A |
| 217 | Battery Power | S_WORD | 1 | W |
| 219 | PV Voltage | S_WORD | 0,1 | V |
| 220 | PV Current | S_WORD | 0,1 | A |
| 223 | PV Power | S_WORD | 1 | W |
| 224 | PV Charging Power | S_WORD | 1 | W |
| 225 | Load | S_WORD | 1 | % |
| 226 | DCDC Temperature | S_WORD | 1 | °C |
| 227 | Inverter Temperature | S_WORD | 1 | °C |
| 229 | Battery SOC | U_WORD | 1 | % |
| 232 | Battery Current (BMS) | S_WORD | 0,1 | A |
| 233 | Inverter Charging Current | S_WORD | 0,1 | A |
| 234 | PV Charging Current | S_WORD | 0,1 | A |
| 643 | Rated Power | U_WORD | 1 | W |

### Convention batterie

Le registre 217 suit la convention **positive = charge**, **négative =
décharge**. C'est la convention du protocole SMG-II et des projets syssi. Elle
est utilisée pour :

- `Charging Power` : `max(217, 0)` ;
- `Discharging Power` : `max(-217, 0)` ;
- `Battery Autonomy` : calculée uniquement si 217 < 0.

### Températures

Les registres 226 et 227 sont déjà en °C (entiers). **Ne pas appliquer de facteur
0,1** : cela afficherait 3,2 °C au lieu de 32 °C.

## 3. Commandes

Toutes les écritures utilisent la fonction 16 (`use_write_multiple: true`). Les
plages sont celles de la configuration 24 V ; doubler les tensions pour un parc
48 V.

| Adresse | Entité | Type | Échelle | Plage | Notes |
|--------:|--------|------|---------|-------|-------|
| 300 | Output Mode | U_WORD | 1 | 0 | **Single uniquement** dans ce YAML : les modes Parallel / Phase P1-P3 exigent plusieurs onduleurs câblés |
| 301 | Output Priority | U_WORD | 1 | 0-3 | UTI, SOL, SBU, SUB |
| 302 | Input Voltage Range | U_WORD | 1 | 0-1 | Wide/Narrow |
| 303 | Buzzer Mode | U_WORD | 1 | 0-3 | |
| 305 | LCD Backlight | U_WORD | 1 | 0-1 | |
| 306 | LCD Auto Home | U_WORD bit0 | 1 | 0-1 | |
| 307 | Energy Saving | U_WORD bit0 | 1 | 0-1 | |
| 308 | Overload Auto Restart | U_WORD bit0 | 1 | 0-1 | |
| 309 | Over Temperature Auto Restart | U_WORD bit0 | 1 | 0-1 | |
| 310 | Overload Transfer To Bypass | U_WORD bit0 | 1 | 0-1 | |
| 313 | Battery Equalization | U_WORD bit0 | 1 | 0-1 | |
| 320 | Output Voltage Setting | U_WORD | 0,1 | 220 / 230 / 240 V | select, pas de valeur continue |
| 321 | Output Frequency Setting | U_WORD | 0,01 | 50 / 60 Hz | select, pas de valeur continue |
| 322 | Battery Type | U_WORD | 1 | 0-8 | AGM, Flooded, User, Li1-Li4, Lib |
| 323 | Battery OVP | U_WORD | 0,1 | 28-32 V | doit rester **au-dessus** de 324 |
| 324 | Max Charging Voltage | U_WORD | 0,1 | 24-30 V | |
| 325 | Float Charging Voltage | U_WORD | 0,1 | 24-30 V | |
| 326 | Recovery Voltage (mains) | U_WORD | 0,1 | 20-26 V | |
| 327 | Low DC Cut-off (mains) | U_WORD | 0,1 | 20-26 V | |
| 329 | Low DC Cut-off (off-grid) | U_WORD | 0,1 | 20-26 V | |
| 331 | Charging Priority | U_WORD | 1 | 0-3 | |
| 332 | Max Charging Current | U_WORD | 0,1 | 0-100 A | maximum réel du modèle 4,2 kW (lu au registre : 100,0 A) |
| 333 | Max Mains Charging Current | U_WORD | 0,1 | 0-80 A | maximum réel du modèle 4,2 kW (lu au registre : 80,0 A) |
| 334 | Equalization Voltage | U_WORD | 0,1 | 24-30 V | |
| 335 | Equalization Time | U_WORD | 1 | 0-900 min | |
| 336 | Equalization Timeout | U_WORD | 1 | 0-900 min | |
| 337 | Equalization Interval | U_WORD | 1 | 1-90 j | |
| 341 | SOC Point Back To Utility | U_WORD | 1 | 31-100 % | doit rester **au-dessus** de 343 |
| 342 | SOC Point Back To Battery | U_WORD | 1 | 60-100 % | doit rester **au-dessus** de 341 |
| 343 | Low DC Cut-off SOC | U_WORD | 1 | 3-30 % | |
| 406 | Turn On Mode | U_WORD | 1 | 0-2 | Local+remote, Local only, Remote only |
| 420 | Remote Output Enable | U_WORD bit0 | 1 | 0-1 | 0 = shutdown, 1 = turn-on |
| 426 | Exit Fault State | U_WORD | 1 | écrire 1 | bouton ; lecture toujours 0 |

### Validation par le firmware

Le firmware SMG-II **refuse** les valeurs hors plage avec une exception
Modbus 03 (Illegal Data Value) et conserve l'ancienne valeur. Vérifié sur
l'appareil : `303=4`, `305=2` et `337=91` sont rejetés. Les bornes du YAML
restent nécessaires pour empêcher la saisie avant l'envoi et pour documenter
les limites ; elles ne remplacent pas cette validation.

### Cohérence inter-paramètres

Les bornes individuelles ne suffisent pas : `OVP=28,0 V` et `bulk=30,0 V`
sont chacune dans leur plage mais incoherentes. Le diagnostic
`Configuration Incoherent` vérifie en continu :

- `323 > 324 > 325 > 326 > 327` ;
- `332 <= 100 A` et `333 <= 80 A` ;
- `343 < 341 < 342` et `342 >= 60 %`.

### Écritures vérifiées sur l'appareil

Les 32 registres configurables (300-420) ont été écrits en FC16 avec leur
valeur courante puis relus : **32/32 identiques**. Un vrai changement a été
validé sur `305` (0 → 1 → 0). `426` renvoie l'exception 03 quand aucun défaut
n'est actif, ce qui est le comportement attendu.

### Écriture correcte

```yaml
- platform: modbus_controller
  use_write_multiple: true
  address: 324
  value_type: U_WORD
  lambda: "return x * 0.1f;"        # lecture : registre -> volts
  write_lambda: "return x * 10.0f;" # écriture : volts -> registre
```

Ne pas pousser d'octets dans `payload` : `write_lambda` doit **retourner** la
valeur entière à écrire.

## 4. Défauts et avertissements

Les registres 100 et 108 sont des masques 32 bits (2 registres). La
correspondance complète des bits est dans
[`specs/001-anenji-functional/contracts/register-map.md`](specs/001-anenji-functional/contracts/register-map.md).

## 5. Variantes non supportées

| Modèle | Registres | Pourquoi |
|--------|-----------|----------|
| Anenji 11 kW | 338, 254, 277-281, 351, 389 | Carte différente ; voir `PreK/esphome-anenji-11kw-native-modbus`. |
| SMG-II 6 kW USB-A | 80-345 | Port et carte différents ; voir `syssi/esphome-smg-ii`. |
| Axpert/Voltronic MKS | 200/201, 250-259 | Ce ne sont pas les registres SMG-II. |

## 6. Sources

- [syssi/esphome-smg-ii](https://github.com/syssi/esphome-smg-ii) — projet
  canonique et PDF `SMG-RS232+Communication+Protocol+V1.0.1.pdf`.
- [jul-ienfr/esphome-anenji-4.2kw-wifi](https://github.com/jul-ienfr/esphome-anenji-4.2kw-wifi)
  — fork historique, dérivé de syssi ; **non utilisé comme source de vérité**.
- [janas-karol/esphome-anenji-6.2kw](https://github.com/janas-karol/esphome-anenji-6.2kw)
  — fork 6,2 kW.
- [PreK/esphome-anenji-11kw-native-modbus](https://github.com/PreK/esphome-anenji-11kw-native-modbus)
  — carte 11 kW.
- [attilagyurman/anenji-local-modbus](https://github.com/attilagyurman/anenji-local-modbus)
  — relevé de registres 11 kW.
