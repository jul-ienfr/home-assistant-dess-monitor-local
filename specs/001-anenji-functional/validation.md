# Validation — Firmware Anenji

**Date** : 2026-11-10

**Cible** : `anenji.yaml` (SMG-II, ESP32dev, Arduino)

## 1. Environnement

| Élément | Valeur |
|---------|--------|
| ESPHome | 2025.12.2 |
| Carte | `esp32dev` |
| Framework | Arduino |
| Module Python | `esphome` (binaire 2025.12.2) |
| OS | Windows 10/11 (PowerShell 5.1) |

## 2. Validation statique

```powershell
esphome config .audit\anenji.yaml
```

- **Résultat** : code de sortie `0`.
- **Avertissement** : `GPIO2 is a strapping PIN` (LED de statut sur la broche
  onboard ; sans conséquence si aucun pull-up externe n'est ajouté).
- **Erreurs** : aucune.
- **Remarque** : la validation a utilisé un `secrets.yaml` de test, car le
  `secrets.yaml` réel du dossier n'était pas lisible dans cet environnement
  (erreur du fournisseur de fichiers cloud). Les clés attendues sont celles de
  `secrets.yaml.example`.

## 3. Compilation

```powershell
esphome compile anenji.yaml
```

- **Résultat** : `INFO Successfully compiled program.`
- **Durée** : 490,96 s (compilation complète, dépendances téléchargées).
- **Artefacts** :
  - `firmware.bin` : 1 028 944 octets ;
  - `firmware.factory.bin` : 1 094 480 octets ;
  - `firmware.ota.bin` : 1 028 944 octets.
- **SHA-256 de `firmware.bin`** :
  `C67002755C0C726FABFD9786341C94865BEAC95D246370DDA6767E3E5C9F8156`.
- **Avertissements de compilation** : aucun avertissement bloquant lié au YAML.
  Les avertissements restants proviennent des bibliothèques ESP-IDF/Arduino
  (`freertos/task_snapshot.h`, `NetworkClient::flush`) et n'affectent pas le
  fonctionnement.

## 4. Ce que la compilation prouve

- Le schéma ESPHome est valide (plateformes, options, identifiants uniques).
- Les lambdas C++ sont compilables : décodage des défauts, bouton Modbus,
  `write_lambda`, text sensors.
- Les composants `modbus_controller`, `uart` avec `flow_control_pin`, `number`,
  `select`, `switch`, `button` template et `total_daily_energy` sont présents.
- Le binaire tient dans la flash de l'ESP32dev.

## 5. Ce qui reste à valider sur matériel

Ces points ne peuvent pas être prouvés sans onduleur :

- [ ] Adresse Modbus 0x01 et débit 9600 8N1 corrects.
- [ ] Lectures cohérentes avec l'écran (tensions, courant, SOC, PV, charge,
      températures).
- [ ] Signe charge/décharge et autonomie.
- [ ] Écriture réversible (priorité de sortie) et bouton « Exit Fault State ».
- [ ] Décodage d'un code de défaut réel.
- [ ] Absence de redémarrage quand Home Assistant est coupé.

La procédure est dans [`quickstart.md`](quickstart.md).

## 6. Notes d'environnement

- Le dossier de travail est synchronisé par un fournisseur cloud. `uv pip list`
  échoue dans ce dossier (`os error -2145452027`), ce qui bloque la compilation
  ESPHome. La compilation a donc été exécutée dans `C:\Temp\anenji`, avec le
  même YAML et le même `secrets.yaml` de test. Ce n'est pas un problème du
  projet.
- Les logs bruts ne sont pas versionnés ; ce document en résume les résultats.
