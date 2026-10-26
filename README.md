# Itération 1 – Porte magique ✨

Une porte qui s'ouvre toute seule quand la caméra reconnaît un visage autorisé.
Quand quelqu'un s'approche, la porte se réveille, analyse le visage, puis s'ouvre lentement
avec une mélodie et un arc-en-ciel lumineux… ou refuse l'accès.

```
arduino/porte_magique/porte_magique.ino   Code Arduino
python/main.py                             Programme principal (caméra + reconnaissance + tableau de bord)
python/enregistrer_visage.py               Enregistre le visage d'une personne autorisée
python/reconnaissance.py                   Détection (Haar) et reconnaissance (LBPH) de visages
python/lien_arduino.py                     Communication série avec l'Arduino
python/camera.py                           Caméra Raspberry Pi (picamera2) ou webcam (OpenCV)
python/config.py                           Paramètres (port série, caméra, seuils)
```

## Capteurs et actionneurs

| # | Composant | Rôle | Broche Arduino |
|---|-----------|------|----------------|
| 1 | Bouton poussoir | Active / désactive la porte | D2 (INPUT_PULLUP, l'autre patte au GND) |
| 2 | Capteur PIR | Détecte une présence → la porte se réveille | OUT D3 |
| 3 | Capteur ultrason HC-SR04 | Lance la reconnaissance à < 40 cm ; empêche la porte de se fermer si quelqu'un est à < 15 cm | TRIG D4, ECHO D5 |
| 4 | Servomoteur SG90 | Ouvre la porte lentement (0° → 90°) | Signal D9 |
| 5 | LED RGB | Violet = veille, bleu = présence, bleu/cyan = analyse, arc-en-ciel = ouverte, rouge = refus | R D10, V D11, B D12 (+ 220 Ω chacune) |
| 6 | Buzzer (passif) | Mélodie magique à l'ouverture, son grave au refus | D8 |
| 7 | Afficheur LCD 16x2 I2C | « Approchez-vous », « Bienvenue Marie », « Acces refuse » | SDA A4, SCL A5 |
| 8 | LED d'état | Allumée quand le système est ON | D13 (+ 220 Ω) |
| 9 | Caméra Raspberry Pi | Reconnaissance faciale, photos des visiteurs, flux vidéo | Port CSI du Pi |

Tous les GND sont communs. LED RGB à cathode commune par défaut ; si c'est une anode commune
(patte longue au 5V), mettre `RGB_ANODE_COMMUNE = true` dans le code Arduino.

## Fonctionnement

1. **Bouton** : allume / éteint la porte (mélodie montante / descendante, LED d'état).
2. **Veille** : LED RGB qui clignote en violet, LCD « Zzz... ».
3. **Présence** (PIR) : LED bleue, LCD « Bonjour ! Approchez-vous ».
4. **Approche** (ultrason < 40 cm) : l'Arduino envoie `EVT:VISAGE_DEMANDE`, LCD « Regardez la camera ».
   Le Python analyse le visage pendant 5 s maximum.
5. **Visage reconnu** (3 images de suite) : photo `photos/autorise_<nom>_...jpg`, le Python envoie
   `OPEN:<nom>` → la porte s'ouvre lentement, mélodie magique, arc-en-ciel, LCD « Bienvenue <nom> »,
   et la porte dit « Yokoso <nom> » (synthèse vocale, phrases modifiables dans `config.py`).
   Elle se referme après 5 s, sauf si quelqu'un est encore dans le passage.
6. **Visage inconnu** : photo `photos/inconnu_...jpg`, `DENY` → LED rouge clignotante, son grave,
   LCD « Acces refuse », la porte dit « Accès refusé ». Il faut reculer puis revenir pour réessayer.
7. Si le PC ne répond pas en 8 s, l'accès est refusé (sécurité).

### Touches du programme Python

| Touche | Action |
|--------|--------|
| `p` | Prendre une photo |
| `v` | Démarrer / arrêter l'enregistrement vidéo (`videos/`) |
| `o` / `c` | Ouvrir / fermer la porte à distance |
| `s` | Système ON/OFF (comme le bouton) |
| `t` | Réentraîner la reconnaissance (après avoir ajouté un visage) |
| `d` | Simuler un visiteur (seulement sans Arduino) |
| `q` | Quitter |

### Protocole série (9600 bauds, une commande par ligne)

- Arduino → PC : `EVT:PRESENCE_DETECTEE`, `EVT:VISAGE_DEMANDE`, `EVT:PORTE_OUVERTE:<nom>`,
  `EVT:PORTE_FERMEE`, `EVT:ACCES_REFUSE`, `EVT:VEILLE`, `EVT:SYSTEME_ON/OFF`,
  `STATUS:actif=1,etat=PRESENCE,presence=1,distance=35,angle=0`
- PC → Arduino : `OPEN:<nom>`, `OPEN`, `DENY`, `CLOSE`, `TOGGLE`, `STATUS`

## Installation

**Arduino** : dans l'IDE Arduino, installer la bibliothèque *LiquidCrystal I2C* (Frank de Brabander),
ouvrir `arduino/porte_magique/porte_magique.ino` et téléverser. Si le LCD reste vide, remplacer
l'adresse `0x27` par `0x3F` et ajuster le contraste (potentiomètre derrière l'écran).

**Raspberry Pi** :
```bash
sudo apt install python3-picamera2 python3-opencv python3-serial espeak-ng
cd python
```
(`espeak-ng` remplace la voix de Windows pour faire parler la porte sur le Pi.)

**Ordinateur (Windows)** : la webcam remplace la caméra du Pi.
```bash
cd python
pip uninstall opencv-python        # seulement s'il est déjà installé (conflit)
pip install -r requirements.txt
```

**Enregistrer les visages autorisés** (une fois par personne, bien éclairé) :
```bash
python enregistrer_visage.py Marie
python enregistrer_visage.py Karim
```

**Lancer la porte** :
```bash
python main.py
```

Le port de l'Arduino est détecté automatiquement. Sinon, le mettre dans `config.py`
(`PORT_SERIE = "COM3"` ou `"/dev/ttyACM0"`). **Fermer le moniteur série de l'IDE Arduino**
avant de lancer le Python, sinon le port est occupé.

**Réglage de la reconnaissance** : le nombre entre parenthèses à côté du nom est la « distance »
LBPH (plus petit = plus sûr). Si une personne enregistrée est refusée, augmenter
`SEUIL_CONFIANCE` dans `config.py` (ex. 80) ; si un inconnu est accepté, le baisser (ex. 60).

## Scénario pour la vidéo de démonstration

1. Montrer le montage et nommer chaque composant.
2. Montrer `enregistrer_visage.py` (enregistrement d'un membre de l'équipe).
3. Lancer `main.py` : flux vidéo, visage encadré en vert avec le nom.
4. Appuyer sur le bouton → mélodie, LED d'état allumée, tableau de bord « Systeme : ON ».
5. Passer devant le PIR → LED bleue, LCD « Approchez-vous ».
6. S'approcher de l'ultrason → analyse (LED bleu/cyan) → porte qui s'ouvre, mélodie, arc-en-ciel,
   « Bienvenue <nom> » sur le LCD, puis fermeture automatique.
7. Mettre la main dans le passage pendant que la porte est ouverte → elle ne se ferme pas.
8. Une personne non enregistrée (ou une photo cachée) → « Acces refuse », LED rouge, son grave.
9. Touches `o` / `c`, `p`, `v` ; montrer le dossier `photos/` et `journal.csv`.

## Remise

- [ ] `arduino/porte_magique/porte_magique.ino`
- [ ] Dossier `python/` (sans le dossier `visages/` si vous ne voulez pas partager vos photos)
- [ ] Photos du prototype électronique
- [ ] Vidéo de démonstration
- [ ] Captures d'écran : tableau de bord avec visage reconnu / inconnu, photos `autorise_` et
      `inconnu_`, LCD, moniteur série
