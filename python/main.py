"""Itération 1 - Porte magique (côté Raspberry Pi / ordinateur)

- Affiche le flux vidéo de la caméra avec les visages détectés et reconnus
- Quand l'Arduino détecte quelqu'un devant la porte (EVT:VISAGE_DEMANDE),
  reconnaît le visage pendant quelques secondes puis répond OPEN:<nom> ou DENY
- Photo de chaque visiteur (autorisé ou inconnu) dans photos/
- Tableau de bord avec l'état de l'Arduino, journal dans journal.csv

Touches :
  p : photo          v : démarrer / arrêter l'enregistrement vidéo
  o : ouvrir         c : fermer la porte
  s : système ON/OFF t : réentraîner la reconnaissance (après enregistrer_visage.py)
  d : simuler une personne devant la porte (mode simulation sans Arduino)
  q : quitter
"""

import csv
import time
import unicodedata
from datetime import datetime

import cv2
import numpy as np

import config
from camera import Camera, ecrire_image
from lien_arduino import LienArduino
from reconnaissance import ReconnaisseurVisages
from voix import parler

LARGEUR_PANNEAU = 280
VERT = (60, 200, 60)
ROUGE = (60, 60, 230)
BLANC = (240, 240, 240)
GRIS = (150, 150, 150)
VIOLET = (220, 90, 180)
JAUNE = (0, 210, 240)


def en_ascii(texte):
    """Le LCD n'affiche pas les accents : « Émilie » -> « Emilie »."""
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()


class PorteMagique:
    def __init__(self):
        config.DOSSIER_PHOTOS.mkdir(exist_ok=True)
        config.DOSSIER_VIDEOS.mkdir(exist_ok=True)

        self.camera = Camera()
        self.arduino = LienArduino()
        self.reconnaisseur = ReconnaisseurVisages()
        self.etat = {}                 # dernier STATUS reçu de l'Arduino
        self.evenements = []           # derniers événements affichés
        self.enregistreur = None       # cv2.VideoWriter pendant l'enregistrement
        self.visages = []              # résultat de la dernière analyse
        self.fin_reconnaissance = None # heure limite quand une reconnaissance est en cours
        self.compteurs = {}            # nom -> nb d'images consécutives reconnues
        self.nb_photos = 0

        self.journaliser("DEMARRAGE", f"camera={self.camera.nom}, port={self.arduino.port}, "
                                      f"personnes={list(self.reconnaisseur.noms.values())}")

    # ---------- Journal ----------
    def journaliser(self, evenement, details=""):
        horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nouveau = not config.FICHIER_JOURNAL.exists()
        with open(config.FICHIER_JOURNAL, "a", newline="", encoding="utf-8") as f:
            ecrivain = csv.writer(f)
            if nouveau:
                ecrivain.writerow(["horodatage", "evenement", "details"])
            ecrivain.writerow([horodatage, evenement, details])
        texte = f"{horodatage[11:]} {evenement}"
        if details and len(details) < 15:
            texte += f" {details}"
        self.evenements.insert(0, texte)
        del self.evenements[6:]
        print(f"[{horodatage}] {evenement} {details}")

    # ---------- Caméra ----------
    def prendre_photo(self, image, prefixe):
        nom = f"{prefixe}_{datetime.now():%Y%m%d_%H%M%S}.jpg"
        ecrire_image(config.DOSSIER_PHOTOS / nom, image)
        self.nb_photos += 1
        return nom

    def basculer_enregistrement(self, image):
        if self.enregistreur is None:
            nom = f"video_{datetime.now():%Y%m%d_%H%M%S}.avi"
            hauteur, largeur = image.shape[:2]
            self.enregistreur = cv2.VideoWriter(
                str(config.DOSSIER_VIDEOS / nom),
                cv2.VideoWriter_fourcc(*"XVID"), 20, (largeur, hauteur))
            self.journaliser("VIDEO_DEBUT", nom)
        else:
            self.enregistreur.release()
            self.enregistreur = None
            self.journaliser("VIDEO_FIN")

    # ---------- Reconnaissance faciale ----------
    def demarrer_reconnaissance(self):
        self.fin_reconnaissance = time.time() + config.DUREE_RECONNAISSANCE
        self.compteurs = {}
        self.journaliser("RECONNAISSANCE_DEBUT")

    def suivre_reconnaissance(self, image):
        """Appelée à chaque image pendant une reconnaissance."""
        noms = {nom for (*_, nom, _) in self.visages if nom is not None}
        # On ne garde que les personnes vues sur cette image (images consécutives)
        self.compteurs = {nom: self.compteurs.get(nom, 0) + 1 for nom in noms}

        for nom, compte in self.compteurs.items():
            if compte >= config.IMAGES_CONSECUTIVES:
                self.fin_reconnaissance = None
                photo = self.prendre_photo(image, f"autorise_{en_ascii(nom)}")
                self.arduino.envoyer(f"OPEN:{en_ascii(nom)[:16]}")
                self.journaliser("ACCES_AUTORISE", f"{nom} ({photo})")
                parler(config.PHRASE_BIENVENUE.format(nom=nom))
                return

        if time.time() > self.fin_reconnaissance:
            self.fin_reconnaissance = None
            photo = self.prendre_photo(image, "inconnu")
            self.arduino.envoyer("DENY")
            self.journaliser("ACCES_REFUSE", photo)
            parler(config.PHRASE_REFUS)

    # ---------- Messages de l'Arduino ----------
    def traiter_messages(self):
        for type_message, contenu in self.arduino.recevoir():
            if type_message == "STATUS":
                self.etat = contenu
            elif type_message == "EVT":
                if contenu == "VISAGE_DEMANDE":
                    self.demarrer_reconnaissance()
                elif contenu != "ACCES_REFUSE":  # déjà journalisé côté Python
                    evenement, _, details = contenu.partition(":")
                    self.journaliser(evenement, details)
            else:
                print(f"[arduino] {contenu}")

    # ---------- Clavier ----------
    def traiter_touche(self, touche, image):
        commandes = {ord("o"): "OPEN:PC", ord("c"): "CLOSE", ord("s"): "TOGGLE"}
        if touche in commandes:
            self.arduino.envoyer(commandes[touche])
            self.journaliser("COMMANDE_PC", commandes[touche])
        elif touche == ord("p"):
            self.journaliser("PHOTO_MANUELLE", self.prendre_photo(image, "manuel"))
        elif touche == ord("v"):
            self.basculer_enregistrement(image)
        elif touche == ord("t"):
            nb = self.reconnaisseur.entrainer()
            self.journaliser("ENTRAINEMENT", f"{nb} images")
        elif touche == ord("d") and self.arduino.simulation:
            self.arduino.simuler("EVT", "VISAGE_DEMANDE")
        return touche != ord("q")

    # ---------- Affichage ----------
    def dessiner(self, image):
        vue = image.copy()
        hauteur, largeur = vue.shape[:2]

        for (x, y, l, h, nom, distance) in self.visages:
            couleur = VERT if nom else ROUGE
            etiquette = en_ascii(nom) if nom else "Inconnu"
            if distance is not None:
                etiquette += f" ({distance:.0f})"
            cv2.rectangle(vue, (x, y), (x + l, y + h), couleur, 2)
            cv2.putText(vue, etiquette, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, couleur, 2)

        if self.fin_reconnaissance is not None:
            restant = max(0.0, self.fin_reconnaissance - time.time())
            cv2.rectangle(vue, (0, 0), (largeur - 1, hauteur - 1), VIOLET, 4)
            cv2.putText(vue, f"Reconnaissance... {restant:.1f}s", (10, hauteur - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, VIOLET, 2)
        if self.enregistreur is not None:
            cv2.circle(vue, (largeur - 25, 25), 10, ROUGE, -1)
            cv2.putText(vue, "REC", (largeur - 90, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, ROUGE, 2)
        cv2.putText(vue, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, BLANC, 2)

        panneau = np.full((hauteur, LARGEUR_PANNEAU, 3), 35, dtype=np.uint8)
        y = 30

        def ligne(texte, couleur=BLANC, taille=0.55, epaisseur=1):
            nonlocal y
            cv2.putText(panneau, en_ascii(texte), (12, y), cv2.FONT_HERSHEY_SIMPLEX,
                        taille, couleur, epaisseur)
            y += int(32 * taille / 0.55)

        ligne("PORTE MAGIQUE", VIOLET, 0.7, 2)
        ligne(f"Arduino : {self.arduino.port}", GRIS, 0.45)
        y += 5
        e = self.etat
        actif = e.get("actif") == "1"
        ligne(f"Systeme : {'ON' if actif else 'OFF'}" if e else "Systeme : -",
              VERT if actif else ROUGE)
        ligne(f"Etat    : {e.get('etat', '-')}")
        ligne(f"Presence: {'OUI' if e.get('presence') == '1' else 'non'}")
        ligne(f"Distance: {e.get('distance', '-')} cm")
        angle = e.get("angle", "-")
        ligne(f"Porte   : {angle} deg", VERT if angle not in ("-", "0") else BLANC)
        ligne(f"Photos  : {self.nb_photos}")
        personnes = ", ".join(self.reconnaisseur.noms.values()) or "aucune"
        ligne(f"Autorises: {personnes}"[:30], GRIS, 0.45)
        y += 5

        aide = ["p photo  v video  t entrainer", "o/c porte  s on/off  q quitter"]
        if self.arduino.simulation:
            aide.insert(0, "SIMULATION : d = visiteur")
        limite = hauteur - 20 - 18 * len(aide)
        ligne("Derniers evenements :", GRIS, 0.45)
        for texte in self.evenements:
            if y > limite:
                break
            ligne(texte[:32], BLANC, 0.42)
        for i, texte in enumerate(reversed(aide)):
            cv2.putText(panneau, texte, (12, hauteur - 12 - 18 * i),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, JAUNE, 1)

        return np.hstack((vue, panneau))

    # ---------- Boucle principale ----------
    def executer(self):
        try:
            while True:
                image = self.camera.lire()
                if image is None:
                    continue
                self.visages = self.reconnaisseur.analyser(image)
                self.traiter_messages()
                if self.fin_reconnaissance is not None:
                    self.suivre_reconnaissance(image)
                if self.enregistreur is not None:
                    self.enregistreur.write(image)

                cv2.imshow("Porte magique", self.dessiner(image))
                touche = cv2.waitKey(1) & 0xFF
                if touche != 255 and not self.traiter_touche(touche, image):
                    break
        finally:
            if self.enregistreur is not None:
                self.enregistreur.release()
            self.camera.fermer()
            self.arduino.fermer()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    PorteMagique().executer()
