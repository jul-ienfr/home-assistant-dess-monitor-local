# Démarrage rapide — Anenji ESPHome

**Objectif** : obtenir un firmware compilé, flashé et vérifié sur un onduleur
SMG-II 4,2/6,2 kW en moins de 30 minutes.

## 1. Prérequis

| Élément | Version / valeur |
|---------|------------------|
| ESPHome | 2025.12.x (validé : 2025.12.2) |
| Carte | ESP32dev (4 Mo) |
| Transceiver | MAX485/SP3485 (RS485) ou MAX3232 (RS232) |
| Alimentation | 5 V stable, 1 A |
| Home Assistant | optionnel (API native recommandée) |

Vérifier ESPHome :

```powershell
esphome version
```

## 2. Secrets

Créer `secrets.yaml` à partir de `secrets.yaml.example` :

```powershell
Copy-Item secrets.yaml.example secrets.yaml
```

Renseigner au minimum :

```yaml
wifi_ssid: "..."
wifi_password: "..."
fallback_password: "..."
api_encryption_key: "..."   # esphome dashboard secret
ota_password: "..."
```

Le serveur web est désactivé par défaut. Pour l'activer, ajouter
`web_server_username` et `web_server_password` dans `secrets.yaml`, puis
décommenter le bloc `web_server` de `anenji.yaml`.

`secrets.yaml` est ignoré par Git. Ne jamais le committer.

## 3. Câblage (résumé)

### RS485 (MAX485/SP3485)

| ESP32 | MAX485 | Onduleur |
|-------|--------|----------|
| GPIO17 | DI | — |
| GPIO16 | RO | — |
| GPIO4 | DE + /RE | — |
| 3,3 V | VCC (module 3,3 V) | — |
| GND | GND | GND |
| — | A+ | A+ |
| — | B- | B- |

> Un MAX485 alimenté en 5 V sort un RO à 5 V : utiliser un module 3,3 V
> (SP3485) ou un adaptateur de niveau. Ne pas injecter 5 V sur GPIO16.

### RS232 (MAX3232)

| ESP32 | MAX3232 | Onduleur |
|-------|---------|----------|
| GPIO17 | T1IN | — |
| GPIO16 | R1OUT | — |
| 3,3 V | VCC | — |
| GND | GND | GND |
| — | T1OUT | RX onduleur |
| — | R1IN | TX onduleur |

La broche GPIO4 n'est pas câblée en RS232 ; elle est simplement inutilisée.

## 4. Validation avant flash

Depuis la racine du dépôt :

```powershell
esphome config anenji.yaml
```

Attendu : code de sortie 0, aucune erreur de schéma, seul l'avertissement
« GPIO2 is a strapping PIN » peut apparaître.

Puis compiler :

```powershell
esphome compile anenji.yaml
```

Attendu : `Successfully created esp32 image` et un binaire dans
`.esphome/build/anenji/.pioenvs/anenji/firmware.bin`.

> **Dossier synchronisé (Nextcloud/OneDrive)** : si `uv pip list` échoue avec
> `os error -2145452027`, copier le projet dans un dossier local non synchronisé
> (par exemple `C:\Temp\anenji`) et compiler là. C'est une limitation de
> l'environnement, pas du YAML.

## 5. Flash

```powershell
esphome run anenji.yaml
```

Ou via le dashboard ESPHome : adopter le fichier `anenji.yaml`, puis « Install ».

## 6. Vérification matérielle

1. Ouvrir les logs : `esphome logs anenji.yaml`.
2. Attendre `Modbus Status: Connected` (moins de 30 s).
3. Comparer avec l'écran de l'onduleur :

| Entité | Attendu | Tolérance |
|--------|---------|-----------|
| AC Input Voltage | ~230 V | ± 2 % |
| AC Output Voltage | ~230 V | ± 2 % |
| Battery Voltage | 24-29 V (24 V) | ± 0,2 V |
| Battery Current | -150 à +150 A | ± 1 A |
| Battery SOC | 0-100 % | ± 2 % |
| PV Power | 0-5000 W | ± 5 % |
| Load | 0-100 % | ± 3 % |
| Inverter Temperature | 20-60 °C | ± 1 °C |
| DCDC Temperature | 20-60 °C | ± 1 °C |

4. Vérifier le signe : batterie en charge → `Charging Power` > 0 ;
   en décharge → `Discharging Power` > 0 et `Battery Autonomy` > 0.
5. Vérifier les diagnostics : `Device Online`, `Uptime`, `WiFi Signal`,
   `Modbus Error Count`.
6. Tester une écriture réversible : changer `Output Priority`, vérifier sur
   l'écran, puis revenir à la valeur initiale.
7. Tester un défaut : si un code est présent, vérifier que `Fault` affiche les
   libellés ; sinon, vérifier que `Fault` affiche « OK ».

## 7. Dépannage

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| `Modbus Status: Error` | A/B inversés, GND absent, DE/RE non câblé | Vérifier le câblage, inverser A/B, relier DE+/RE à GPIO4 |
| Aucune trame | Mauvaise adresse ou débit | Vérifier 0x01 et 9600 8N1 |
| Valeurs incohérentes | Mauvaise carte de registres (11 kW ?) | Consulter `PROTOCOL.md` |
| Température à 3,2 °C | Ancienne configuration | Utiliser `anenji.yaml`, pas `legacy/` |
| Écriture sans effet | FC06 au lieu de FC16 | Vérifier `use_write_multiple: true` |
| Redémarrages | Alimentation instable | Alimenter en 5 V/1 A, vérifier le buck |
| Compilation impossible | Dossier synchronisé | Compiler dans `C:\Temp\anenji` |

## 8. Retour arrière

- Conserver le binaire précédent (`firmware.bin`) avant flash.
- En cas de problème, flasher par USB le binaire connu bon.
- Le `safe_mode` revient au firmware précédent après 5 échecs de démarrage.
- Les réglages d'écriture sont bornés ; noter les valeurs avant modification.

## 9. Adaptation 48 V

Doubler les substitutions suivantes avant flash :

```yaml
battery_capacity_wh: "9600"
battery_voltage_high: "60.0"
battery_voltage_low: "42.0"
battery_ovp_min: "48.0"
battery_ovp_max: "64.0"
battery_charge_min: "48.0"
battery_charge_max: "60.0"
battery_recovery_min: "40.0"
battery_recovery_max: "52.0"
```

Ne pas flasher une configuration 24 V sur un parc 48 V : les seuils de charge et
de coupure seraient dangereux.
