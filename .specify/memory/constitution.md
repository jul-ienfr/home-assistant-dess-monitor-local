# Constitution du projet Anenji ESPHome

## Principes fondamentaux

### I. Sécurité de l'installation (NON NÉGOCIABLE)

Toute commande envoyée à l'onduleur peut modifier la charge, la batterie ou la
sortie AC. Une écriture ne peut être exposée que si son registre, son type, son
échelle et sa plage ont été vérifiés sur une source documentaire ou un test
matériel. Les valeurs par défaut doivent être conservatrices, les plages doivent
être bornées, et toute commande destructrice doit rester réversible ou
explicitement signalée dans la documentation.

### II. Registres fondés sur des preuves

Chaque registre utilisé doit être tracé dans `PROTOCOL.md` avec son adresse, son
type, son facteur d'échelle, son accès (R/W) et sa source. Aucun registre ne peut
être ajouté « au hasard » ou par analogie avec un autre modèle. Les différences
entre générations (SMG-II 4,2/6,2 kW, 11 kW, variantes 6 kW USB) doivent être
documentées et les cartes non supportées doivent être refusées explicitement.

### III. Modifications vérifiées par la compilation

Aucune évolution du firmware n'est considérée terminée sans :
1. `esphome config <fichier>.yaml` réussi sans erreur de schéma ;
2. `esphome compile <fichier>.yaml` réussi pour la carte cible ;
3. une vérification matérielle décrite dans `specs/.../quickstart.md`.

Les erreurs de schéma, les identifiants dupliqués, les plateformes inexistantes
et les lambdas C++ non compilables sont des bloqueurs, jamais des avertissements.

### IV. Hygiène des secrets et du réseau

Aucun secret (WiFi, mot de passe OTA, clé API, mot de passe web) ne doit être
versionné. `secrets.yaml` reste ignoré par Git ; seul `secrets.yaml.example` est
publié. L'API, l'OTA et le serveur web doivent être protégés. L'appareil doit
rester utilisable sans Home Assistant (pas de redémarrage automatique imposé).

### V. Documentation synchronisée

Le `README.md`, `WIRING.md`, `PROTOCOL.md` et les commentaires du YAML décrivent
le même matériel, le même câblage et la même carte de registres. Toute
modification fonctionnelle met à jour la documentation dans la même livraison.
Les schémas de câblage doivent distinguer explicitement RS232 et RS485, les
niveaux logiques 3,3 V/5 V et la gestion DE/RE.

### VI. Simplicité et réversibilité

Une seule configuration principale fait foi ; les anciennes variantes sont
archivées dans `legacy/` avec un avertissement. Les fonctions qui ne peuvent pas
être testées sont documentées comme non vérifiées ou supprimées. Les filtres et
automatisations ne doivent pas masquer une panne ou une valeur aberrante.

## Contraintes techniques

- **Firmware** : ESPHome 2025.12.x (validé avec 2025.12.2), framework Arduino.
- **Cible** : ESP32dev (4 Mo), UART 9600 8N1, esclave Modbus 0x01.
- **Protocole de référence** : SMG-II (Anenji 4,2/6,2 kW), pas la carte 11 kW.
- **Composants** : uniquement des composants ESPHome natifs ; pas de composant
  externe non maintenu pour le cœur du fonctionnement.
- **Énergie** : options 80/160/240 MHz et WiFi réduit documentées, sans casser
  la fiabilité du bus.

## Flux de développement et portes de qualité

1. Toute fonctionnalité passe par une spécification dans `specs/`.
2. Le plan et les tâches sont générés avant l'implémentation.
3. Les portes de qualité (config + compile) sont exécutées avant livraison.
4. Un test matériel minimal est décrit avec les valeurs attendues.
5. Les secrets sont remplacés par des exemples avant tout commit.

## Gouvernance

La présente constitution prime sur les habitudes et les fichiers historiques.
Toute exception doit être justifiée dans `plan.md` (section « Complexity
Tracking »). Les amendements nécessitent une mise à jour datée, une revue et une
note de migration si le comportement change. Le respect des principes est vérifié
à chaque revue et avant chaque fusion.

**Version** : 1.0.0 | **Ratifiée** : 2026-11-10 | **Dernière modification** : 2026-11-10
