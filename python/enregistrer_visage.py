"""Enregistre le visage d'une personne autorisée à ouvrir la porte.

Utilisation : python enregistrer_visage.py Marie
Regarder la caméra en bougeant un peu la tête (q pour arrêter).
Les images sont sauvegardées dans visages/Marie/.
"""

import sys
import time

import cv2

import config
from camera import Camera, ecrire_image
from reconnaissance import TAILLE_VISAGE, ReconnaisseurVisages


def main():
    if len(sys.argv) != 2:
        print("Utilisation : python enregistrer_visage.py <nom>")
        return
    nom = sys.argv[1]
    dossier = config.DOSSIER_VISAGES / nom
    dossier.mkdir(parents=True, exist_ok=True)
    deja = len(list(dossier.glob("*.jpg")))

    camera = Camera()
    detecteur = ReconnaisseurVisages()
    compte = 0
    derniere_photo = 0.0

    try:
        while compte < config.NB_IMAGES_ENREGISTREMENT:
            image = camera.lire()
            if image is None:
                continue
            gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            visages = detecteur.detecter(gris)

            # Une seule personne devant la caméra, une photo toutes les 0,2 s
            if len(visages) == 1 and time.time() - derniere_photo > 0.2:
                x, y, l, h = visages[0]
                visage = cv2.resize(gris[y:y + h, x:x + l], TAILLE_VISAGE)
                ecrire_image(dossier / f"{deja + compte:03d}.jpg", visage)
                compte += 1
                derniere_photo = time.time()

            for (x, y, l, h) in visages:
                cv2.rectangle(image, (x, y), (x + l, y + h), (60, 200, 60), 2)
            cv2.putText(image, f"{nom} : {compte}/{config.NB_IMAGES_ENREGISTREMENT}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 200, 60), 2)
            cv2.imshow("Enregistrement du visage", image)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.fermer()
        cv2.destroyAllWindows()

    print(f"{compte} images enregistrées dans {dossier}")


if __name__ == "__main__":
    main()
