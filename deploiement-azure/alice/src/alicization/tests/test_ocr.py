#!/usr/bin/env python3
# test_ocr.py
# Tests pour l'OCR local

import unittest
import os
import sys
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from outils.ocr import extraire_texte, extraire_texte_depuis_bytes

class TestOCR(unittest.TestCase):

    def test_extraire_texte_fichier_inexistant(self):
        """Un fichier inexistant retourne None."""
        self.assertIsNone(extraire_texte("/tmp/fichier_inexistant.png"))

    def test_extraire_texte_fichier_valide(self):
        """Avec une image simple, Tesseract extrait du texte."""
        # Créer une image simple avec ImageMagick (si disponible) ou un fichier factice
        # On va utiliser un fichier texte converti en image via convert (si présent)
        try:
            subprocess.run(["convert", "-size", "200x50", "xc:white", "-font", "Arial", "-pointsize", "24", "-fill", "black", "-draw", "text 10,30 'Bonjour'", "/tmp/test_ocr.png"], check=True, capture_output=True)
        except:
            self.skipTest("ImageMagick non disponible pour générer l'image de test")
        texte = extraire_texte("/tmp/test_ocr.png")
        self.assertIsNotNone(texte)
        self.assertIn("Bonjour", texte)
        os.unlink("/tmp/test_ocr.png")

    def test_extraire_texte_depuis_bytes(self):
        """Les bytes d'une image donnent aussi le texte."""
        try:
            subprocess.run(["convert", "-size", "200x50", "xc:white", "-font", "Arial", "-pointsize", "24", "-fill", "black", "-draw", "text 10,30 'Bonjour'", "/tmp/test_ocr_bytes.png"], check=True, capture_output=True)
        except:
            self.skipTest("ImageMagick non disponible pour générer l'image de test")
        with open("/tmp/test_ocr_bytes.png", "rb") as f:
            contenu = f.read()
        texte = extraire_texte_depuis_bytes(contenu)
        self.assertIsNotNone(texte)
        self.assertIn("Bonjour", texte)
        os.unlink("/tmp/test_ocr_bytes.png")

if __name__ == "__main__":
    unittest.main()