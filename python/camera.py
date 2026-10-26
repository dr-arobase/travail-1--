"""Accès à la caméra : caméra Raspberry Pi (picamera2) ou webcam (OpenCV)."""

import cv2
import numpy as np

import config


# cv2.imread / cv2.imwrite échouent sous Windows si le chemin contient
# des accents (ex. « Collège ») : on passe par numpy pour lire/écrire le fichier.
def ecrire_image(chemin, image):
    ok, donnees = cv2.imencode(".jpg", image)
    if ok:
        donnees.tofile(str(chemin))
    return ok


def lire_image(chemin, flags=cv2.IMREAD_COLOR):
    donnees = np.fromfile(str(chemin), dtype=np.uint8)
    return cv2.imdecode(donnees, flags) if donnees.size else None


class Camera:
    def __init__(self, source=config.SOURCE_CAMERA, resolution=config.RESOLUTION):
        self.resolution = resolution
        self.picam = None
        self.capture = None
        self.nom = ""

        if source in ("auto", "picamera") and self._ouvrir_picamera():
            return
        if source in ("auto", "opencv") and self._ouvrir_opencv():
            return
        raise RuntimeError(
            "Aucune caméra disponible : brancher une webcam USB, vérifier "
            "INDEX_WEBCAM dans config.py, ou lancer le programme sur le Raspberry Pi")

    def _ouvrir_picamera(self):
        try:
            from picamera2 import Picamera2
        except ImportError:
            return False
        try:
            self.picam = Picamera2()
            cfg = self.picam.create_preview_configuration(
                main={"size": self.resolution, "format": "RGB888"})
            self.picam.configure(cfg)
            self.picam.start()
            self.nom = "Camera Raspberry Pi"
            return True
        except Exception as erreur:
            print(f"[camera] picamera2 indisponible : {erreur}")
            self.picam = None
            return False

    def _ouvrir_opencv(self):
        self.capture = cv2.VideoCapture(config.INDEX_WEBCAM)
        if not self.capture.isOpened():
            self.capture = None
            return False
        largeur, hauteur = self.resolution
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, largeur)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, hauteur)
        self.nom = f"Webcam OpenCV #{config.INDEX_WEBCAM}"
        return True

    def lire(self):
        """Retourne une image BGR (format OpenCV) ou None."""
        if self.picam is not None:
            # Le format "RGB888" de picamera2 est déjà ordonné BGR pour OpenCV
            return self.picam.capture_array()
        ok, image = self.capture.read()
        return image if ok else None

    def fermer(self):
        if self.picam is not None:
            self.picam.stop()
        if self.capture is not None:
            self.capture.release()
