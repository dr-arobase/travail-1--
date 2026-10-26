"""Communication série avec l'Arduino (lecture dans un thread séparé)."""

import queue
import threading
import time

import serial
import serial.tools.list_ports

import config


def trouver_port():
    """Cherche un port qui ressemble à un Arduino."""
    mots_cles = ("arduino", "ch340", "usb serial", "ttyacm", "ttyusb", "wch")
    for port in serial.tools.list_ports.comports():
        texte = f"{port.device} {port.description} {port.manufacturer}".lower()
        if any(mot in texte for mot in mots_cles):
            return port.device
    return None


class LienArduino:
    """Envoie des commandes et reçoit les messages de l'Arduino.

    Si aucun Arduino n'est branché, le lien passe en mode simulation :
    les commandes sont affichées et les événements peuvent être simulés
    au clavier (utile pour tester la partie Python seule).
    """

    def __init__(self, port=config.PORT_SERIE, vitesse=config.VITESSE_SERIE):
        self.messages = queue.Queue()
        self.serie = None
        self.simulation = False
        self._actif = True

        port = port or trouver_port()
        if port is None:
            print("[serie] Aucun Arduino trouvé -> mode simulation")
            self.simulation = True
            self.port = "simulation"
            return

        self.serie = serial.Serial(port, vitesse, timeout=0.1)
        self.port = port
        time.sleep(2)  # l'Arduino redémarre à l'ouverture du port
        threading.Thread(target=self._lire_en_continu, daemon=True).start()
        print(f"[serie] Connecté à {port}")

    def _lire_en_continu(self):
        while self._actif:
            try:
                ligne = self.serie.readline().decode("utf-8", errors="ignore").strip()
            except serial.SerialException:
                self.messages.put(("INFO", "Connexion série perdue"))
                break
            if ligne:
                self.messages.put(analyser_message(ligne))

    def envoyer(self, commande):
        if self.simulation:
            print(f"[simulation] -> {commande}")
            return
        self.serie.write((commande + "\n").encode())

    def simuler(self, type_message, contenu):
        """Injecte un faux message comme s'il venait de l'Arduino."""
        self.messages.put((type_message, contenu))

    def recevoir(self):
        """Retourne la liste des messages reçus depuis le dernier appel."""
        recus = []
        while not self.messages.empty():
            recus.append(self.messages.get_nowait())
        return recus

    def fermer(self):
        self._actif = False
        if self.serie is not None:
            self.serie.close()


def analyser_message(ligne):
    """'STATUS:actif=1,etat=VEILLE' -> ('STATUS', {'actif': '1', 'etat': 'VEILLE'})
       'EVT:VISAGE_DEMANDE'        -> ('EVT', 'VISAGE_DEMANDE')"""
    type_message, _, contenu = ligne.partition(":")
    if type_message == "STATUS":
        valeurs = {}
        for paire in contenu.split(","):
            cle, _, valeur = paire.partition("=")
            valeurs[cle] = valeur
        return "STATUS", valeurs
    if type_message in ("EVT", "INFO"):
        return type_message, contenu
    return "INFO", ligne
