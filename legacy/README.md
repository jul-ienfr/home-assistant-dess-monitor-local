# Configurations archivées — ne pas flasher

Ces fichiers sont conservés pour l'historique et la comparaison. Ils ne
correspondent pas à la configuration fonctionnelle actuelle et **ne doivent pas
être flashés**.

| Fichier | Ancien nom | Pourquoi il est archivé |
|---------|------------|--------------------------|
| `Anenji.legacy.YAML` | `Anenji.YAML` | Carte de registres de type Axpert (200/201/250-259) au lieu de SMG-II ; températures ×0,1 ; signe batterie inversé ; serveur web ouvert. |
| `Anenji_V24_CurrentRegisters.legacy.yaml` | `Anenji_V24_CurrentRegisters.yaml` | Même carte fausse ; `update_interval` interdit sur `text_sensor.modbus_controller` ; défauts lus en hexadécimal. |
| `Anenji_V24_SMG2.legacy.yaml` | `Anenji_V24_SMG2.yaml` | Carte la plus proche, mais `button.modbus_controller` n'existe pas ; `std::stoul` + `try/catch` incompatible ; températures ×0,1 ; `write_lambda` incorrect. |

## Utiliser la bonne configuration

```powershell
esphome config anenji.yaml
esphome run anenji.yaml
```

La carte de registres vérifiée est dans [PROTOCOL.md](../PROTOCOL.md) et le
contrat détaillé dans
[`specs/001-anenji-functional/contracts/register-map.md`](../specs/001-anenji-functional/contracts/register-map.md).

Les anciennes configurations restent disponibles dans l'historique Git :

```powershell
git log --oneline -- Anenji.YAML
git show <commit>:Anenji.YAML
```
