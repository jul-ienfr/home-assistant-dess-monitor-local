# Câblage Anenji — ESP32 ↔ Onduleur

Ce document couvre les deux façons de relier un ESP32 à un onduleur Anenji
SMG-II : **RS485** (MAX485/SP3485) et **RS232** (MAX3232). Le bon choix dépend
du port disponible sur l'onduleur.

> **Sécurité** : couper l'onduleur et débrancher la batterie avant de câbler.
> Vérifier les tensions au multimètre avant de relier l'ESP32. Ne jamais injecter
> 12 V ou 5 V sur une broche GPIO de l'ESP32.

## 1. Choisir le bon montage

| Port de l'onduleur | Transceiver | Quand l'utiliser |
|--------------------|-------------|------------------|
| Bornes A+/B- | MAX485 / SP3485 | Modèles avec port RS485 explicite |
| RJ45 (RS232) | MAX3232 | SMG-II avec port COM RJ45 (protocole V1.0.1) |
| USB-A (variante 6 kW) | MAX3232 | Les lignes D+/D- portent du RS232, pas de l'USB |
| Port série interne | MAX3232 ou niveau TTL | Remplacement du module WiFi d'origine |

Le même firmware `anenji.yaml` fonctionne dans les deux cas : la broche DE/RE
(GPIO4) est simplement non câblée en RS232.

> Pour piloter l'onduleur **sans ESP32** (dongle Wi-Fi d'origine, passerelle
> série → Ethernet, adaptateur USB sur le serveur Home Assistant ou cloud),
> voir [`REMOTE_ACCESS.md`](REMOTE_ACCESS.md) et
> [`EYBOND_LOCAL.md`](EYBOND_LOCAL.md).

## 2. Vue d'ensemble

```text
┌─────────────┐    UART TTL    ┌──────────────┐   RS232/RS485   ┌──────────────┐
│   ESP32     │◄──────────────►│  MAX3232     │◄───────────────►│  Onduleur    │
│  (esp32dev) │  TX/RX/GND     │  ou MAX485   │   A/B ou TX/RX  │  SMG-II      │
└──────┬──────┘                └──────────────┘                 └──────────────┘
       │
       │ 5 V / 1 A
       └──────── Alimentation USB ou buck 12 V → 5 V
```

## 3. Montage RS485 (MAX485 / SP3485)

### 3.1 Broches

| ESP32 | MAX485 | Direction | Notes |
|-------|--------|-----------|-------|
| GPIO17 | DI (pin 4) | ESP32 → transceiver | TX UART |
| GPIO16 | RO (pin 1) | transceiver → ESP32 | RX UART |
| GPIO4 | DE (pin 3) + /RE (pin 2) | ESP32 → transceiver | Relier DE et /RE ensemble |
| 3,3 V | VCC (pin 8) | Alimentation | **Module 3,3 V obligatoire** |
| GND | GND (pin 5) | Masse commune | Obligatoire |

```text
        ┌─────────────────┐
        │    MAX485       │
        │                 │
  RO  ──┤1            8├── VCC 3,3 V
  /RE ──┤2            7├── B- ────── vers onduleur
   DE ──┤3            6├── A+ ────── vers onduleur
  DI  ──┤4            5├── GND ───── GND commun
        └─────────────────┘
```

### 3.2 Niveau logique

Un MAX485 alimenté en **5 V** délivre un RO à 5 V. L'ESP32 est en 3,3 V :
utiliser un **SP3485** (3,3 V) ou un adaptateur de niveau sur RO. Le DI tolère
généralement 3,3 V, mais le RO ne doit jamais dépasser 3,3 V.

### 3.3 DE/RE

`flow_control_pin: GPIO4` dans `anenji.yaml` bascule automatiquement le
transceiver entre émission et réception. Sans cette broche, un MAX485 reste en
réception et les requêtes Modbus ne partent jamais sur le bus.

### 3.4 Terminaison et polarisation

- Bus court (< 2 m) : terminaison souvent inutile.
- Bus long ou bruité : résistance **120 Ω** entre A et B aux deux extrémités.
- Éviter les étoiles ; privilégier une topologie en daisy-chain.
- Relier les masses (GND) des transceivers et de l'onduleur.

## 4. Montage RS232 (MAX3232)

### 4.1 Broches

| ESP32 | MAX3232 | Direction | Notes |
|-------|---------|-----------|-------|
| GPIO17 | T1IN | ESP32 → transceiver | TX UART |
| GPIO16 | R1OUT | transceiver → ESP32 | RX UART |
| 3,3 V | VCC | Alimentation | Module 3,3 V |
| GND | GND | Masse | Obligatoire |
| — | T1OUT | transceiver → onduleur | RX onduleur |
| — | R1IN | onduleur → transceiver | TX onduleur |

GPIO4 n'est pas utilisé en RS232. Laisser la broche non connectée.

### 4.2 RJ45 (SMG-II)

Le connecteur RJ45 du SMG-II n'est **pas** un Ethernet. Le brochage documenté par
syssi :

| Broche RJ45 | Signal | Couleur T-568B |
|------------:|--------|----------------|
| 1 | TX onduleur | Blanc-orange |
| 2 | RX onduleur | Orange |
| 4 | VCC 12 V | Bleu |
| 8 | GND | Marron |

> La broche 4 peut fournir **12 V**. Ne pas la relier directement à l'ESP32.
> Utiliser un buck 12 V → 5 V ou une alimentation séparée.

> **Modèle ANJ-4000W / ANJ-4200W-24V-WIFI** : Anenji ne publie pas de manuel
> détaillé ni de brochage pour ce modèle. Les photos produit confirment un
> onduleur 24 V de la famille SMG-II, mais ne montrent pas les ports. Le
> brochage ci-dessus est celui du SMG-II générique : **le vérifier au multimètre
> avant de brancher**. Si l'appareil possède un port BMS RJ45 séparé, ne pas le
> confondre avec le port de communication ; ce firmware utilise uniquement le
> port Modbus de l'onduleur.

### 4.3 Variante USB-A (6 kW)

Certains SMG-II 6 kW exposent un port USB-A qui transporte du **RS232** sur les
lignes de données, avec VBUS et GND standard. Utiliser un MAX3232, pas un
adaptateur USB.

## 5. Alimentation de l'ESP32

| Option | Usage | Remarque |
|--------|-------|----------|
| USB 5 V / 1 A | Debug et test | Le plus simple |
| Buck 12 V → 5 V | Installation van | Vérifier 500 mA stables |
| Alimentation interne onduleur | Intégration | Vérifier la tension et l'isolation |

Ne pas alimenter l'ESP32 par la broche 3,3 V d'un module RS485 : le régulateur
de la carte n'est pas prévu pour cela.

## 6. Broches utilisées

| Broche ESP32 | Fonction | Notes |
|-------------|----------|-------|
| GPIO17 | UART TX | Vers DI (RS485) ou T1IN (RS232) |
| GPIO16 | UART RX | Depuis RO (RS485) ou R1OUT (RS232) |
| GPIO4 | DE/RE | RS485 uniquement |
| GPIO2 | LED de statut | LED onboard, optionnelle |
| GND | Masse | Obligatoire |
| 5 V / VIN | Alimentation | 5 V stable |

## 7. Paramètres du bus

| Paramètre | Valeur |
|-----------|--------|
| Débit | 9600 bauds |
| Données | 8 bits |
| Parité | aucune |
| Stop | 1 bit |
| Adresse | 0x01 |
| Protocole | Modbus RTU |
| Délai | 200 ms (`send_wait_time`) |

## 8. Vérification avant mise sous tension

1. Contrôler la continuité GND entre ESP32, transceiver et onduleur.
2. Vérifier qu'aucun fil 5 V/12 V ne touche un GPIO.
3. Vérifier A/B (ou TX/RX) : un inverseur A/B est la cause n°1 d'absence de
   données.
4. Alimenter l'ESP32 seul et vérifier qu'il démarre.
5. Brancher le bus, puis lancer `esphome logs anenji.yaml`.

## 9. Dépannage

| Symptôme | Cause probable | Solution |
|----------|----------------|----------|
| Aucune donnée | A/B inversés | Inverser A et B |
| Aucune donnée | GND non connecté | Relier les masses |
| Aucune donnée | DE/RE non câblé (RS485) | Relier DE + /RE à GPIO4 |
| Aucune donnée | MAUVAIS PORT (RS232 vs RS485) | Vérifier le port de l'onduleur |
| Données erratiques | Pas de terminaison | Ajouter 120 Ω |
| Timeout Modbus | Mauvaise adresse | Vérifier 0x01 sur l'écran |
| Timeout Modbus | Mauvais débit | Vérifier 9600 8N1 |
| ESP32 redémarre | Alimentation insuffisante | 5 V / 1 A stable |
| RO chauffe / ESP32 instable | MAX485 en 5 V | Utiliser SP3485 ou level shifter |

## 10. Références

- [syssi/esphome-smg-ii — schémas et RJ45](https://github.com/syssi/esphome-smg-ii)
- [jul-ienfr/esphome-anenji-4.2kw-wifi — photos historiques du module d'origine](https://github.com/jul-ienfr/esphome-anenji-4.2kw-wifi)
  (le dépôt n'est pas une source de vérité pour les registres)
- [Documentation ESPHome UART](https://esphome.io/components/uart.html)
