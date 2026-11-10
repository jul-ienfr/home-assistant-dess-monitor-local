# Anenji ESPHome — Onduleur Van Master

Firmware ESPHome pour surveiller et piloter un onduleur solaire hybride
**Anenji / EASUN / ISolar SMG-II** (4,2 kW / 6,2 kW) via Modbus RTU, depuis Home
Assistant ou en autonomie.

> **État** : configuration validée avec ESPHome 2025.12.2 (`esphome config` et
> `esphome compile`). Le test sur onduleur réel reste à effectuer avec la
> checklist [`quickstart.md`](specs/001-anenji-functional/quickstart.md).

## Sommaire

- [Matériel](#matériel)
- [Fonctionnalités](#fonctionnalités)
- [Démarrage rapide](#démarrage-rapide)
- [Sans ESP32](#sans-esp32)
- [Carte des registres](#carte-des-registres)
- [Sécurité](#sécurité)
- [Variantes et limites](#variantes-et-limites)
- [Structure du dépôt](#structure-du-dépôt)
- [Dépannage](#dépannage)
- [Sources](#sources)

## Matériel

| Composant | Description | Prix estimé |
|-----------|-------------|-------------|
| ESP32dev | Carte ESP32-WROOM, 4 Mo | 5-8 € |
| MAX485 / SP3485 | Transceiver RS485 (si le port onduleur est RS485) | 1-3 € |
| MAX3232 | Transceiver RS232 (si le port onduleur est RS232/RJ45) | 1-3 € |
| Câble torsadé | 2 fils, 0,5 mm² minimum | 2-5 € |
| Alimentation 5 V | USB ou buck 12 V → 5 V, 1 A | 3-5 € |

**Total : ~12-24 €**

Le choix du transceiver dépend du port de l'onduleur. Voir
[WIRING.md](WIRING.md) pour les deux schémas, les niveaux 3,3 V/5 V et la gestion
DE/RE.

## Fonctionnalités

### Mesures (lecture seule)

| Entité | Unité | Registre |
|--------|-------|---------:|
| AC Input Voltage / Frequency / Power | V / Hz / W | 202-204 |
| Inverter Voltage / Current / Frequency / Power | V / A / Hz / W | 205-208 |
| AC Output Voltage / Current / Frequency / Active Power | V / A / Hz / W | 210-213 |
| AC Output Apparent Power | VA | 214 |
| Battery Voltage / Current / Power / SOC | V / A / W / % | 215-217, 229 |
| PV Voltage / Current / Power / Charging Power | V / A / W | 219-224 |
| Load | % | 225 |
| DCDC / Inverter Temperature | °C | 226-227 |
| PV Energy Today | kWh | dérivé de 223 |
| Charging / Discharging Power | W | dérivé de 217 |
| Battery Autonomy | min | dérivé de 217, 229 et capacité |

### Commandes

- **Select** : mode de sortie, priorité de sortie, plage d'entrée, buzzer,
  rétroéclairage, priorité de charge, mode de démarrage, type de batterie.
- **Switch** : LCD auto home, économie d'énergie, redémarrage sur surcharge ou
  surchauffe, transfert bypass, égalisation, interrupteur distant.
- **Number** : tensions de charge/décharge, OVP, courants max, fréquence et
  tension de sortie, paramètres d'égalisation.
- **Button** : sortie de l'état défaut (registre 426).

### Diagnostic

- Mode de fonctionnement lisible (registre 201).
- Code de défaut et code d'avertissement bruts (32 bits) + libellés.
- Statut Modbus, compteur d'erreurs, uptime, signal WiFi, appareil en ligne.
- `safe_mode` avec retour arrière après 5 échecs de démarrage.

### Énergie et autonomie

- CPU à 160 MHz par défaut (80 MHz possible), WiFi à 8,5 dB, power save LIGHT.
- Mode debug réglable depuis Home Assistant (5 s au lieu de 10 s).
- Aucun redémarrage automatique si Home Assistant est absent
  (`api.reboot_timeout: 0s`).

## Démarrage rapide

```powershell
# 1. Cloner le dépôt
git clone https://github.com/VOTRE_USER/anenji-esphome.git
cd anenji-esphome

# 2. Créer les secrets
Copy-Item secrets.yaml.example secrets.yaml
# Éditer secrets.yaml : WiFi, API, OTA, web

# 3. Valider et compiler
esphome config anenji.yaml
esphome compile anenji.yaml

# 4. Flasher
esphome run anenji.yaml
```

> Si le projet est dans un dossier synchronisé (Nextcloud/OneDrive) et que la
> compilation échoue sur `uv pip list`, copier le projet dans un dossier local
> non synchronisé (par exemple `C:\Temp\anenji`) et compiler là.

Procédure détaillée, checklist de vérification et adaptation 48 V :
[`quickstart.md`](specs/001-anenji-functional/quickstart.md).

## Sans ESP32

Le firmware ESP32 n'est pas obligatoire pour lire ou piloter l'onduleur. Trois
voies existent :

1. **Passerelle série → Ethernet** (recommandée) : elle remplace l'ESP32 sur le
   bus RS232/RS485 et reste entièrement locale.
2. **Adaptateur USB-RS485/RS232** sur le serveur Home Assistant, si celui-ci
   est proche de l'onduleur.
3. **Cloud fabricant** (SmartESS/SolarMAN), sans matériel mais avec latence et
   dépendance à Internet.

Le dongle Wi-Fi d'origine est une passerelle série → cloud : son IP n'expose
généralement pas Modbus en local. Tests de ports, configuration Home Assistant,
limites d'écriture FC16 et sécurité : voir
[`REMOTE_ACCESS.md`](REMOTE_ACCESS.md).

## Carte des registres

La carte complète, avec types, échelles, sources et variantes non supportées, est
dans [PROTOCOL.md](PROTOCOL.md) et dans le contrat
[`contracts/register-map.md`](specs/001-anenji-functional/contracts/register-map.md).

Points importants :

- **Températures** : registres 226/227 déjà en °C, **sans facteur 0,1**.
- **Batterie** : registre 217, positif = charge, négatif = décharge.
- **Écritures** : fonction 16 (`use_write_multiple: true`) et `write_lambda` qui
  retourne la valeur mise à l'échelle.
- **Défauts** : registres 100/108 en `U_DWORD` (2 registres), décodés par bits.

## Sécurité

- `secrets.yaml` est ignoré par Git ; seul `secrets.yaml.example` est versionné.
- API chiffrée et OTA protégé. Le serveur web est **désactivé par défaut** ; si
  vous l'activez, utilisez l'authentification (snippet dans `anenji.yaml`).
- Écritures bornées (`min_value` / `max_value`) et classées `config`.
- Seuils batterie paramétrables ; ne pas flasher une configuration 24 V sur un
  parc 48 V.
- Avant toute écriture critique, noter les valeurs d'origine et tester un réglage
  réversible.

## Variantes et limites

| Modèle | Support |
|--------|---------|
| Anenji / EASUN / ISolar SMG-II 4,2 kW | Oui (cible principale) |
| Anenji ANJ-4000W / ANJ-4200W-24V-WIFI | Oui — modèle 24 V de la gamme 4,2 kW |
| Anenji SMG-II 6,2 kW | Oui (mêmes registres, vérifier le port) |
| Anenji 11 kW hybride | **Non** — carte différente (277+, 338, 351, 389) ; voir `PreK/esphome-anenji-11kw-native-modbus` |
| SMG-II 6 kW variante USB-A | **Non** — carte et port différents ; voir `syssi/esphome-smg-ii` |
| Axpert / Voltronic MKS | **Non** — registres 200/250-259, hors SMG-II |

Les anciennes configurations de ce dépôt sont conservées dans `legacy/` et ne
doivent pas être flashées telles quelles.

> **Fonctionnement sans batterie** : la documentation commerciale Anenji indique
> que l'ANJ-4000W/4200W-24V-WIFI peut alimenter la charge sans batterie
> (PV + réseau). Dans ce mode, les entités de batterie (tension, SOC, autonomie)
> ne sont pas significatives ; la lecture PV/réseau/sortie reste valable. Ne pas
> y activer les automatismes de charge/décharge.

## Structure du dépôt

```text
anenji.yaml                  # configuration principale
secrets.yaml.example         # modèle de secrets
README.md                    # ce fichier
WIRING.md                    # câblage RS232 / RS485
PROTOCOL.md                  # carte de registres SMG-II
REMOTE_ACCESS.md             # contrôle sans ESP32 (passerelle, USB, cloud)
legacy/                      # anciennes configurations (avertissement)
specs/001-anenji-functional/ # spécification, plan, recherche, contrat, quickstart
.specify/                    # infrastructure SpecKit
```

## Dépannage

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| `Modbus Status: Error` | A/B inversés, GND absent, DE/RE non câblé | Vérifier le câblage, inverser A/B, relier DE+/RE à GPIO4 |
| Aucune trame | Mauvaise adresse ou débit | Vérifier `0x01` et 9600 8N1 |
| Température à 3,2 °C | Ancienne configuration | Utiliser `anenji.yaml` |
| Écriture sans effet | FC06 au lieu de FC16 | Vérifier `use_write_multiple: true` |
| Valeurs d'un 11 kW incohérentes | Carte de registres différente | Utiliser un projet 11 kW |
| Compilation impossible | Dossier synchronisé | Compiler dans `C:\Temp\anenji` |

## Sources

- [syssi/esphome-smg-ii](https://github.com/syssi/esphome-smg-ii)
- [jul-ienfr/esphome-anenji-4.2kw-wifi](https://github.com/jul-ienfr/esphome-anenji-4.2kw-wifi)
  — fork historique, dérivé de syssi ; **non utilisé comme source de vérité**.
- [janas-karol/esphome-anenji-6.2kw](https://github.com/janas-karol/esphome-anenji-6.2kw)
- [PreK/esphome-anenji-11kw-native-modbus](https://github.com/PreK/esphome-anenji-11kw-native-modbus)
- [attilagyurman/anenji-local-modbus](https://github.com/attilagyurman/anenji-local-modbus)
- [Documentation ESPHome Modbus](https://esphome.io/components/modbus_controller.html)

## Licence

GPL-3.0 — voir [LICENSE](LICENSE).
