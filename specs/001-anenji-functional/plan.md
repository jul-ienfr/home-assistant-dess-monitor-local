# Plan d'implémentation : Firmware Anenji fonctionnel

**Branche** : `001-anenji-functional` | **Date** : 2026-11-10 | **Spec** : [spec.md](spec.md)

**Entrée** : spécification `specs/001-anenji-functional/spec.md`

## Résumé

Le dépôt contient trois configurations ESPHome concurrentes, dont la principale
(`Anenji.YAML`) utilise une carte de registres de type Axpert qui ne correspond
pas à l'onduleur SMG-II, et dont les deux autres ne compilent pas (plateforme
`button.modbus_controller` inexistante, `update_interval` interdit sur un
`text_sensor` Modbus). L'objectif est de livrer une configuration unique,
compilable et vérifiée, fondée sur la carte SMG-II documentée par
`syssi/esphome-smg-ii` et ses forks Anenji, puis de mettre la documentation
(câblage, protocole, secrets, validation) au même niveau.

La démarche est volontairement conservatrice : une seule cible matérielle
(ESP32dev, SMG-II 4,2/6,2 kW), une seule configuration principale, des écritures
bornées et documentées, et une séparation nette entre RS232 et RS485.

## Contexte technique

**Langage / version** : YAML ESPHome, ESPHome 2025.12.2 (minimum 2025.12.1),
framework Arduino, C++ généré.

**Dépendances principales** : composants natifs ESPHome (`uart`, `modbus`,
`modbus_controller`, `sensor`, `text_sensor`, `number`, `select`, `switch`,
`button`, `total_daily_energy`, `api`, `ota`, `safe_mode`). Le serveur web est
optionnel et désactivé par défaut.

**Stockage** : NVS de l'ESP32 pour l'état restauré (énergie PV, mode debug,
capacité batterie). Pas de base de données.

**Tests** :
- validation statique : `esphome config anenji.yaml` ;
- compilation : `esphome compile anenji.yaml` ;
- test matériel : checklist `quickstart.md` (lectures, écriture réversible,
  défaut simulé, coupure HA).
- Vérification de la carte de registres : `contracts/register-map.md` comparé aux
  sources publiques et à l'écran de l'onduleur.

**Plateforme cible** : ESP32dev (ESP32-WROOM-32, 4 Mo), 2,4 GHz, UART 9600 8N1,
esclave Modbus 0x01.

**Type de projet** : firmware / configuration déclarative ESPHome, pas
d'application serveur.

**Objectifs de performance** : cycle Modbus de 10 s en production (5 s en debug),
moins de 5 % de trames en erreur sur un bus correctement terminé, démarrage WiFi
en moins de 30 s, fonctionnement continu sans Home Assistant.

**Contraintes** :
- ESPHome 2025.12.x installé ; l'API `modbus_controller::ModbusCommandItem` et
  `use_write_multiple` doivent rester compatibles.
- Pas de composant externe pour le cœur du fonctionnement.
- Les modèles 11 kW et 6 kW USB ont des cartes différentes : hors périmètre.
- Le dossier de travail peut être synchronisé par un fournisseur cloud qui
  bloque `uv pip list` : compiler depuis un dossier local non synchronisé.

**Échelle / portée** : un onduleur, un ESP32, environ 70 entités HA, une
configuration principale, deux variantes de câblage documentées.

## Vérification de la constitution

*PORTE : doit passer avant la phase 0 et être revérifiée après la phase 1.*

| Principe | Vérification | Résultat |
|----------|--------------|----------|
| I. Sécurité | Toutes les écritures sont bornées, documentées, réversibles ; valeurs par défaut 24 V explicites. | PASS |
| II. Registres fondés sur des preuves | Chaque registre est tracé dans `PROTOCOL.md` et `contracts/register-map.md` avec source. | PASS |
| III. Compilation vérifiée | Les portes `esphome config` et `esphome compile` sont obligatoires et exécutées. | PASS |
| IV. Secrets / réseau | `secrets.yaml` ignoré, exemples seulement, API/OTA/web protégés, `reboot_timeout: 0s`. | PASS |
| V. Documentation | README, WIRING, PROTOCOL, quickstart mis à jour dans la même livraison. | PASS |
| VI. Simplicité / réversibilité | Une config principale, legacy archivé, filtres non masquants. | PASS |

Aucune violation justifiée : la section « Complexity Tracking » reste vide.

## Structure du projet

### Documentation de la fonctionnalité

```text
specs/001-anenji-functional/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── register-map.md
└── tasks.md
```

### Code source (racine du dépôt)

```text
anenji.yaml                 # configuration principale (SMG-II, RS485/RS232)
secrets.yaml.example        # modèle de secrets (aucune valeur réelle)
README.md                   # présentation, matériel, entités, usage
WIRING.md                   # câblage RS232 vs RS485, niveaux, DE/RE
PROTOCOL.md                 # carte de registres SMG-II + sources + limites
legacy/
├── README.md               # avertissement : ne pas flasher tel quel
├── Anenji.legacy.YAML
├── Anenji_V24_CurrentRegisters.legacy.yaml
└── Anenji_V24_SMG2.legacy.yaml
.specify/                   # infrastructure SpecKit
specs/                      # spécifications et preuves
```

**Décision de structure** : configuration unique à la racine pour rester
compatible avec `esphome run anenji.yaml` et le dashboard ESPHome ; archives dans
`legacy/` pour ne pas casser l'historique ; contrats et preuves dans `specs/`
pour la traçabilité SpecKit.

## Suivi de complexité

Aucune violation de la constitution. Pas de quatrième projet, pas de composant
externe, pas de couche d'abstraction supplémentaire.
