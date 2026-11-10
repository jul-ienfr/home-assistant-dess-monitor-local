# Marketplace (ex-HACS) — format et publication

Depuis Home Assistant **2026.11**, HACS est intégré à Home Assistant sous le
nom **Marketplace**. Il n'y a plus d'application « Get HACS » à installer :
elle s'arrête à 2026.11 et doit être retirée. Les dépôts déjà installés, les
dépôts personnalisés et les entités de mise à jour sont repris
automatiquement.

- Accès : `Paramètres → Marketplace` (`Settings → Marketplace`).
- Documentation utilisateur :
  <https://www.home-assistant.io/integrations/marketplace/>
- Documentation éditeur :
  <https://contributors.home-assistant.io/marketplace/>
- Annonce : [release notes 2026.11](https://www.home-assistant.io/blog/2026/11/04/release-202611/#welcome-to-the-marketplace)

## Format attendu pour une intégration

Le Marketplace lit `hacs.json` **à la racine du dépôt**, pour chaque version
qu'il installe. Sans ce fichier, il refuse l'installation et les mises à jour.

Structure minimale :

```text
hacs.json
README.md
custom_components/<domain>/
    __init__.py
    manifest.json
    ...
```

Règles principales :

- dépôt GitHub **public** ;
- un seul type de contenu par dépôt (ici : `integration`) ;
- `custom_components/<domain>/` contient tous les fichiers de l'intégration ;
- `manifest.json` contient `domain`, `version`, `documentation`,
  `issue_tracker`, `codeowners` et `name` ;
- la `version` du manifest doit correspondre au **tag de la release** (sans le
  préfixe `v`) ;
- une **release GitHub publiée** est nécessaire pour que les utilisateurs
  reçoivent une version stable. Un tag seul ne suffit pas : le Marketplace
  retombe alors sur le dernier commit de la branche par défaut ;
- le README à la racine est affiché sur la page Marketplace du dépôt.

`hacs.json` accepte notamment :

| Clé | Effet |
|-----|-------|
| `name` | Nom affiché (obligatoire pour HACS et le catalogue) |
| `homeassistant` | Version minimale de Home Assistant pour cette release |
| `hide_default_branch` | Ne pas proposer la branche par défaut comme version |
| `zip_release` + `filename` | Installer depuis une archive ZIP attachée à la release |
| `persistent_directory` | Sous-dossier de l'intégration conservé lors des mises à jour |

Références :
[hacs.json](https://contributors.home-assistant.io/marketplace/reference/hacs-json/),
[structure du dépôt](https://contributors.home-assistant.io/marketplace/reference/repository-structure/),
[releases et mises à jour](https://contributors.home-assistant.io/marketplace/guides/releases/).

## Structure de ce dépôt

Tout est sur la branche `main`, qui est la branche par défaut :

| Élément | Contenu |
|---------|---------|
| `hacs.json` | métadonnées Marketplace |
| `custom_components/dess_monitor_local/` | intégration DESS Monitor Local |
| `INTEGRATION.md` | documentation de l'intégration |
| `README.md` | documentation du firmware ESPHome |
| `anenji.yaml` et le reste | firmware ESPHome Anenji |

Le Marketplace cherche `hacs.json` et `custom_components/` sur la branche par
défaut : c'est pourquoi ils sont à la racine de `main`. Il n'y a plus de
branche d'intégration séparée.

## Installer l'intégration

1. `Paramètres → Marketplace`.
2. En haut à droite : **Add from link** / **Ajouter depuis un lien**.
3. Coller `https://github.com/jul-ienfr/home-assistant-dess-monitor-local`
   (ou `jul-ienfr/home-assistant-dess-monitor-local`) et valider.
4. Choisir **Integration** si le type est demandé.
5. Ouvrir la fiche, **Install**, puis sélectionner la version
   `v1.1.0-beta.4-anenji.2`.

Une intégration avec config flow se charge immédiatement après l'installation.
Les mises à jour et les suppressions nécessitent un redémarrage, proposé par
une réparation.

Le dépôt personnalisé demande une connexion GitHub (device sign-in). Le
Marketplace vérifie les mises à jour d'un dépôt ajouté par lien via l'API
GitHub toutes les 48 heures ; le catalogue est lu toutes les 6 heures. Un
délai de quelques heures est donc normal.

## Publier une nouvelle version

1. Se placer sur `main` :

   ```bash
   git switch main
   git pull
   ```

2. Modifier le code, puis mettre à jour `CHANGELOG.md`.
3. Incrémenter `version` dans
   `custom_components/dess_monitor_local/manifest.json`. Cette valeur doit
   correspondre au futur tag, sans le préfixe `v` (par exemple manifest
   `1.1.0-beta.4-anenji.2` pour le tag `v1.1.0-beta.4-anenji.2`).
4. Committer et pousser :

   ```bash
   git add custom_components CHANGELOG.md
   git commit -m "release: vX.Y.Z"
   git push origin main
   ```

5. Créer et pousser le tag :

   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

6. Sur GitHub : **Releases → Draft a new release**, sélectionner le tag,
   rédiger les notes, puis **Publish release**. Ne pas laisser la release en
   brouillon. Pour une bêta, cocher **Pre-release** : elle ne sera proposée
   qu'aux utilisateurs qui activent l'entité **Pre-release**.
7. Vérifier qu'à ce tag, `hacs.json` et
   `custom_components/dess_monitor_local/manifest.json` sont bien présents et
   que les deux versions correspondent.

Le Marketplace refusera une intégration dont le manifest n'a pas de `version`
valide. Il refusera aussi une release qui exige une version de Home Assistant
supérieure à celle de l'utilisateur ; dans ce cas il propose une version
antérieure compatible.

## Pièges à éviter

- **Tout est sur `main`** : ne pas recréer de branche séparée pour
  l'intégration, sinon le Marketplace ne verra plus `hacs.json` à la racine de
  la branche par défaut.
- **Un tag sans release publiée** ne donne pas de version stable ; le
  Marketplace utilise alors le dernier commit de la branche par défaut.
- **Ne pas modifier un tag existant** : les utilisateurs qui l'ont installé
  gardent leurs fichiers, et le Marketplace ne retrouve plus la version.
- **Ne pas installer l'intégration sur le bus série** si l'ESPHome interroge
  déjà le port Modbus de l'onduleur : un seul maître à la fois. Utiliser le
  transport `eybond` du dongle Wi-Fi ou le hub Eybond multi-dongles.
- **L'ancien HACS** ne doit plus être installé à partir de 2026.11 ; ses
  fichiers sont repris par le Marketplace.
