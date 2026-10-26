"""Paramètres du programme Python (Raspberry Pi ou ordinateur)."""

from pathlib import Path

# Port série de l'Arduino. None = détection automatique.
# Exemples : "COM3" (Windows), "/dev/ttyACM0" ou "/dev/ttyUSB0" (Raspberry Pi)
PORT_SERIE = None
VITESSE_SERIE = 9600

# Caméra : "auto" essaie d'abord la caméra Raspberry Pi (picamera2),
# puis une webcam USB / intégrée via OpenCV.
SOURCE_CAMERA = "auto"   # "auto", "picamera" ou "opencv"
INDEX_WEBCAM = 0
RESOLUTION = (640, 480)

# Dossiers de sortie (créés automatiquement)
DOSSIER_BASE = Path(__file__).resolve().parent
DOSSIER_VISAGES = DOSSIER_BASE / "visages"     # un sous-dossier par personne autorisée
DOSSIER_PHOTOS = DOSSIER_BASE / "photos"
DOSSIER_VIDEOS = DOSSIER_BASE / "videos"
FICHIER_JOURNAL = DOSSIER_BASE / "journal.csv"

# Voix de la porte ({nom} est remplacé par le nom de la personne reconnue)
VOIX_ACTIVE = True
PHRASE_BIENVENUE = "Yokoso {nom}"
PHRASE_REFUS = "Accès refusé"

# Reconnaissance faciale (LBPH : plus la « distance » est petite, plus c'est sûr)
SEUIL_CONFIANCE = 70           # au-dessus -> visage inconnu
IMAGES_CONSECUTIVES = 3        # nb d'images où la même personne doit être reconnue
DUREE_RECONNAISSANCE = 5.0     # secondes avant de refuser l'accès
NB_IMAGES_ENREGISTREMENT = 30  # photos prises par personne avec enregistrer_visage.py
