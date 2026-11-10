# Correctifs optionnels

## `dess-monitor-local-beta3-anenji.patch`

Correctif de compatibilité pour **DESS Monitor Local `v1.1.0-beta.3`** :

- lit le PN complet du dongle (18 caractères au lieu de 14) ;
- ajoute le mode de sortie **SUB** (registre 301 = `3`) à la lecture et au
  sélecteur Home Assistant ;
- mappe l'écriture de SUB sur la valeur Modbus `3`.

Le patch ne modifie pas le transport Eybond ni les lectures. Il a été vérifié
sur le dongle du site : PN complet extrait, écriture FC16 de SUB acceptée
(écriture de la valeur déjà présente, donc sans changement de mode).

Une version déjà corrigée est archivée dans le dépôt
[jul-ienfr/home-assistant-dess-monitor-local](https://github.com/jul-ienfr/home-assistant-dess-monitor-local)
sur la branche
[`archive/dess-monitor-local`](https://github.com/jul-ienfr/home-assistant-dess-monitor-local/tree/archive/dess-monitor-local)
(tag `v1.1.0-beta.3-anenji.3`). Elle contient ce correctif SUB / PN complet,
plus le SOC et la puissance apparente réels, la gestion des NAK, le démarrage
non bloquant et les entités vSoC résolues par registre. La branche `main` de ce
dépôt contient désormais le projet ESPHome Anenji. Le patch reste utile pour
rester sur le dépôt upstream.

Application, depuis `/config` :

```bash
patch -p1 < /config/patches/dess-monitor-local-beta3-anenji.patch
```

ou, si `git apply` est disponible :

```bash
git apply patches/dess-monitor-local-beta3-anenji.patch
```

Redémarrer Home Assistant après l'application. Si un onduleur enfant a déjà été
configuré avec l'ancien PN tronqué, le supprimer et le reconfigurer : le PN
complet devient la clé de routage.

Une mise à jour HACS de l'intégration écrase les fichiers ; réappliquer le
patch après la mise à jour, ou utiliser directement le fork.
