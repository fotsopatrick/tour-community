#!/usr/bin/env python3
# /home/orel/alicization/outils/ocr.py
# OCR local avec Tesseract — pas d'API externe

import subprocess
import os
import tempfile

# Tesseract installé sans sudo dans ~/alice-local (avec leps français).
BIN_TESSERACT = "/home/alice/alice-local/usr/bin/tesseract"
PREFIX_LOCAL = "/home/alice/alice-local/usr/lib/x86_64-linux-gnu"
TESSDATA = "/home/alice/alice-local/usr/share/tesseract-ocr/5/tessdata"

_ENV = dict(os.environ)
if os.path.exists(BIN_TESSERACT):
    _ENV["PATH"] = "/home/alice/alice-local/usr/bin:" + _ENV.get("PATH", "")
    _ENV["LD_LIBRARY_PATH"] = PREFIX_LOCAL + ":" + _ENV.get("LD_LIBRARY_PATH", "")
    _ENV["TESSDATA_PREFIX"] = TESSDATA


def extraire_texte(chemin_image, lang="fra"):
    """
    Extrait le texte d'une image via Tesseract.
    Retourne le texte brut, ou None en cas d'erreur.
    """
    if not os.path.exists(chemin_image):
        return None

    if os.path.exists(BIN_TESSERACT):
        binaire = BIN_TESSERACT
    elif subprocess.run(["which", "tesseract"], capture_output=True).returncode == 0:
        binaire = "tesseract"
    else:
        return None

    try:
        tentatives = [
            [binaire, chemin_image, "stdout", "-l", lang],
            [binaire, chemin_image, "stdout", "-l", lang, "--psm", "6"],
            [binaire, chemin_image, "stdout", "-l", lang, "--psm", "7"],
            [binaire, chemin_image, "stdout"],
        ]
        for args in tentatives:
            resultat = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=20,
                env=_ENV
            )
            if resultat.returncode == 0 and resultat.stdout.strip():
                return resultat.stdout.strip()
        return None
    except Exception:
        return None


def extraire_texte_depuis_bytes(contenu_image):
    """
    Extrait le texte depuis des bytes (image en mémoire).
    """
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(contenu_image)
        tmp_path = tmp.name
    try:
        return extraire_texte(tmp_path)
    finally:
        os.unlink(tmp_path)