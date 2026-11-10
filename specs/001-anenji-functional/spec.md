# Spécification de fonctionnalité : Firmware Anenji fonctionnel

**Branche** : `001-anenji-functional`

**Créée** : 2026-11-10

**Statut** : Draft

**Entrée** : « Rendre le firmware ESPHome Anenji fonctionnel : corriger la carte
des registres SMG-II, supprimer les erreurs de compilation, sécuriser le câblage
RS485/RS232 et documenter la validation. »

## Scénarios utilisateur et tests *(obligatoire)*

### Histoire 1 - Lire les mesures réelles de l'onduleur (Priorité : P1)

En tant qu'utilisateur, je flashe un ESP32 relié à l'onduleur et je vois dans
Home Assistant des tensions, courants, puissances, SOC, températures et énergie
PV cohérents avec l'écran de l'onduleur.

**Pourquoi cette priorité** : sans lecture fiable, le projet n'a aucune valeur ;
c'est le MVP.

**Test indépendant** : après flash, comparer pendant une minute les entités
« AC Input Voltage », « AC Output Voltage », « Battery Voltage », « Battery
Current », « Battery SOC », « PV Power », « Load » et les températures avec
l'écran de l'onduleur. Les valeurs doivent être dans les plages physiques et
évoluer de façon cohérente.

**Scénarios d'acceptation** :

1. **Étant donné** un onduleur SMG-II sous tension et un ESP32 correctement câblé,
   **quand** le firmware démarre, **alors** la connexion Modbus passe à
   « Connected » en moins de 30 secondes.
2. **Étant donné** une lecture de tension batterie, **quand** l'écran indique
   26,5 V, **alors** l'entité affiche 26,5 V (± 0,2 V).
3. **Étant donné** une lecture de température, **quand** l'écran indique 32 °C,
   **alors** l'entité affiche 32 °C (± 1 °C), et non 3,2 °C.
4. **Étant donné** une batterie en charge, **quand** le courant est positif,
   **alors** « Charging Power » est positif et « Discharging Power » vaut 0.

---

### Histoire 2 - Piloter l'onduleur sans risque (Priorité : P2)

En tant qu'utilisateur, je peux modifier la priorité de sortie, la priorité de
charge, les courants et les tensions de charge depuis Home Assistant, et le
changement est appliqué par l'onduleur.

**Pourquoi cette priorité** : le projet annonce du contrôle ; des écritures
fausses peuvent endommager la batterie ou l'installation.

**Test indépendant** : modifier un réglage non critique (par exemple la priorité
de sortie), vérifier le changement sur l'écran de l'onduleur, puis revenir à la
valeur initiale.

**Scénarios d'acceptation** :

1. **Étant donné** un registre d'écriture SMG-II, **quand** l'utilisateur change
   une valeur, **alors** la commande utilise une écriture multiple (FC16) et la
   valeur est relue correctement.
2. **Étant donné** une valeur hors plage, **quand** l'utilisateur la saisit,
   **alors** l'entité la refuse (bornes min/max) et l'onduleur n'est pas modifié.
3. **Étant donné** un bouton « Exit Fault State », **quand** on appuie dessus,
   **alors** la commande d'écriture est envoyée au registre 426 sans provoquer
   d'erreur de compilation.

---

### Histoire 3 - Diagnostiquer les pannes (Priorité : P3)

En tant qu'utilisateur, je vois l'état de l'appareil, le mode de fonctionnement,
le code de défaut, le code d'avertissement et leur signification lisible.

**Pourquoi cette priorité** : un onduleur en défaut doit être compris rapidement,
surtout en installation isolée.

**Test indépendant** : provoquer ou simuler un code de défaut via le registre 100
(ou vérifier un code existant) et contrôler que l'entité texte affiche les noms
correspondants.

**Scénarios d'acceptation** :

1. **Étant donné** un code de défaut 0, **quand** l'entité « Fault » est lue,
   **alors** elle affiche « OK ».
2. **Étant donné** un code de défaut non nul, **quand** l'entité est lue,
   **alors** chaque bit actif est traduit par un libellé connu.
3. **Étant donné** une coupure de Home Assistant, **quand** l'ESP32 reste
   alimenté, **alors** il ne redémarre pas en boucle et continue de lire le bus.

---

### Histoire 4 - Installer et dépanner sans deviner (Priorité : P3)

En tant qu'utilisateur, je dispose d'une documentation qui me dit quel matériel
choisir, comment câbler (RS232 ou RS485), comment flasher, comment vérifier les
registres et quoi faire en cas d'échec.

**Pourquoi cette priorité** : le projet est aujourd'hui inutilisable pour un
nouvel arrivant à cause de documents contradictoires (RS485 vs RS232, carte de
registres 200 vs 100-643).

**Test indépendant** : suivre `quickstart.md` sur un poste vierge et obtenir un
firmware compilé, puis un onduleur qui répond.

**Scénarios d'acceptation** :

1. **Étant donné** un lecteur qui suit `WIRING.md`, **quand** il câble un MAX485,
   **alors** la broche DE/RE est reliée à GPIO4 et la terminaison est expliquée.
2. **Étant donné** un lecteur qui utilise un MAX3232, **quand** il lit la doc,
   **alors** il sait que la broche GPIO4 reste inutilisée.
3. **Étant donné** un utilisateur d'un modèle 11 kW, **quand** il lit
   `PROTOCOL.md`, **alors** il est averti que la carte de registres diffère et
   qu'il doit utiliser un projet adapté.

---

### Cas limites

- L'onduleur est éteint ou le câble A/B est inversé : le statut doit passer à
  « Error » sans bloquer le WiFi ni redémarrer l'ESP32.
- Le bus est bruité ou mal terminé : les lectures peuvent échouer ; l'intervalle
  et les retries doivent rester bornés.
- La batterie est en charge : l'autonomie ne doit pas être calculée (division par
  une puissance positive) et doit afficher « inconnu ».
- Le SOC ou la capacité est inconnu : l'autonomie doit afficher « inconnu ».
- Un modèle 48 V est utilisé avec les seuils 24 V par défaut : la documentation
  doit exiger l'adaptation des substitutions avant flash.
- Le mot de passe WiFi est absent : la compilation doit échouer clairement sur
  `secrets.yaml`, pas sur une valeur vide.

## Exigences *(obligatoire)*

### Exigences fonctionnelles

- **FR-001** : La configuration principale DOIT passer `esphome config` avec
  ESPHome 2025.12.x sans erreur de schéma.
- **FR-002** : La configuration principale DOIT compiler pour `esp32dev` avec le
  framework Arduino.
- **FR-003** : Les mesures DOIVENT utiliser uniquement les adresses SMG-II
  vérifiées (202-234, 643) avec les types et facteurs documentés.
- **FR-004** : Le courant et la puissance batterie DOIVENT respecter la convention
  positive = charge, négative = décharge.
- **FR-005** : Les températures DOIVENT être exprimées en °C sans facteur 0,1.
- **FR-006** : Le bus RS485 DOIT piloter DE/RE via `flow_control_pin` (GPIO4 par
  défaut) ; le mode RS232 DOIT rester possible sans modifier le reste du fichier.
- **FR-007** : Toutes les écritures de réglage DOIVENT utiliser
  `use_write_multiple: true` et des `write_lambda` retournant la valeur mise à
  l'échelle.
- **FR-008** : Les défauts et avertissements DOIVENT être lus comme des entiers
  32 bits (U_DWORD) et décodés en texte par table de bits.
- **FR-009** : L'API et l'OTA DOIVENT être protégés ; si le serveur web est
  activé, il DOIT être authentifié ; aucun secret ne DOIT être versionné.
- **FR-010** : L'appareil NE DOIT PAS redémarrer automatiquement lorsque Home
  Assistant est absent (`api.reboot_timeout: 0s`).
- **FR-011** : Le projet DOIT conserver une seule configuration principale et
  archiver les anciennes variantes dans `legacy/` avec un avertissement.
- **FR-012** : La documentation DOIT distinguer les générations 4,2/6,2 kW
  (SMG-II), 11 kW et 6 kW USB, et refuser explicitement les cartes non adaptées.

### Entités clés

- **Mesure** : nom, registre, type Modbus, facteur, unité, classe HA, plage
  physique attendue.
- **Réglage** : nom, registre, type, plage, valeur par défaut, caractère
  critique, procédure de retour arrière.
- **Diagnostic** : code de défaut, code d'avertissement, mode, statut du bus.
- **Appareil** : ESP32dev, adresse Modbus 0x01, UART 9600 8N1, GPIO16/17, DE/RE
  GPIO4.

## Critères de réussite *(obligatoire)*

### Résultats mesurables

- **SC-001** : `esphome config anenji.yaml` retourne le code 0 et aucune erreur
  de schéma.
- **SC-002** : `esphome compile anenji.yaml` produit un firmware sans erreur C++.
- **SC-003** : Sur matériel, au moins 10 entités de mesure sur 10 sont cohérentes
  avec l'écran de l'onduleur à ± 2 % (ou ± 1 unité pour les températures) après
  30 secondes.
- **SC-004** : Un changement de priorité de sortie est visible sur l'onduleur en
  moins de 10 secondes et peut être annulé.
- **SC-005** : Un nouvel utilisateur peut câbler et flasher en moins de 30 minutes
  en suivant `quickstart.md`, sans consulter l'historique Git.
- **SC-006** : Aucun secret réel n'apparaît dans `git ls-files`.

## Hypothèses

- L'onduleur ciblé est un Anenji SMG-II 4,2 kW ou 6,2 kW en parc 24 V, dont le
  modèle et le port sont confirmés par l'utilisateur. Le dépôt historique n'est
  **pas** une source de vérité.
- Le port de communication est accessible en UART TTL derrière un transceiver
  RS485 (MAX485/SP3485) ou RS232 (MAX3232).
- La carte ESP32dev dispose de 4 Mo de flash et du WiFi 2,4 GHz.
- Home Assistant n'est pas obligatoire au fonctionnement ; le serveur web et
  l'API sont optionnels.
- Le lecteur sait générer une clé API ESPHome et renseigner `secrets.yaml`.
- Les modèles 11 kW (registres 277+) et 6 kW USB (registres 80+) sont hors
  périmètre de cette version et seulement documentés.
