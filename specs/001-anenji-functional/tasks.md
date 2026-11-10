# Tâches : Firmware Anenji fonctionnel

**Entrée** : `specs/001-anenji-functional/`

**Prérequis** : `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/register-map.md`

**Organisation** : les tâches sont groupées par histoire utilisateur pour rester
indépendamment vérifiables. Les tâches matérielles sont marquées
`(matériel)` : elles ne peuvent pas être validées sans l'onduleur.

## Phase 1 : Mise en place

- [x] **T001** Initialiser SpecKit dans le dépôt (`specify init . --integration opencode`)
- [x] **T002** Créer la branche et le dossier `specs/001-anenji-functional/`
- [x] **T003** [P] Rédiger la constitution `.specify/memory/constitution.md`

---

## Phase 2 : Fondations (bloquant)

- [x] **T004** Auditer les trois YAML existants et l'historique Git
- [x] **T005** [P] Valider les configurations avec ESPHome 2025.12.2
- [x] **T006** [P] Rechercher les projets similaires et la documentation ESPHome
- [x] **T007** Établir la carte de registres SMG-II dans `contracts/register-map.md`
- [x] **T008** Rédiger `research.md` avec les décisions et alternatives
- [x] **T009** Rédiger `plan.md` et vérifier la constitution
- [x] **T010** Rédiger `data-model.md`, `quickstart.md` et ce fichier `tasks.md`

**Point de contrôle** : la carte de registres et les décisions sont figées.

---

## Phase 3 : Histoire 1 — Lecture fiable (P1) 🎯 MVP

**Objectif** : un firmware compilable qui lit les mesures SMG-II.

- [x] **T011** [US1] Créer `anenji.yaml` avec la configuration ESP32/Modbus
- [x] **T012** [US1] Ajouter les mesures réseau, onduleur, sortie, batterie, PV, charge, températures
- [x] **T013** [US1] Corriger les échelles : températures 1 °C, tensions 0,1 V, fréquences 0,01 Hz
- [x] **T014** [US1] Corriger la convention batterie (positif = charge) et l'autonomie
- [x] **T015** [US1] Ajouter l'énergie PV quotidienne (`total_daily_energy`)
- [x] **T016** [US1] Ajouter les classes HA (`device_class`, `state_class`) et les plages
- [x] **T017** [US1] Valider `esphome config anenji.yaml` (code 0)
- [x] **T018** [US1] Compiler `esphome compile anenji.yaml` (binaire produit)
- [ ] **T019** [US1] (matériel) Comparer les 10 mesures à l'écran de l'onduleur
- [ ] **T020** [US1] (matériel) Vérifier le signe charge/décharge et l'autonomie

**Test indépendant** : `esphome config` + `esphome compile` + checklist des
mesures dans `quickstart.md`.

---

## Phase 4 : Histoire 2 — Contrôle sûr (P2)

**Objectif** : écrire les réglages SMG-II avec le bon mode et les bonnes bornes.

- [x] **T021** [US2] Ajouter les `select` (mode, priorités, plage, buzzer, LCD, charge, batterie)
- [x] **T022** [US2] Ajouter les `switch` (LCD, économie, redémarrages, bypass, EQ, remote)
- [x] **T023** [US2] Ajouter les `number` (tensions, courants, fréquences, EQ)
- [x] **T024** [US2] Ajouter `use_write_multiple: true` sur toutes les écritures
- [x] **T025** [US2] Corriger les `write_lambda` pour retourner la valeur mise à l'échelle
- [x] **T026** [US2] Remplacer `button.modbus_controller` par un bouton `template` (registre 426)
- [x] **T027** [US2] Paramétrer les seuils batterie 24 V/48 V par substitutions
- [x] **T028** [US2] Valider et compiler après ajout des commandes
- [ ] **T029** [US2] (matériel) Tester une écriture réversible (priorité de sortie)
- [ ] **T030** [US2] (matériel) Tester le bouton « Exit Fault State » si un défaut est présent

**Test indépendant** : écrire une valeur bornée, la relire, revenir à l'état
initial.

---

## Phase 5 : Histoire 3 — Diagnostic (P3)

**Objectif** : comprendre l'état et les pannes sans redémarrer.

- [x] **T031** [US3] Lire les défauts/avertissements en `U_DWORD` (100/108)
- [x] **T032** [US3] Décoder les bits en texte sans `try/catch`
- [x] **T033** [US3] Ajouter le mode de fonctionnement lisible (registre 201)
- [x] **T034** [US3] Ajouter `Modbus Status`, `Modbus Error Count`, `Uptime`, `WiFi Signal`
- [x] **T035** [US3] Désactiver le redémarrage si Home Assistant est absent (`reboot_timeout: 0s`)
- [x] **T036** [US3] Ajouter `Device Online` et `safe_mode`
- [ ] **T037** [US3] (matériel) Vérifier l'affichage d'un code de défaut connu
- [ ] **T038** [US3] (matériel) Couper Home Assistant et vérifier l'absence de redémarrage

**Test indépendant** : les entités de diagnostic sont présentes et le firmware
reste en ligne sans HA.

---

## Phase 6 : Histoire 4 — Documentation (P3)

**Objectif** : un nouvel utilisateur peut installer et dépanner sans deviner.

- [x] **T039** [US4] Réécrire `README.md` (matériel, entités, carte, validation)
- [x] **T040** [US4] Réécrire `WIRING.md` (RS232 vs RS485, 3,3 V/5 V, DE/RE, terminaison)
- [x] **T041** [US4] Créer `PROTOCOL.md` (carte, sources, variantes, limites)
- [x] **T042** [US4] Mettre à jour `secrets.yaml.example` (web, API, OTA)
- [x] **T043** [US4] Archiver les anciennes configs dans `legacy/` avec un avertissement
- [x] **T044** [US4] Ajouter la procédure de compilation hors dossier synchronisé
- [x] **T045** [US4] Documenter l'adaptation 48 V et les modèles non supportés
- [x] **T054** [US4] Documenter le modèle ANJ-4000W/4200W-24V-WIFI, le mode sans
  batterie et l'absence de manuel/brochage BMS
- [x] **T055** [US4] Documenter l'accès sans ESP32 (passerelle série → Ethernet,
  USB sur Home Assistant, cloud) dans `REMOTE_ACCESS.md`

---

## Phase 7 : Finition et portes de qualité

- [x] **T046** Exécuter `esphome config anenji.yaml` et archiver la sortie
- [x] **T047** Exécuter `esphome compile anenji.yaml` et archiver la sortie
- [x] **T048** Vérifier `git ls-files` : aucun secret réel
- [x] **T049** Vérifier l'absence d'identifiants dupliqués et de plateformes inexistantes
- [x] **T050** Mettre à jour le rapport d'audit final dans `research.md`
- [ ] **T051** (matériel) Valider la checklist complète `quickstart.md`
- [x] **T052** Nettoyer `.audit/` (recherche temporaire)
- [ ] **T053** Committer la livraison (non exécuté : l'utilisateur n'a pas demandé de commit)

> Résultats de validation : [`validation.md`](validation.md).

## Dépendances

```text
T001-T003 → T004-T010 → T011-T020 (US1)
                       ├→ T021-T030 (US2, dépend de US1)
                       ├→ T031-T038 (US3, dépend de US1)
                       └→ T039-T045 (US4, peut avancer en parallèle)
T046-T050 après US1-US4
```

## Stratégie MVP

Le MVP est l'histoire 1 (T011-T020) : un firmware compilable qui lit les bonnes
mesures. Les histoires 2 et 3 ajoutent le contrôle et le diagnostic sans remettre
en cause la lecture. L'histoire 4 rend le tout reproductible.

## Notes

- Les tâches `(matériel)` restent ouvertes tant que l'onduleur n'est pas
  disponible ; elles ne bloquent pas la livraison du firmware compilé.
- Toute nouvelle adresse de registre doit être ajoutée à
  `contracts/register-map.md` avant le YAML.
- Ne jamais committer `secrets.yaml` ni `.esphome/`.
