# Recherche et audit — Firmware Anenji

**Date** : 2026-11-10

**Objet** : comprendre l'état du dépôt, vérifier la carte de registres, comparer
les projets similaires et choisir une base fiable avant réécriture.

## 1. État initial du dépôt

| Fichier | Lignes | `esphome config` | Problème principal |
|---------|-------:|------------------|--------------------|
| `Anenji.YAML` | 655 | PASS | Carte de registres fausse (type Axpert), signe batterie inversé, serveur web ouvert, switch « Web Server » factice. |
| `Anenji_V24_CurrentRegisters.yaml` | 832 | FAIL | `update_interval` interdit sur `text_sensor.modbus_controller` ; registres 100/108 lus en texte hexadécimal ; carte majoritairement fausse. |
| `Anenji_V24_SMG2.yaml` | 1246 | FAIL | `button.modbus_controller` n'existe pas ; `update_interval` interdit ; décodage `std::stoul` + `try/catch` incompatible avec les exceptions désactivées ; températures ×0,1. |
| `.esphome/build/anenji` | — | — | Une compilation antérieure existe (ESPHome 2025.12.2), preuve que `Anenji.YAML` a déjà compilé. |

L'audit statique a été complété par une validation ESPHome 2025.12.2 et par la
comparaison avec des projets publics.

## 2. Sources consultées

### Projets de référence

1. **syssi/esphome-smg-ii** — https://github.com/syssi/esphome-smg-ii
   Projet canonique pour les onduleurs SMG-II (ISolar/EASUN/PowMr/Anenji). Il
   contient le protocole RS232 SMG-II et une configuration ESP32/ESP8266
   complète. C'est la source de la carte de registres utilisée ici.
2. **jul-ienfr/esphome-anenji-4.2kw-wifi** — https://github.com/jul-ienfr/esphome-anenji-4.2kw-wifi
   Fork francophone **historique**, dérivé de syssi. Il contient les erreurs
   corrigées ici et n'est **pas** utilisé comme autorité. Le PDF qu'il référence
   est celui de syssi ; la carte est vérifiée directement dans ce PDF.
3. **janas-karol/esphome-anenji-6.2kw** — https://github.com/janas-karol/esphome-anenji-6.2kw
   Fork 6,2 kW ; confirme les mêmes registres et l'usage de `use_write_multiple`.
4. **PreK/esphome-anenji-11kw-native-modbus** — https://github.com/PreK/esphome-anenji-11kw-native-modbus
   Modèle 11 kW : carte **différente** (338, 254, 277, 278, 280, 351, 389…).
   Sert à documenter la limite de compatibilité.
5. **attilagyurman/anenji-local-modbus** — https://github.com/attilagyurman/anenji-local-modbus
   Passerelle Python et relevé de registres 11 kW ; confirme les adresses 277-281,
   351, 389.
6. **sabatex/NetDaemonApps.InverterAnenji-4kw-7.2kw** — https://github.com/sabatex/NetDaemonApps.InverterAnenji-4kw-7.2kw
   Implémentation C# du protocole Anenji (trame TCP + Modbus).
7. **Millerderek/anenji-ha-bridge** — https://github.com/Millerderek/anenji-ha-bridge
   Intégration Home Assistant avec pont local ; montre les attentes d'entités.
8. **groove-max/ha-eybond-local** — https://github.com/groove-max/ha-eybond-local
   Intégration HACS pour les collecteurs EyeBond/SmartESS ; utile pour comprendre
   les variantes de passerelles cloud.
9. **GitHub Spec Kit** — https://github.com/github/spec-kit
   Méthodologie utilisée pour structurer cette évolution.

### Documentation ESPHome

- Modbus Controller : https://esphome.io/components/modbus_controller.html
- UART (dont `flow_control_pin`) : https://esphome.io/components/uart.html
- API : https://esphome.io/components/api.html
- Web Server : https://esphome.io/components/web_server.html
- `total_daily_energy` : https://esphome.io/components/sensor/total_daily_energy.html

## 3. Carte de registres vérifiée (SMG-II)

Les valeurs ci-dessous sont confirmées par **syssi** et par le **PDF
SMG-RS232 V1.0.1** (texte extrait directement). Les forks 4,2/6,2 kW sont
seulement vérifiés pour convergence ; ils ne servent pas de source primaire. La
table complète est dans
[`contracts/register-map.md`](contracts/register-map.md).

### Mesures

| Registre | Nom | Type | Échelle | Unité |
|---------:|-----|------|---------|-------|
| 100 | Fault code (2 registres) | U_DWORD | 1 | — |
| 108 | Warning code (2 registres) | U_DWORD | 1 | — |
| 201 | Operation mode | U_WORD | 1 | — |
| 202 | AC input voltage | S_WORD | 0,1 | V |
| 203 | AC input frequency | S_WORD | 0,01 | Hz |
| 204 | AC input power | S_WORD | 1 | W |
| 205 | Inverter voltage | S_WORD | 0,1 | V |
| 206 | Inverter current | S_WORD | 0,1 | A |
| 207 | Inverter frequency | S_WORD | 0,01 | Hz |
| 208 | Inverter power | S_WORD | 1 | W |
| 209 | Inverter charging power | S_WORD | 1 | W |
| 210 | AC output voltage | S_WORD | 0,1 | V |
| 211 | AC output current | S_WORD | 0,1 | A |
| 212 | AC output frequency | S_WORD | 0,01 | Hz |
| 213 | AC output active power | S_WORD | 1 | W |
| 214 | AC output apparent power | S_WORD | 1 | VA |
| 215 | Battery voltage | S_WORD | 0,1 | V |
| 216 | Battery current | S_WORD | 0,1 | A |
| 217 | Battery power (positif = charge) | S_WORD | 1 | W |
| 219 | PV voltage | S_WORD | 0,1 | V |
| 220 | PV current | S_WORD | 0,1 | A |
| 223 | PV power | S_WORD | 1 | W |
| 224 | PV charging power | S_WORD | 1 | W |
| 225 | Load | S_WORD | 1 | % |
| 226 | DCDC temperature | S_WORD | 1 | °C |
| 227 | Inverter temperature | S_WORD | 1 | °C |
| 229 | Battery SOC | U_WORD | 1 | % |
| 232 | Battery current (BMS) | S_WORD | 0,1 | A |
| 233 | Inverter charging current | S_WORD | 0,1 | A |
| 234 | PV charging current | S_WORD | 0,1 | A |
| 643 | Rated power | U_WORD | 1 | W |

### Commandes

| Registre | Nom | Type | Échelle | Valeurs |
|---------:|-----|------|---------|---------|
| 300 | Output mode | U_WORD | 1 | 0-4 |
| 301 | Output priority | U_WORD | 1 | 0-3 |
| 302 | Input voltage range | U_WORD | 1 | 0/1 |
| 303 | Buzzer mode | U_WORD | 1 | 0-3 |
| 305 | LCD backlight | U_WORD | 1 | 0/1 |
| 306 | LCD auto return | U_WORD (bit) | 1 | 0/1 |
| 307 | Energy saving | U_WORD (bit) | 1 | 0/1 |
| 308 | Overload auto restart | U_WORD (bit) | 1 | 0/1 |
| 309 | Over temperature auto restart | U_WORD (bit) | 1 | 0/1 |
| 310 | Overload bypass | U_WORD (bit) | 1 | 0/1 |
| 313 | Battery equalization | U_WORD (bit) | 1 | 0/1 |
| 320 | Output voltage setting | U_WORD | 0,1 | V |
| 321 | Output frequency setting | U_WORD | 0,01 | Hz |
| 322 | Battery type | U_WORD | 1 | 0-8 |
| 323 | Battery OVP | U_WORD | 0,1 | V |
| 324 | Max charging voltage | U_WORD | 0,1 | V |
| 325 | Float charging voltage | U_WORD | 0,1 | V |
| 326 | Recovery voltage (mains) | U_WORD | 0,1 | V |
| 327 | Low DC cut-off (mains) | U_WORD | 0,1 | V |
| 329 | Low DC cut-off (off-grid) | U_WORD | 0,1 | V |
| 331 | Charging priority | U_WORD | 1 | 0-3 |
| 332 | Max charging current | U_WORD | 0,1 | A |
| 333 | Max mains charging current | U_WORD | 0,1 | A |
| 334 | Equalization voltage | U_WORD | 0,1 | V |
| 335 | Equalization time | U_WORD | 1 | min |
| 336 | Equalization timeout | U_WORD | 1 | min |
| 337 | Equalization interval | U_WORD | 1 | jour |
| 420 | Remote switch | U_WORD (bit) | 1 | 0/1 |
| 426 | Exit fault state | U_WORD | 1 | écrire 1 |

## 4. Défauts constatés et corrections

| # | Sévérité | Constat | Preuve | Correction |
|---|----------|---------|--------|------------|
| 1 | Bloquant | `button.modbus_controller` n'existe pas | `esphome config` : « Platform not found » | Bouton `template` + `ModbusCommandItem::create_write_multiple_command`. |
| 2 | Bloquant | `update_interval` interdit sur `text_sensor.modbus_controller` | `esphome config` | Supprimé ; rafraîchissement par `text_sensor.template` ou lecture numérique. |
| 3 | Bloquant | `std::stoul` + `try/catch` | Exceptions désactivées sur ESP32 Arduino | Décodage par registre `U_DWORD` + table de bits, sans exception. |
| 4 | Critique | Registres 200/201/202/214/263/264 faux | PDF SMG-II + syssi | Carte 202-234/643. |
| 5 | Critique | Températures multipliées par 0,1 | Protocole : 1 °C, `S_WORD` | Facteur supprimé, `accuracy_decimals: 0`. |
| 6 | Critique | Signe batterie inversé | Protocole : positif = charge | `Battery Power` = registre 217 ; charge/décharge et autonomie corrigées. |
| 7 | Critique | Écritures sans `use_write_multiple` | PDF + syssi | `use_write_multiple: true` partout. |
| 8 | Critique | `write_lambda` pousse des octets et retourne `true` | API ESPHome : la lambda retourne la valeur | `write_lambda: "return x * 10.0f;"`. |
| 9 | Majeur | Pas de contrôle DE/RE RS485 | WIRING + MAX485 | `flow_control_pin: GPIO4`. |
| 10 | Majeur | Serveur web sans authentification | `web_server` sans `auth` | Serveur web désactivé par défaut ; snippet protégé documenté. |
| 11 | Majeur | Redémarrage si HA absent | `api.reboot_timeout: 10min` | `reboot_timeout: 0s`. |
| 12 | Majeur | Documentation contradictoire | README/WIRING vs code | README, WIRING, PROTOCOL réécrits. |
| 13 | Moyen | Pas de `state_class` | HA n'enregistre pas les statistiques | Ajouté sur les mesures. |
| 14 | Moyen | Switch « Web Server » factice | Il ne fait que logger | Supprimé ; serveur web toujours actif et protégé. |
| 15 | Moyen | Aucune entité d'état du bus | Diagnostic difficile | `Modbus Status`, `Modbus Error Count`, `Uptime`, `WiFi Signal`. |
| 16 | Faible | LED annoncée mais absente de `Anenji.YAML` | README vs YAML | LED `light` conservée dans la config principale. |

## 5. Variantes matérielles

| Génération | Registres clés | Compatible avec ce dépôt ? |
|------------|----------------|----------------------------|
| SMG-II 4,2/6,2 kW (24 V) | 202-234, 643 | **Oui** — cible principale. |
| Anenji 11 kW hybride | 338, 254, 277-281, 351, 389 | Non — carte différente, voir PreK. |
| SMG-II 6 kW variante USB-A | 80-345 (selon syssi) | Non — port et carte différents. |
| Modèles 48 V | mêmes registres, seuils doublés | Oui après adaptation des substitutions. |

## 6. Décisions d'architecture

1. **Une seule configuration principale** (`anenji.yaml`) au lieu de trois.
   Les anciennes sont archivées dans `legacy/` avec un avertissement.
2. **RS485 et RS232 dans le même fichier** : `flow_control_pin` est configuré sur
   GPIO4. Avec un MAX3232, cette broche n'est simplement pas câblée ; cela évite
   deux fichiers presque identiques.
3. **API native Home Assistant**, pas MQTT : moins de dépendances, découverte
   automatique, logs et OTA intégrés.
4. **Pas de composant externe** : uniquement `modbus_controller` natif, pour
   rester compatible ESPHome 2025.12 et éviter une dépendance non maintenue.
5. **Décodage des défauts par table de bits** : plus simple et plus robuste que
   le parsing hexadécimal, et compatible avec les exceptions désactivées.
6. **Seuils batterie paramétrables** : substitutions pour 24 V, doublées pour 48 V.
7. **Pas de filtres delta** : ils masquaient les valeurs et compliquaient le
   diagnostic ; l'intervalle Modbus suffit. Les moyennes glissantes sont
   réservées aux températures si nécessaire.

## 7. Alternatives rejetées

| Alternative | Raison du rejet |
|-------------|-----------------|
| Utiliser directement `syssi/esphome-smg-ii` (2026.9) | Exige ESPHome ≥ 2026.9 ; l'environnement validé est 2025.12.2. |
| Conserver `Anenji.YAML` et corriger quelques registres | La carte est structurellement fausse (Axpert vs SMG-II) ; risque de commander la mauvaise chose. |
| Deux fichiers RS232/RS485 | Duplication de 700 lignes ; la broche DE non câblée est inoffensive. |
| Composant externe `modbus_controller` custom | Complexité et maintenance ; le natif suffit. |
| MQTT | Dépendance supplémentaire sans bénéfice pour HA. |
| Supprimer le contrôle et ne garder que la lecture | Le projet revendique le contrôle ; les écritures vérifiées sont utiles. |

## 8. Risques et questions ouvertes

- **Modèle exact** : la carte SMG-II est supposée d'après l'ascendance du dépôt.
  Si l'onduleur est un 11 kW, la configuration ne lira pas les bonnes valeurs ;
  `PROTOCOL.md` l'indique explicitement.
- **Port physique** : certains Anenji exposent RS232 (RJ45/USB-A), d'autres
  RS485. Le câblage doit être confirmé avant flash.
- **Accès sans ESP32** : le dongle Wi-Fi est une passerelle série → cloud ;
  son IP n'expose généralement pas Modbus en local. Les solutions (passerelle
  série → Ethernet, adaptateur USB sur Home Assistant, cloud) et les limites
  d'écriture FC16 sont documentées dans [`REMOTE_ACCESS.md`](../../REMOTE_ACCESS.md).
- **Manuel du ANJ-4000W/4200W-24V-WIFI** : introuvable en ligne (novembre 2026).
  Les photos produit confirment un 24 V de la famille SMG-II et le fonctionnement
  sans batterie, mais ne documentent ni les ports ni un éventuel brochage BMS.
  Le brochage RJ45 de `WIRING.md` reste celui du SMG-II générique et doit être
  vérifié au multimètre.
- **Écritures** : `use_write_multiple` est requis par les forks, mais certains
  firmware acceptent aussi FC06. Tester d'abord un réglage non critique.
- **Seuils 24 V/48 V** : les valeurs par défaut sont 24 V ; un parc 48 V doit
  doubler les substitutions avant flash.
- **Compilation dans un dossier cloud** : `uv pip list` échoue si le dossier est
  synchronisé (erreur `os error -2145452027`). Compiler depuis un dossier local
  non synchronisé, puis copier le binaire.

## 9. Validation finale

| Vérification | Résultat |
|--------------|----------|
| `esphome config anenji.yaml` (ESPHome 2025.12.2) | Code 0, aucune erreur de schéma |
| `esphome compile anenji.yaml` | `INFO Successfully compiled program.` |
| Durée de compilation | 490,96 s (build complet) |
| `firmware.bin` | 1 028 944 octets |
| Avertissement restant | `GPIO2 is a strapping PIN` (LED onboard) |
| Identifiants dupliqués | Aucun |
| Plateformes inexistantes | Aucune |
| Secrets versionnés | Aucun (`git ls-files` vérifié) |

Détail complet : [`validation.md`](validation.md).

**Limite** : la validation matérielle (lectures réelles, écritures, défauts,
coupure HA) reste à effectuer ; elle est décrite dans
[`quickstart.md`](quickstart.md).
