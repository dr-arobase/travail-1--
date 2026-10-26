"""Détection (Haar cascade) et reconnaissance (LBPH) de visages avec OpenCV."""

from pathlib import Path

import cv2
import numpy as np

import config
from camera import lire_image

TAILLE_VISAGE = (200, 200)
NOM_CASCADE = "haarcascade_frontalface_default.xml"


def trouver_cascade():
    """Le fichier du détecteur n'est pas au même endroit selon l'installation."""
    dossiers = [config.DOSSIER_BASE,                    # copie locale (optionnelle)
                Path("/usr/share/opencv4/haarcascades"),  # Raspberry Pi (apt)
                Path("/usr/share/opencv/haarcascades")]
    if hasattr(cv2, "data"):
        dossiers.insert(1, Path(cv2.data.haarcascades))  # pip opencv 4.x
    for dossier in dossiers:
        if (dossier / NOM_CASCADE).exists():
            return dossier / NOM_CASCADE
    raise RuntimeError(f"{NOM_CASCADE} introuvable : installer opencv-contrib-python 4.x "
                       "ou copier ce fichier dans le dossier python/")


def charger_cascade(chemin):
    """OpenCV ne peut pas ouvrir un chemin avec accents sous Windows :
    on lit le XML avec Python et on le donne à OpenCV en mémoire."""
    stockage = cv2.FileStorage(chemin.read_text(encoding="utf-8"),
                               cv2.FILE_STORAGE_READ | cv2.FILE_STORAGE_MEMORY)
    detecteur = cv2.CascadeClassifier()
    if not detecteur.read(stockage.getFirstTopLevelNode()):
        raise RuntimeError(f"Impossible de charger {chemin}")
    return detecteur


class ReconnaisseurVisages:
    def __init__(self, dossier=config.DOSSIER_VISAGES, seuil=config.SEUIL_CONFIANCE):
        if not hasattr(cv2, "face"):
            raise RuntimeError(
                "Module cv2.face absent : pip uninstall opencv-python puis "
                "pip install opencv-contrib-python")
        self.dossier = dossier
        self.seuil = seuil
        self.detecteur = charger_cascade(trouver_cascade())
        self.modele = None
        self.noms = {}
        self.entrainer()

    def detecter(self, gris):
        """Retourne les rectangles (x, y, l, h) des visages trouvés."""
        return self.detecteur.detectMultiScale(gris, scaleFactor=1.2, minNeighbors=5,
                                               minSize=(80, 80))

    def entrainer(self):
        """Apprend les visages de visages/<nom>/*.jpg. Retourne le nombre d'images."""
        self.dossier.mkdir(exist_ok=True)
        images, etiquettes = [], []
        self.noms = {}
        personnes = sorted(p for p in self.dossier.iterdir() if p.is_dir())
        for numero, dossier_personne in enumerate(personnes):
            self.noms[numero] = dossier_personne.name
            for fichier in dossier_personne.glob("*.jpg"):
                image = lire_image(fichier, cv2.IMREAD_GRAYSCALE)
                if image is not None:
                    images.append(cv2.resize(image, TAILLE_VISAGE))
                    etiquettes.append(numero)

        if not images:
            self.modele = None
            return 0
        self.modele = cv2.face.LBPHFaceRecognizer_create()
        self.modele.train(images, np.array(etiquettes))
        return len(images)

    def analyser(self, image):
        """Retourne une liste de (x, y, l, h, nom, distance) ; nom = None si inconnu."""
        gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        resultats = []
        for (x, y, l, h) in self.detecter(gris):
            nom, distance = None, None
            if self.modele is not None:
                visage = cv2.resize(gris[y:y + h, x:x + l], TAILLE_VISAGE)
                numero, distance = self.modele.predict(visage)
                if distance < self.seuil:
                    nom = self.noms[numero]
            resultats.append((x, y, l, h, nom, distance))
        return resultats
