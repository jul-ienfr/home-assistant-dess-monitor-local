# Outils de diagnostic

## `eybond_probe.py`

Lecture seule d'un bloc de registres Modbus RTU à travers un dongle Wi-Fi
Eybond / SmartESS. Le script annonce l'IP de la machine locale au dongle, attend
sa connexion TCP inverse, puis envoie une lecture FC3.

Il **ne fait aucune écriture**. Il prend temporairement le dongle à la place du
cloud et de l'intégration Home Assistant ; arrêter le script rend le dongle au
cloud après quelques secondes.

### Utilisation

Depuis la racine du dépôt :

```bash
python tools/eybond_probe.py \
  --announce-ip 192.168.68.56 \
  --broadcast 192.168.71.255 \
  --register 201 --count 31
```

- `--announce-ip` : IP LAN de la machine qui exécute le script (celle que le
  dongle doit joindre). Par défaut, le script la détecte automatiquement.
- `--broadcast` : broadcast du sous-réseau, par exemple `192.168.71.255` pour
  un LAN `192.168.68.0/22`. `255.255.255.255` est ajouté automatiquement.
- `--register` / `--count` : bloc à lire. Exemples : `201`/`31` (mesures),
  `300`/`38` (configuration), `100`/`16` (défauts).
- `--devaddr` : adresse Modbus de l'onduleur (défaut `1`).
- `--timeout` : délai total (défaut `45` s).
- `--out` : fichier de log, utile avec `pythonw.exe` quand le pare-feu Windows
  bloque `python.exe`.

Avant de lancer le script, arrêter l'intégration DESS Monitor Local dans Home
Assistant : un seul processus peut écouter sur le port 8899.

### Exemple de sortie

```text
12:47:17 LISTENING on 0.0.0.0:8899
12:47:17 UDP announce -> 192.168.71.255:58899 set>server=192.168.68.56:8899;
12:47:17 CONNECTED from ('192.168.68.57', 50880)
12:47:17 TX heartbeat 00010000000a01011a0b0a0c2f11003c
12:47:17 RX tid=1 devcode=0x0102 devaddr=255 fc=1 payload=453530303030323231313632393236303531
12:47:17 PN E50000221162926051 (18 caracteres)
12:47:17 TX read 201 x31 inner=010300c9001fd43c frame=00020994000a0104010300c9001fd43c
12:47:17 REGS 201 [2, 2335, 5009, ...]
```

### Pare-feu Windows

Le profil réseau « Public » bloque souvent les connexions entrantes vers
`python.exe`. Deux options :

1. autoriser `python.exe` (ou le port TCP 8899) pour le réseau privé dans le
   pare-feu Windows ;
2. lancer avec `pythonw.exe`, qui dispose souvent déjà d'une règle
   d'autorisation, et écrire la sortie dans un fichier :

```bat
pythonw.exe -X utf8 tools\eybond_probe.py --out probe.log
```

### Limites

- Un seul dongle / une seule session à la fois.
- Le script ne remplace pas l'intégration Home Assistant : il sert à vérifier
  la connectivité, le PN et les registres avant installation ou en dépannage.
- Le dongle retourne au cloud quand le script se termine ; aucune commande de
  restauration n'est nécessaire.
