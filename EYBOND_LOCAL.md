# Contrôle local via le dongle Wi-Fi Eybond / SmartESS

**Cible** : Anenji ANJ-4000W / ANJ-4200W-24V-WIFI (SMG-II, 24 V)

**Version** : 1.0.0 — 2026-11-10

**Statut** : validé sur le matériel du site — lecture des blocs 100, 201 et 300,
puis écriture FC16 de contrôle.

Ce document décrit la voie **la plus directe** pour piloter l'onduleur depuis
Home Assistant sans ESP32 ni passerelle supplémentaire : réutiliser le dongle
Wi-Fi d'origine comme transport local. Le dongle reste maître du bus RS485 de
l'onduleur ; Home Assistant lui parle en Modbus RTU à travers une connexion TCP
inverse.

La carte de registres ne change pas : voir [`PROTOCOL.md`](PROTOCOL.md).

## 1. Résumé

Le dongle Wi-Fi livré avec l'onduleur n'est pas un serveur Modbus TCP. Il
n'écoute ni sur 502 ni sur 8899. En revanche, le modèle **Eybond / SmartESS**
utilisé ici accepte une commande UDP qui lui indique où ouvrir une connexion
TCP sortante :

```text
set>server=<IP de Home Assistant>:<port>;
```

Home Assistant écoute sur ce port, le dongle s'y connecte, puis les trames
Modbus RTU sont transportées dans le canal `Forward2Device` du protocole
Eybond. C'est ce mécanisme qui permet de « passer par le NAT » : c'est le
dongle qui initie la connexion, exactement comme il le fait vers le cloud.

```text
Dongle 192.168.68.57 ── UDP 58899 « set>server=192.168.68.60:8899; » ──► LAN
Dongle 192.168.68.57 ── TCP 8899 (connexion sortante) ────────────────► HA 192.168.68.60:8899
HA 192.168.68.60 ── FC4 / Modbus RTU ──► dongle ── RS485 ──► onduleur SMG-II
```

Aucune redirection de port WAN n'est nécessaire. Le routeur ne fait que
transporter une connexion sortante du dongle vers Home Assistant.

## 2. Matériel identifié sur le site

| Élément | Valeur relevée |
|---------|----------------|
| Home Assistant principal | `192.168.68.60` (`homeassistant.local`) |
| Seconde instance Home Assistant | `192.168.68.53` — à identifier avant installation |
| Dongle Wi-Fi | `192.168.68.57`, MAC `E8:88:6C:38:19:15` |
| Modèle / PN complet | Eybond, `E50000221162926051` |
| Firmware du dongle | `8.50.12.3` |
| Ports du dongle | `80` ouvert (interface web) ; `502` et `8899` fermés |
| Onduleur | SMG-II 24 V, adresse Modbus `1`, 9600 8N1 |
| ESP32 existant | `192.168.68.62` — à ne pas laisser poller le même bus |
| Routeur | `192.168.68.1`, LAN `192.168.68.0/22`, broadcast `192.168.71.255` |

Le dongle est bien celui de l'onduleur : son interface web et son heartbeat
Eybond répondent, et les lectures Modbus renvoient des valeurs cohérentes
(tension batterie, tension AC, mode de sortie).

> Les deux instances Home Assistant répondent sur le port 8123. Choisir une
> seule instance pour héberger l'intégration : un seul processus doit écouter
> sur 8899. Sinon, les deux se disputent la connexion du dongle.

## 3. Pourquoi le port 502 ne répond pas

Un scan TCP classique du dongle donne :

| Port | Résultat | Interprétation |
|-----:|----------|----------------|
| 80 | ouvert | interface web de configuration |
| 502 | fermé | aucun serveur Modbus TCP |
| 8899 | fermé | aucun serveur TCP local |
| 58899/UDP | écoute | réception des commandes `set>server=` |

Le dongle est un **client** qui se connecte au cloud. Pour le détourner vers
Home Assistant, il faut lui envoyer la commande UDP sur le port 58899, puis
accepter sa connexion TCP. C'est exactement ce que fait l'intégration
`dess_monitor_local` en mode « EyBond hub ».

## 4. Validation sur le matériel

Les essais ont été réalisés le 2026-11-10 depuis le poste `192.168.68.56`,
avec le dongle `192.168.68.57` et l'onduleur en service.

### 4.1 Connexion et heartbeat

Après l'annonce UDP, le dongle ouvre la connexion TCP et envoie un heartbeat
dont le payload contient le PN :

```text
UDP  -> 192.168.68.57:58899   set>server=192.168.68.56:8899;
TCP  <- 192.168.68.57:50873
RX   tid=1 devcode=0x0102 fc=1 payload=453530303030323231313632393236303531
PN   E50000221162926051
```

### 4.2 Lectures Modbus

Les trois blocs utilisés par l'intégration ont été lus sans erreur :

| Bloc | Registres | Résultat |
|------|-----------|----------|
| Défauts | 100–115 | lu |
| Mesures | 201–231 | lu |
| Configuration | 300–343, 406, 420 | lu |

Exemples de valeurs décodées lors du relevé :

| Grandeur | Registre | Valeur |
|----------|---------:|--------|
| Tension AC d'entrée | 202 | 235,5 V |
| Fréquence d'entrée | 203 | 49,98 Hz |
| Puissance d'entrée | 204 | 65 W |
| Tension AC de sortie | 210 | 236,1 V |
| Puissance active de sortie | 213 | 55 W |
| Tension batterie | 215 | 28,1 V |
| Courant batterie | 216 | −1,4 A |
| Puissance batterie | 217 | −39 W |
| Priorité de sortie | 301 | `3` = SUB |
| Tension de sortie réglée | 320 | 230,0 V |
| Fréquence de sortie réglée | 321 | 50,00 Hz |
| Tension bulk | 324 | 28,5 V |
| Tension float | 325 | 27,2 V |
| Priorité de charge | 331 | `1` = Solar First |
| Courant de charge max | 332 | 100,0 A |
| Courant de charge réseau max | 333 | 80,0 A |

### 4.3 Écriture

L'onduleur refuse la fonction Modbus **06** (écriture d'un registre unique) :
la requête reste sans réponse. La fonction **16** (écriture de plusieurs
registres) est acceptée :

```text
FC06 registre 305 -> pas de réponse
FC16 registre 305, valeur 0 -> OK (fonction 16)
```

Le test FC16 écrivait la valeur déjà présente (`0`), donc aucun état n'a été
modifié. L'intégration `dess_monitor_local` essaie FC06 puis bascule
automatiquement sur FC16 ; c'est le comportement attendu pour ce firmware.

### 4.4 Correctif de compatibilité

Le correctif de `patches/` a été vérifié sur le dongle :

- extraction du PN complet : `E50000221162926051` (18 caractères) ;
- écriture SUB via le mapping corrigé : requête FC16 acceptée
  (`{"status": "OK", "func": 16}`) ;
- relecture du registre 301 après ce test : toujours `3` (SUB). L'écriture
  était volontairement une écriture de la valeur déjà présente, donc le mode
  de l'onduleur n'a pas changé.

### 4.5 Audit complet du 2026-11-10

L'outil `tools/eybond_audit.py` a relu toutes les mesures et toute la
configuration, puis testé les écritures. Résultats :

| Contrôle | Résultat |
|----------|----------|
| Lecture des blocs 100-115, 201-231, 232-234, 300-343, 406, 420, 426, 643 | OK |
| Invariants physiques (tensions, fréquences, températures, puissance) | OK |
| Écriture FC16 valeur identique sur les 32 registres configurables | 32/32 OK |
| Changement réel (305 rétroéclairage 0 → 1 → 0) | OK |
| Rejet des valeurs hors plage (303=4, 305=2, 337=91) | exception 03, valeur conservée |
| `426=1` sans défaut actif | exception 03 (attendu) |

Les correspondances de mesures ont été vérifiées par cohérence :

- `217 = 215 × 216` : 27,9 V × −1,4 A = −39 W ;
- `208 ≈ 204 − 213` avec la convention positive = sortie onduleur ;
- `225 = 213 / 643` : 51 W / 4200 W = 1 % ;
- `202` ≈ `210` et `203` ≈ `212` : entrée et sortie à ~236 V / 50 Hz.

Paramètres présents sur l'onduleur mais absents du YAML avant l'audit :
`341` (SOC retour réseau), `342` (SOC retour batterie) et `343` (coupure basse
SOC). Ils ont été ajoutés, avec des bornes cohérentes avec le firmware. Le
registre `406` (mode d'allumage) était déjà piloté par le YAML mais manquait
dans `PROTOCOL.md` ; la documentation a été complétée.

Bornes resserrées après l'audit :

- OVP minimum 28,0 V (au lieu de 24,0 V) pour rester au-dessus de la charge ;
- courant de charge max 100 A et courant réseau max 80 A (maxima réels lus) ;
- tension de sortie en select 220/230/240 V et fréquence 50/60 Hz ;
- mode de sortie limité à `Single`, les modes parallèle/phase exigeant
  plusieurs onduleurs ;
- diagnostic `Configuration Incoherent` pour les combinaisons
  inter-paramètres dangereuses.

## 5. Installation dans Home Assistant

### 5.1 Prérequis

- Home Assistant sur `192.168.68.60` (ou l'instance choisie), accessible depuis
  le dongle.
- Marketplace disponible (Home Assistant 2026.11+), ou accès au dossier
  `config/custom_components`. HACS est intégré au Marketplace depuis 2026.11 ;
  l'application « Get HACS » n'est plus nécessaire.
- Port TCP `8899` libre sur l'hôte Home Assistant.
- Un seul maître sur le bus RS485 : si l'ESP32 `192.168.68.62` est encore
  câblé au même port COM, le débrancher ou désactiver son polling avant de
  continuer.
- L'application cloud SmartESS / DESS Monitor sera hors ligne pendant que Home
  Assistant contrôle le dongle. C'est normal (voir les limites).

### 5.2 Installer l'intégration

Deux dépôts sont utilisables :

| Dépôt | Version | Contenu |
|-------|---------|---------|
| **Fork Anenji** (recommandé) | `1.1.0-beta.4-anenji.2` | beta.3 + SUB + PN complet + SOC réel + pilotage complet |
| Upstream | `v1.1.0-beta.3` | beta.3 non corrigée |

Le fork est intégré à la branche `main` du dépôt :
<https://github.com/jul-ienfr/home-assistant-dess-monitor-local>
(release `v1.1.0-beta.4-anenji.2`).

Il reprend la beta.3 upstream et ajoute le correctif SUB / PN complet décrit au
§ 7.4, les valeurs réelles de SOC et de puissance apparente, la gestion des
NAK et le démarrage non bloquant. Le transport Eybond reste celui de
l'upstream.

Depuis Home Assistant 2026.11, HACS est intégré sous le nom **Marketplace**
(`Paramètres → Marketplace`). L'application « Get HACS » n'est plus nécessaire
et doit être retirée. Le Marketplace lit `hacs.json` et
`custom_components/dess_monitor_local/` sur la branche `main`.

Via Marketplace :

1. `Paramètres → Marketplace`.
2. En haut à droite, **Add from link** / **Ajouter depuis un lien**.
3. Coller `https://github.com/jul-ienfr/home-assistant-dess-monitor-local`,
   puis choisir **Integration** si le type est demandé.
4. Ouvrir la fiche du dépôt, **Install**, et sélectionner la version
   `v1.1.0-beta.4-anenji.2`.
5. L'intégration a un config flow : elle se charge immédiatement. Sinon,
   redémarrer Home Assistant, puis l'ajouter dans
   `Paramètres → Appareils et services`.

Le Marketplace installe la dernière **release GitHub publiée**, pas un simple
tag. La version de `manifest.json` doit correspondre au tag (sans le préfixe
`v`). Toute nouvelle version doit donc être publiée sur `main` ; voir
[`MARKETPLACE.md`](MARKETPLACE.md).

Pour rester sur l'upstream, ajouter à la place
`https://github.com/Antoxa1081/home-assistant-dess-monitor-local`, activer les
préversions et installer `v1.1.0-beta.3`, puis appliquer le patch du § 7.4.1.

Installation manuelle : télécharger l'archive du dépôt, puis copier le dossier
`custom_components/dess_monitor_local` dans `/config/custom_components/`, et
redémarrer Home Assistant.

> **Un seul maître sur le bus Modbus.** Ne pas créer une entrée avec le
> transport `serial` ou `modbus` sur le port COM déjà interrogé par l'ESPHome :
> deux maîtres se marcheraient dessus. Utiliser le transport `eybond` du
> dongle Wi-Fi, le hub Eybond multi-dongles, ou désactiver le polling de
> l'ESP32 avant de continuer.

> **Changement de PN** : le fork lit le PN complet (18 caractères). Si un
> onduleur enfant a déjà été créé avec l'ancien PN tronqué (14 caractères),
> le supprimer puis le reconfigurer après l'installation du fork.

### 5.3 Créer le hub EyBond

1. **Paramètres → Appareils et services → Ajouter une intégration**.
2. Choisir **DESS Monitor Local**.
3. Choisir **EyBond hub** (et non « Single inverter »).
4. Renseigner :

| Champ | Valeur |
|-------|--------|
| Nom | `Anenji dongle` |
| Bind host | `0.0.0.0` |
| Port | `8899` |
| Broadcast | `192.168.71.255` |
| Announce IP | `192.168.68.60` |
| Intervalle de mise à jour | `10` s |

`Announce IP` doit être l'adresse **LAN de la machine qui exécute Home
Assistant**, jamais l'adresse d'un conteneur Docker. Le broadcast
`192.168.71.255` correspond au sous-réseau `/22` du site ; `255.255.255.255`
fonctionne aussi dans la plupart des cas.

5. Valider et attendre 30 à 60 secondes. L'appareil « Discovered dongles »
   doit passer à `1`, et une notification propose de configurer le dongle.

### 5.4 Configurer l'onduleur enfant

1. Ouvrir **Configurer** sur l'entrée DESS Monitor Local.
2. Sélectionner le dongle découvert.
3. Choisir le protocole **Modbus / SMG-II**.
4. Mettre l'adresse RS485 à `1`.
5. Activer l'appareil, puis valider.

L'entrée se recharge et les entités de l'onduleur apparaissent : tensions,
courants, puissances, températures, SOC, priorités et courant de charge
réseau.

### 5.5 Vérifier

- La tension batterie doit être proche de la tension réelle (environ 28 V sur
  un parc 24 V chargé).
- La tension AC de sortie doit être proche de 230 V.
- Le mode de sortie doit refléter l'écran de l'onduleur.
- L'horodatage de dernière mise à jour doit avancer toutes les 10 s.

## 6. NAT, Docker et VLAN

### 6.1 Home Assistant OS ou installation native

Rien à configurer côté routeur. Le dongle ouvre une connexion sortante vers
`192.168.68.60:8899`. Il suffit que le pare-feu de l'hôte accepte le TCP 8899
en entrée depuis le réseau local.

### 6.2 Home Assistant en Docker

Le port doit être publié et l'IP annoncée doit être celle de l'hôte :

```yaml
services:
  homeassistant:
    ports:
      - "8123:8123/tcp"
      - "8899:8899/tcp"
```

Avec `network_mode: host`, la publication n'est pas nécessaire, mais le port
8899 doit rester libre sur l'hôte.

> Ne jamais mettre l'IP du conteneur dans `Announce IP`. Le dongle ne peut pas
> router vers le réseau interne de Docker. Utiliser l'IP LAN de la machine
> hôte.

Sous Docker Desktop pour Windows, le NAT interne peut compliquer les tests :
vérifier que le port publié est bien joignable depuis le poste
(`Test-NetConnection <ip-hote> -Port 8899`) et autoriser le trafic entrant dans
le pare-feu Windows.

### 6.3 Routeur et VLAN

- Aucune redirection de port depuis Internet.
- Le dongle et Home Assistant doivent pouvoir se joindre en TCP 8899.
- Si le dongle est dans un VLAN IoT, autoriser :
  - `dongle → HA` en TCP 8899 ;
  - les broadcasts UDP 58899 depuis HA vers le VLAN du dongle (ou au moins
    l'annonce vers l'IP du dongle, selon le routeur) ;
  - désactiver l'isolation client entre les deux.
- Le NAT du routeur n'a rien à configurer : la connexion est initiée par le
  dongle.

## 7. Limites connues

### 7.1 Une seule destination

Le dongle ne peut pas être simultanément connecté au cloud et à Home Assistant.
Pendant le contrôle local, l'application SmartESS / DESS Monitor indique
l'appareil hors ligne. Lorsque Home Assistant ferme la connexion (arrêt de
l'intégration, redémarrage), le dongle retourne au cloud après quelques
secondes.

### 7.2 Un seul écouteur

Un seul processus peut écouter sur le port 8899 et posséder la session du
dongle. Ne pas lancer deux instances Home Assistant, ni un script de diagnostic
en même temps que l'intégration. Le script `tools/eybond_probe.py` doit être
utilisé après avoir arrêté l'intégration.

### 7.3 PN tronqué dans la version beta.3 upstream

Le heartbeat contient le PN complet sur 18 caractères
(`E50000221162926051`), mais `v1.1.0-beta.3` ne lit que les 14 premiers :

```text
E5000022116292
```

L'intégration reste cohérente avec elle-même : elle utilise cette valeur
tronquée comme identifiant interne. Si une configuration manuelle le demande,
utiliser la valeur affichée par Home Assistant, pas le PN complet. Le fork
`1.1.0-beta.3-anenji.3` lit le PN complet ; un correctif est aussi fourni dans
`patches/` pour ceux qui restent sur l'upstream.

### 7.4 Priorité de sortie SUB non reconnue (beta.3 upstream)

Au moment du relevé, l'onduleur est en mode **SUB** (registre 301 = `3`). La
version beta.3 upstream ne connaît que `0` (Utility First), `1` (Solar First)
et `2` (SBU) :

- la lecture affiche **Utility First** au lieu de SUB ;
- le sélecteur ne propose pas SUB.

> Ne pas « corriger » l'affichage en resélectionnant Utility First : cela
> écrirait réellement `0` dans le registre 301 et changerait le mode de
> l'onduleur.

Trois solutions :

1. installer le **fork Anenji** (§ 5.2), qui contient déjà SUB et le PN complet ;
2. laisser la priorité de sortie se régler sur l'écran de l'onduleur ;
3. appliquer le correctif `patches/dess-monitor-local-beta3-anenji.patch` sur
   l'upstream, puis redémarrer Home Assistant.

Le correctif est fourni « tel quel » pour la beta.3 ; le fork
`1.1.0-beta.3-anenji.3` l'intègre déjà. Une mise à jour de l'intégration peut
rendre le patch obsolète ; dans ce cas, ouvrir une issue upstream pour intégrer
SUB et le PN complet.

### 7.4.1 Faut-il créer un fork ?

Non, il est déjà intégré :
<https://github.com/jul-ienfr/home-assistant-dess-monitor-local>

La branche `main` contient la beta.3 upstream, le correctif SUB et le PN
complet, ainsi que les correctifs de la version
`1.1.0-beta.3-anenji.3`. Le tag `v1.1.0-beta.3-anenji.3` marque exactement
cette version. La branche contient `hacs.json` et `custom_components/`, donc
le Marketplace peut l'installer directement. Aucun fork supplémentaire n'est
nécessaire. Une nouvelle release de l'intégration doit être taguée sur `main`.

Pour ceux qui préfèrent rester sur le dépôt upstream, le patch reste
applicable. Copier d'abord `patches/dess-monitor-local-beta3-anenji.patch`
dans `/config/patches/`, puis appliquer :

```bash
cd /config
patch -p1 < /config/patches/dess-monitor-local-beta3-anenji.patch
```

Ou, si `git apply` est disponible :

```bash
cd /config
git apply patches/dess-monitor-local-beta3-anenji.patch
```

Redémarrer Home Assistant après l'application. Une mise à jour via le
Marketplace (ex-HACS) écrase les fichiers : il faudra réappliquer le patch ou
passer à une version upstream qui l'intègre.

> **À faire avant de configurer l'onduleur enfant** : le patch remplace le PN
> tronqué par le PN complet comme clé de routage. Si un enfant a déjà été créé
> avec l'ancien PN, le supprimer puis le reconfigurer après le patch.

### 7.5 Écritures et bouton de défaut

Les écritures passent par FC16 et sont validées. Dans la beta.3 upstream, le
bouton **Exit Fault State** utilise encore le chemin Modbus TCP direct et ne
fonctionne pas sur un enfant `eybond-modbus://`. Le fork
`1.1.0-beta.3-anenji.3` passe par `ModbusAdapter` et corrige ce point ; sinon,
utiliser l'écran de l'onduleur pour acquitter un défaut.

### 7.6 Intégration en beta

`1.1.0-beta.3-anenji.3` reste une préversion. Sauvegarder la configuration
Home Assistant avant l'installation et relire les notes de version avant chaque
mise à jour.

## 8. Dépannage

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| Aucune connexion du dongle | `Announce IP` incorrecte | Mettre l'IP LAN de l'hôte HA |
| Aucune connexion | Port 8899 fermé/pare-feu | Ouvrir le TCP 8899 en entrée |
| Aucune connexion | Dongle et HA sur des VLAN séparés | Autoriser dongle → HA:8899 |
| Connexion puis aucune donnée | Adresse RS485 ou protocole faux | Protocole `modbus`, adresse `1` |
| Connexion instable | ESP32 poll aussi le bus | Un seul maître RS485 |
| Connexion instable | Deux écouteurs sur 8899 | Arrêter l'autre instance/script |
| Le dongle revient au cloud | Home Assistant a arrêté l'écoute | Redémarrer l'intégration |
| Priorité affichée « Utility First » | Mode SUB non mappé | Correctif ou écran onduleur |
| Écriture sans effet | FC06 refusée | L'intégration bascule FC16 ; vérifier les logs |
| L'app SmartESS est hors ligne | Contrôle local actif | Comportement normal |

Activer les logs détaillés dans `configuration.yaml` :

```yaml
logger:
  default: warning
  logs:
    custom_components.dess_monitor_local: debug
    custom_components.dess_monitor_local.api.protocols.eybond_dongle: debug
```

## 9. Sécurité

- **Ne jamais exposer le port 8899 sur Internet.** Le protocole Eybond et
  Modbus n'authentifient pas et ne chiffrent pas.
- Placer le dongle dans un VLAN IoT et n'autoriser que les flux nécessaires
  vers Home Assistant.
- L'interface web du dongle (port 80) peut être accessible sans authentification
  forte : la restreindre au réseau d'administration.
- Sauvegarder les valeurs des registres 300–337 avant toute écriture.
- Tester les écritures critiques avec une valeur réversible et vérifier les
  bornes dans [`PROTOCOL.md`](PROTOCOL.md).

## 10. Références

- [DESS Monitor Local](https://github.com/Antoxa1081/home-assistant-dess-monitor-local)
  — intégration Home Assistant d'origine.
- [Fork Anenji](https://github.com/jul-ienfr/home-assistant-dess-monitor-local)
  — beta.3 + SUB + PN complet + SOC réel, intégré sur `main`
  (release `v1.1.0-beta.4-anenji.2`).
- [Documentation EyBond du projet](https://github.com/Antoxa1081/home-assistant-dess-monitor-local/blob/main/wiki/EyBond-Transport-Setup.md)
  — transport inverse, Docker et dépannage.
- [`PROTOCOL.md`](PROTOCOL.md) — carte des registres SMG-II.
- [`REMOTE_ACCESS.md`](REMOTE_ACCESS.md) — comparaison des autres voies sans ESP32.
- [`tools/eybond_probe.py`](tools/eybond_probe.py) — diagnostic lecture seule.
