# Modèle de données — Entités du firmware

**Fonctionnalité** : `001-anenji-functional`

Ce document décrit les objets manipulés par la configuration, indépendamment du
YAML. Les adresses et facteurs exacts sont dans
[`contracts/register-map.md`](contracts/register-map.md).

## 1. Appareil (Device)

| Attribut | Valeur | Règle |
|----------|--------|-------|
| `name` | `anenji` | minuscules, sans espace |
| `friendly_name` | `Onduleur Van Master` | libre |
| `board` | `esp32dev` | 4 Mo minimum |
| `framework` | Arduino | compatible `cpu_frequency` |
| `modbus_address` | `0x01` | doit correspondre à l'onduleur |
| `uart` | 9600, 8N1, GPIO17 TX / GPIO16 RX | 3,3 V |
| `de_re_pin` | GPIO4 | RS485 uniquement, non câblé en RS232 |
| `battery_nominal` | 24 V (défaut) | 48 V via substitutions |

**Invariants** :
- L'adresse Modbus et le débit ne peuvent pas être changés sans mise à jour de
  `PROTOCOL.md`.
- Aucun secret n'est stocké dans le YAML.

## 2. Mesure (Measurement)

Une mesure est une valeur lue en lecture seule sur un registre `holding`.

| Attribut | Type | Exemple | Règle |
|----------|------|---------|-------|
| `name` | texte | `Battery Voltage` | unique dans Home Assistant |
| `id` | identifiant | `battery_voltage` | unique dans le YAML |
| `address` | entier | 215 | doit exister dans le contrat |
| `value_type` | enum | `S_WORD`, `U_WORD`, `U_DWORD` | cohérent avec le protocole |
| `scale` | réel | 0,1 | 1 si le registre est déjà dans l'unité |
| `unit` | texte | `V`, `A`, `W`, `°C`, `%` | cohérent avec `device_class` |
| `device_class` | enum HA | `voltage`, `battery` | optionnel mais recommandé |
| `state_class` | `measurement` | — | requis pour les statistiques HA |
| `range` | min/max | 15-35 V | validation physique |

**Règles de validation** :
- Une mesure hors plage physique est ignorée (`NAN`) plutôt que publiée.
- Les températures sont en °C sans facteur.
- La puissance batterie suit la convention positive = charge.
- L'autonomie n'est calculée que si la puissance est strictement négative.

## 3. Commande (Control)

Une commande écrit un registre `holding` et doit être réversible.

| Attribut | Type | Exemple | Règle |
|----------|------|---------|-------|
| `name` | texte | `Output Priority` | explicite |
| `address` | entier | 301 | doit exister dans le contrat |
| `write_mode` | `FC16` | `use_write_multiple: true` | obligatoire |
| `min` / `max` | réel | 0 / 120 | bornes physiques |
| `step` | réel | 0,1 | précision réelle |
| `scale` | réel | 0,1 | lecture et écriture cohérentes |
| `default` | valeur | selon onduleur | conservatrice |
| `critical` | booléen | oui pour tensions | test matériel obligatoire |

**Règles de validation** :
- Toute commande critique doit être testée avec une valeur proche de la valeur
  actuelle, puis ramenée à sa valeur initiale.
- Une commande ne doit jamais écrire une valeur hors de `min`/`max`.
- Le bouton « Exit Fault State » écrit 1 au registre 426 uniquement sur action
  utilisateur.

## 4. Diagnostic (Diagnostic)

| Entité | Source | Rôle |
|--------|--------|------|
| `Operation Mode` | registre 201 + table | comprendre l'état (mains, off-grid, bypass, défaut…) |
| `Fault Code` | registre 100 (U_DWORD) | code brut 32 bits |
| `Fault` | registre 100 + table | libellés lisibles |
| `Warning Code` | registre 108 (U_DWORD) | code brut 32 bits |
| `Warning` | registre 108 + table | libellés lisibles |
| `Modbus Status` | `status_has_error()` | connecté / erreur |
| `Modbus Error Count` | front montant de l'erreur | compteur de coupures |
| `Device Online` | `binary_sensor.status` | présence réseau |
| `Uptime` | composant `uptime` | stabilité |
| `WiFi Signal` | composant `wifi_signal` | qualité radio |

**Règles** :
- Un code 0 affiche « OK ».
- Un bit inconnu ne doit pas faire planter le décodage ; il est ignoré ou affiché
  comme inconnu.
- Le statut ne doit pas provoquer de redémarrage.

## 5. Énergie (Energy)

| Attribut | Valeur |
|----------|--------|
| source | `PV Power` (registre 223) |
| intégration | `total_daily_energy` |
| unité | kWh |
| restauration | NVS (`restore: true`) |
| remise à zéro | quotidienne, fuseau `Europe/Paris` |

## 6. Relations

```text
Appareil 1 ─── * Mesure
Appareil 1 ─── * Commande
Appareil 1 ─── * Diagnostic
Appareil 1 ─── 1 Énergie (dérivée de PV Power)
Mesure "Battery Power" ─── alimente ─── Charging/Discharging/Autonomy
Mesure "Battery SOC" ─── alimente ─── Autonomy
Commande "Battery Capacity" ─── alimente ─── Autonomy
```

## 7. Contraintes de cohérence

- Toute entité doit avoir un `id` unique et un `name` unique.
- Un registre ne peut pas être à la fois mesure et commande avec des échelles
  différentes.
- Les entités de commande doivent avoir `entity_category: config`.
- Les entités de diagnostic doivent avoir `entity_category: diagnostic`.
- Les entités calculées doivent avoir `update_interval: never` et être mises à
  jour par `component.update` ou un intervalle explicite.
