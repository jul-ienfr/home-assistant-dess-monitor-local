# Contrôler l'onduleur sans ESP32

**Cible** : Anenji ANJ-4000W / ANJ-4200W-24V-WIFI (SMG-II, 24 V)

**Version** : 1.0.0 — 2026-11-10

Ce document décrit les solutions pour lire et piloter l'onduleur **sans
ESP32**, en passant par le réseau local ou par le cloud. La carte de registres
reste celle de [`PROTOCOL.md`](PROTOCOL.md) : le protocole Modbus RTU ne change
pas selon le matériel qui l'émet.

## 1. L'IP du module Wi-Fi n'est pas celle de l'onduleur

Le module Wi-Fi livré avec l'onduleur est une **passerelle série → cloud** :

- il dialoguait déjà en Modbus RTU avec l'onduleur par son port COM ;
- il ouvre des connexions **sortantes** vers l'application du fabricant
  (SmartESS, SolarMAN ou équivalent selon le dongle) ;
- sur la plupart des modèles, il **n'écoute aucun port en local**.

Avoir Home Assistant et le dongle sur le même routeur ne suffit donc pas. Pour
contrôler l'onduleur, il faut soit parler au dongle par un protocole qu'il
expose, soit remplacer/insérer une passerelle locale sur le bus série.

> Le dongle Wi-Fi n'est pas l'onduleur : l'IP appartient au dongle, et
> l'onduleur n'a généralement pas de pile TCP/IP.

Le dongle **Eybond / SmartESS** de ce site expose bien un protocole local, mais
pas sous forme de serveur Modbus TCP : il accepte une annonce UDP
(`set>server=<ip>:<port>;`) et ouvre lui-même une connexion TCP vers Home
Assistant. C'est la voie décrite dans [`EYBOND_LOCAL.md`](EYBOND_LOCAL.md), et
elle a été validée sur le matériel (lecture des registres 100/201/300 et
écriture FC16).

## 2. Diagnostic en cinq minutes

Récupérer l'IP du dongle dans le bail DHCP du routeur, puis tester les ports
depuis un PC du même réseau :

```powershell
$ip = "192.168.1.50"   # IP du dongle, pas de l'onduleur

foreach ($port in 502, 8899, 80, 443, 23) {
    $open = Test-NetConnection $ip -Port $port -InformationLevel Quiet `
        -WarningAction SilentlyContinue
    "{0,-4} {1}" -f $port, $(if ($open) { "ouvert" } else { "fermé" })
}
```

| Port | Signification probable |
|-----:|------------------------|
| 502 | Modbus TCP ou RTU encapsulé : à tester en lecture |
| 8899 | Protocole Solarman propriétaire, souvent **pas** du Modbus |
| 58899/UDP | Écoute Eybond : accepte `set>server=<ip>:<port>;` (non testable avec `Test-NetConnection`) |
| 80 / 443 | Page web de configuration du dongle |
| 23 | Telnet de diagnostic, rarement utile |

Si le port 502 répond, tenter une lecture du registre 201 (mode de
fonctionnement) avec un client Modbus. Deux variantes existent :

- **Modbus TCP** (en-tête MBAP) : la passerelle traduit déjà les trames ;
- **RTU over TCP** (trame RTU + CRC, sans MBAP) : la passerelle est
  transparente.

Si les ports 502 et 8899 sont fermés, le dongle n'expose pas Modbus TCP. Ce
n'est pas une conclusion d'inutilisabilité : tester la voie Eybond (section 3)
avant de le considérer comme uniquement cloud. Sinon, passer à la section 4
(passerelle série) ou 6 (cloud).

## 3. Option A — Dongle Wi-Fi d'origine (Eybond / SmartESS)

C'est la voie la plus directe lorsque le dongle d'origine est déjà installé :
aucun matériel supplémentaire et aucune redirection de port depuis Internet.

Principe :

- Home Assistant écoute en TCP sur `8899` et annonce son adresse au dongle en
  UDP sur `58899` : `set>server=<ip-ha>:8899;` ;
- le dongle ouvre lui-même la connexion TCP vers Home Assistant ;
- les trames Modbus RTU (FC3 en lecture, FC16 en écriture) sont transportées
  dans le canal `Forward2Device` du protocole Eybond.

C'est le dongle qui initie la connexion : le NAT du routeur n'a rien à
configurer. En Docker, publier `8899:8899/tcp` et annoncer l'IP LAN de l'hôte,
jamais celle du conteneur.

Validation sur ce site : dongle `192.168.68.57`, lectures des blocs 100, 201 et
300, écriture FC16 acceptée (FC06 refusée). L'intégration Home Assistant
utilisée est **DESS Monitor Local** en mode « EyBond hub ».

Limites à connaître : le cloud SmartESS est hors ligne pendant le contrôle
local et un seul processus peut écouter sur 8899. La beta.3 upstream tronque
le PN à 14 caractères et ne mappe pas le mode de sortie SUB (registre 301 =
3) ; le fork actuel (`1.1.0-beta.4-anenji.3`) corrige ces deux points.

Procédure complète, valeurs mesurées et dépannage :
[`EYBOND_LOCAL.md`](EYBOND_LOCAL.md).

## 4. Option B — Passerelle série → Ethernet

C'est le remplacement direct de l'ESP32, sans cloud et sans modifier
l'onduleur. C'est la voie la plus prévisible pour les écritures.

### 4.1 Matériel

- une passerelle série → Ethernet, par exemple USR-TCP232-410S,
  Waveshare RS232/RS485 to Ethernet ou PUSR USR-TCP232-302 ;
- une alimentation adaptée à la passerelle ;
- un câble vers le port COM de l'onduleur (voir [`WIRING.md`](WIRING.md)).

### 4.2 Câblage

| Port onduleur | Câblage passerelle |
|---------------|--------------------|
| RS232 (RJ45) | TX, RX et GND ; ne pas utiliser la broche 12 V |
| RS485 (A+/B-) | A vers A, B vers B, GND commun |

> Le RJ45 de l'onduleur peut porter du **12 V** sur la broche 4. Vérifier au
> multimètre avant de brancher la passerelle, et ne jamais relier cette broche
> à un port série.

### 4.3 Configuration de la passerelle

- mode **TCP Server** (ou « transparent ») ;
- **9600 bauds, 8 bits, sans parité, 1 stop** ;
- port local 4001 ou 502 selon la documentation de la passerelle ;
- IP fixe ou réservation DHCP ;
- si la passerelle propose un mode **Modbus TCP**, l'activer ; sinon laisser en
  mode transparent (RTU over TCP).

### 4.4 Configuration Home Assistant

Avec une passerelle transparente (RTU over TCP), le type est `rtuovertcp` :

```yaml
modbus:
  - name: anenji
    type: rtuovertcp
    host: 192.168.1.50
    port: 4001
    delay: 1
    timeout: 3
    message_wait_milliseconds: 200

    sensors:
      - name: "Anenji Battery Voltage"
        address: 215
        input_type: holding
        data_type: int16
        scale: 0.1
        precision: 1
        unit_of_measurement: V
        device_class: voltage
        state_class: measurement

      - name: "Anenji Battery SOC"
        address: 229
        input_type: holding
        data_type: uint16
        unit_of_measurement: "%"
        device_class: battery
        state_class: measurement
```

Avec une passerelle qui traduit réellement en Modbus TCP, remplacer par :

```yaml
    type: tcp
    port: 502
```

Les adresses, types et échelles sont dans [`PROTOCOL.md`](PROTOCOL.md).

## 5. Option C — Adaptateur USB sur la machine Home Assistant

Si le serveur Home Assistant est proche de l'onduleur, un adaptateur
USB-RS485 (ou USB-RS232 avec un MAX3232) suffit.

```yaml
modbus:
  - name: anenji
    type: serial
    port: /dev/ttyUSB0
    baudrate: 9600
    bytesize: 8
    parity: N
    stopbits: 1
    delay: 1
    timeout: 3
```

- Home Assistant OS : l'adaptateur apparaît dans `/dev/serial/by-id/...` ;
- Home Assistant en Docker : passer le périphérique au conteneur
  (`--device=/dev/ttyUSB0`) ;
- Windows : utiliser `COM3`, `COM4`, etc.

C'est la solution la moins chère, mais elle impose un câble entre le serveur
Home Assistant et l'onduleur.

## 6. Option D — Cloud du fabricant

Sans aucun matériel supplémentaire, on peut passer par le compte cloud :

- application SmartESS / SolarMAN du dongle ;
- intégration Marketplace (ex-HACS) ou pont MQTT qui interroge l'API du
  fabricant ;
- certains projets, comme `anenji-ha-bridge`, exposent les mesures en MQTT.

Limites à connaître :

- dépendance à Internet et au compte fabricant ;
- latence et fréquence de rafraîchissement imposées ;
- écritures souvent absentes ou limitées ;
- API non contractuelle, pouvant changer sans préavis.

Cette voie convient à la **surveillance**, pas à une régulation temps réel.

## 7. Écriture des réglages depuis Home Assistant

L'intégration Modbus de Home Assistant expose :

- des `sensors` pour la lecture ;
- des `switches` pour les registres tout-ou-rien ;
- l'action `modbus.write_register` pour écrire une valeur.

Point important pour l'Anenji : le firmware d'origine utilise la **fonction 16**
(écriture de plusieurs registres). `modbus.write_register` utilise la fonction
06. Selon la version de l'onduleur, FC06 peut être refusée.

Sur la voie Eybond, l'intégration DESS Monitor Local essaie FC06 puis bascule
automatiquement sur FC16. Ce comportement a été validé sur l'onduleur du site
(FC06 sans réponse, FC16 acceptée) ; voir [`EYBOND_LOCAL.md`](EYBOND_LOCAL.md).

Pour les commandes tout-ou-rien, utiliser un `switch` avec
`write_type: holdings` (FC16) :

```yaml
    switches:
      - name: "Anenji LCD Backlight"
        address: 305
        write_type: holdings
        command_on: 1
        command_off: 0
```

Pour les valeurs numériques (tension de charge, courant maximal, etc.) :

1. tester d'abord `modbus.write_register` sur un registre non critique ;
2. si FC06 est refusée, passer par un `switch` `write_type: holdings` (deux
   valeurs seulement) ou par un petit pont `pymodbus` / Node-RED qui parle
   FC16 ;
3. conserver les bornes `min`/`max` et noter la valeur d'origine avant toute
   écriture.

Les plages et les adresses sont dans [`PROTOCOL.md`](PROTOCOL.md).

## 8. Comparaison

| Solution | Local | Contrôle | Matériel | Latence | Dépendance |
|----------|:-----:|:--------:|----------|---------|------------|
| Dongle d'origine (Eybond) | Oui | Oui* | 0 € | Faible | Intégration beta ; cloud coupé |
| Passerelle série → Ethernet | Oui | Oui | 30-60 € | Faible | Aucune |
| USB sur le serveur HA | Oui | Oui | 10-20 € | Faible | HA proche de l'onduleur |
| Cloud fabricant | Non | Partiel | 0 € | Élevée | Internet + compte |

\* La beta.3 upstream ne mappe pas encore le mode SUB ni le bouton
d'acquittement de défaut sur le transport Eybond ; le fork
`1.1.0-beta.3-anenji.3` les ajoute. La lecture et les écritures FC16 sont
validées sur le dongle du site.

## 9. Sécurité

- Modbus TCP et le transport Eybond **n'authentifient pas** et **ne chiffrent
  pas** : ne jamais exposer les ports 502 ou 8899 sur Internet.
- L'interface web du dongle (port 80) peut être accessible sans authentification
  forte : la restreindre au réseau d'administration.
- Placer l'onduleur et la passerelle sur un VLAN IoT, avec un filtrage vers
  Home Assistant uniquement.
- Utiliser un mot de passe unique pour le compte cloud et activer la
  double authentification si elle existe.
- Avant une écriture : sauvegarder les registres, vérifier la borne, tester un
  réglage réversible.

## 10. Recommandation

- **Dongle d'origine déjà installé** : option A (Eybond), validée sur ce site,
  sans matériel supplémentaire. Accepter que le cloud soit coupé pendant le
  contrôle local et que l'intégration soit encore en beta.
- **Contrôle local fiable, écritures prévisibles** : passerelle série →
  Ethernet (option B).
- **Installation compacte** : adaptateur USB sur le serveur HA (option C).
- **Surveillance sans matériel** : cloud (option D), en acceptant ses limites.

Le dongle Wi-Fi d'origine peut parfois être reflashé en ESPHome, mais il
redevient alors un ESP32 : cette voie est hors du périmètre de ce document.

## 11. Références

- [Intégration Modbus de Home Assistant](https://www.home-assistant.io/integrations/modbus/)
- [Composant Modbus d'ESPHome](https://esphome.io/components/modbus_controller.html)
- [DESS Monitor Local](https://github.com/Antoxa1081/home-assistant-dess-monitor-local)
  — intégration EyBond / SMG-II.
- [`EYBOND_LOCAL.md`](EYBOND_LOCAL.md) — procédure validée sur le dongle du site
- [`PROTOCOL.md`](PROTOCOL.md) — carte des registres et paramètres de liaison
- [`WIRING.md`](WIRING.md) — câblage RS232/RS485 et précautions
