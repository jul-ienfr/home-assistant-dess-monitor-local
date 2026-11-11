# DESS Monitor Local — Anenji / SMG-II

Intégration Home Assistant **100 % locale** pour les onduleurs Anenji, EASUN et
ISolar SMG-II, ainsi que les appareils compatibles PI30 (Voltronic/Axpert),
PI18 (InfiniSolar-V) et Modbus RTU.

Elle interroge directement l'onduleur, ou réutilise le dongle Wi-Fi d'origine
(Eybond / SmartESS) : pas de cloud, pas d'ESP32, pas de passerelle
supplémentaire.

> **Dépôt** :
> [jul-ienfr/home-assistant-dess-monitor-local](https://github.com/jul-ienfr/home-assistant-dess-monitor-local)
> **Documentation complète** : [`INTEGRATION.md`](INTEGRATION.md)
> **Installation et publication** : [`MARKETPLACE.md`](MARKETPLACE.md)

## Fonctionnalités

- **Télémétrie complète** : entrée AC, sortie onduleur, batterie, PV,
  températures, charge, énergie et autonomie.
- **Pilotage depuis Home Assistant** : priorités de sortie et de charge,
  tensions et courants de charge, seuils SOC, buzzer, rétroéclairage, mode de
  sortie, égalisation, sortie distante et sortie d'état défaut.
- **Défauts et avertissements décodés** : code 32 bits, libellés et conseils
  d'action, en français ou en anglais selon la langue de Home Assistant.
- **Énergie fiable** : intégration trapézoïdale qui s'arrête pendant une
  interruption de données au lieu de compter une énergie jamais produite.
- **vSoC optionnel** : estimation du SOC batterie par comptage de coulombs,
  indépendante de la tension sous charge.
- **Dongle EyBond** : un seul écouteur TCP pour plusieurs dongles, découverte
  par PN, protocole et transport configurables par onduleur.
- **Identité stable** : changer l'IP ou le nom d'hôte de l'onduleur dans les
  options conserve les entités, l'appareil et l'historique.
- **Diagnostic intégré** : dernier échantillon live, âge de la donnée,
  compteurs d'échec par section, `stale` / `stale_cycles`, intervalles
  configuré et effectif.
- **Noms français et anglais** fournis ; toute autre langue retombe sur
  l'anglais.

## Protocoles et transports

| Protocole | Appareils | Transports |
| --- | --- | --- |
| `voltronic` | Voltronic / Axpert PI30 | `tcp_elfin`, `serial`, `eybond` |
| `pi18` | PI18 / InfiniSolar-V | `tcp`, `serial` |
| `modbus` | Modbus RTU, SMG-II | `tcp`, `eybond` |
| `agent` | API HTTP locale `solar-system-agent` | `agent_http` |

L'intervalle de mise à jour est réglable de 1 à 300 s. Les dongles EyBond ont un
minimum de **5 s** : ils renouvellent leur session TCP toutes les quelques
secondes, et un poll plus rapide tombe surtout dans les trous de connexion.

## Installation

### Marketplace (Home Assistant 2026.11+)

1. **Paramètres → Marketplace**.
2. **Add from link** et coller
   `https://github.com/jul-ienfr/home-assistant-dess-monitor-local`.
3. Choisir **Integration**, puis **Install**.
4. Sélectionner la dernière release publiée (activer les préversions pour la
   ligne beta), puis redémarrer Home Assistant si demandé.
5. Ajouter l'intégration dans **Paramètres → Appareils et services**.

### HACS avant Home Assistant 2026.11

Ajouter le dépôt comme **Integration** dans les dépôts personnalisés, installer
**DESS Monitor Local**, puis redémarrer Home Assistant.

### Manuel

Copier `custom_components/dess_monitor_local` dans le dossier
`config/custom_components/` de Home Assistant et redémarrer. Le Marketplace est
préférable : il gère les mises à jour et la dépendance
`pyserial-asyncio-fast`.

Home Assistant **2024.6.0** ou plus récent est requis.

## Démarrage rapide

### Dongle Wi-Fi EyBond / SmartESS

1. Ajouter **DESS Monitor Local**, puis choisir **EyBond hub** (plusieurs
   dongles) ou **Single inverter**.
2. Protocole `modbus`, transport `eybond`, écoute `0.0.0.0:8899`, adresse RS485
   `1`.
3. Renseigner le broadcast du sous-réseau. Laisser **Announce IP** vide sur
   HAOS ou une installation native ; l'adresse locale est revérifiée tant que
   l'annonce est nécessaire. En Docker bridge, indiquer l'IP LAN de l'hôte.
4. Vérifier que le TCP `8899` est joignable depuis le dongle.

Procédure détaillée, schémas et dépannage : [`EYBOND_LOCAL.md`](EYBOND_LOCAL.md).

### Onduleur en TCP/Modbus direct

Choisir le protocole `modbus`, le transport `tcp`, puis l'hôte et le port de
l'onduleur ou de la passerelle. Préférer un **bail DHCP réservé** ou un nom
d'hôte local (par exemple `inverter.local`) à une IP brute : un changement
d'adresse reste transparent.

### Port série

Utiliser le transport `serial` uniquement si aucun autre maître n'interroge
déjà le port Modbus de l'onduleur. Un seul maître à la fois sur le bus.

## Documentation

| Document | Contenu |
| --- | --- |
| [`INTEGRATION.md`](INTEGRATION.md) | Documentation complète de l'intégration |
| [`EYBOND_LOCAL.md`](EYBOND_LOCAL.md) | Dongle EyBond / SmartESS, NAT, Docker, VLAN |
| [`PROTOCOL.md`](PROTOCOL.md) | Carte des registres Modbus SMG-II |
| [`wiki/Configuration.md`](wiki/Configuration.md) | Toutes les options de configuration |
| [`wiki/EyBond-Transport-Setup.md`](wiki/EyBond-Transport-Setup.md) | Assistant EyBond pas à pas |
| [`wiki/Inverter-Faults-API.md`](wiki/Inverter-Faults-API.md) | Contrat des entités défauts/avertissements |
| [`wiki/Inverter-Warnings-Card.md`](wiki/Inverter-Warnings-Card.md) | Carte Lovelace prête à coller |
| [`wiki/vSoC-Setup.md`](wiki/vSoC-Setup.md) | Mise en place du vSoC |
| [`MARKETPLACE.md`](MARKETPLACE.md) | Format Marketplace et publication |
| [`CHANGELOG.md`](CHANGELOG.md) | Historique des versions |

## Structure du dépôt

```text
hacs.json                     # métadonnées Marketplace
custom_components/dess_monitor_local/
                              # intégration Home Assistant
tests/                        # tests unitaires et tests Home Assistant
wiki/                         # documentation utilisateur
tools/                        # diagnostic Eybond (lecture et audit)
INTEGRATION.md                # documentation complète
EYBOND_LOCAL.md               # transport Eybond
PROTOCOL.md                   # carte des registres
MARKETPLACE.md                # publication
CHANGELOG.md                  # versions
```

Le firmware ESPHome, le câblage ESP32 et les configurations matérielles
historiques ne font plus partie de ce dépôt. L'intégration Home Assistant est
le seul produit maintenu ici.

## Développement

```bash
python -m pytest -q
ruff check custom_components/dess_monitor_local tests
```

La suite pure ne demande pas Home Assistant. Les tests de cycle de vie
(`tests/test_setup_hass.py`, `tests/test_entities.py`, etc.) nécessitent
`pytest-homeassistant-custom-component` et tournent dans le job CI Linux.

## Licence

Le dépôt upstream ne déclare pas de licence. Ce fork n'en ajoute pas
unilatéralement : considérer le code comme « tous droits réservés à l'auteur
upstream » tant que la situation n'est pas clarifiée.
