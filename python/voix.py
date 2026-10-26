"""La porte parle : synthèse vocale de Windows (System.Speech) ou espeak sur Raspberry Pi."""

import platform
import shutil
import subprocess

import config


def parler(texte):
    """Dit la phrase en arrière-plan, sans figer le flux vidéo."""
    if not config.VOIX_ACTIVE:
        return
    print(f"[voix] {texte}")
    try:
        if platform.system() == "Windows":
            texte_ps = texte.replace("'", "''")  # une apostrophe se double en PowerShell
            commande = ("Add-Type -AssemblyName System.Speech; "
                        "(New-Object System.Speech.Synthesis.SpeechSynthesizer)"
                        f".Speak('{texte_ps}');")
            subprocess.Popen(["powershell", "-NoProfile", "-Command", commande],
                             creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            moteur = shutil.which("espeak-ng") or shutil.which("espeak")
            if moteur:
                subprocess.Popen([moteur, "-v", "fr", texte])
            else:
                print("[voix] installer espeak-ng : sudo apt install espeak-ng")
    except OSError as erreur:
        print(f"[voix] impossible de parler : {erreur}")
