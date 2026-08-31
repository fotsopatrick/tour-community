#!/usr/bin/env python3
# test_routeur_ocr.py
# Vérifie que routeur.py appelle bien extraire_texte() et retourne le texte lu.

import unittest
import sys
import os
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from routeur import Routeur

IMAGE = "/tmp/test_routeur_ocr.png"


class TestRouteurOCR(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            subprocess.run(
                ["convert", "-size", "200x50", "xc:white", "-font", "Arial",
                 "-pointsize", "24", "-fill", "black", "-draw", "text 10,30 'Bonjour'",
                 IMAGE],
                check=True, capture_output=True)
        except Exception:
            raise unittest.SkipTest("ImageMagick indisponible")
        cls.routeur = Routeur(
            chemin_carte="/home/orel/carte-vivante/cartes.json",
            chemin_db="/home/orel/alicization/state/alicization.db"
        )

    def test_routeur_ocr_lecture_image(self):
        """« lis cette image ... » → Alice revient avec le texte extrait."""
        resultat = self.routeur.router(f"lis cette image {IMAGE}")
        self.assertEqual(resultat["source"], "outil_ocr")
        self.assertIn("Bonjour", resultat["message"])

    def test_routeur_ocr_image_absente(self):
        """Une image inexistante → Alice ne ment pas : elle dit qu'elle n'a rien lu."""
        resultat = self.routeur.router("/tmp/fichier_qui_nexiste_pas.png, lis l'image")
        self.assertEqual(resultat["source"], "outil_ocr")
        self.assertIn("rien lu", resultat["message"])

    def test_routeur_ocr_chemin_relatif(self):
        """Un chemin relatif (sans /) est résolu sous /home/orel."""
        relatif = "test_routeur_ocr_relatif.png"
        chemin_rel = os.path.join("/home/orel", relatif)
        subprocess.run(["cp", IMAGE, chemin_rel], check=True)
        try:
            resultat = self.routeur.router(f"ocr {relatif}")
            self.assertEqual(resultat["source"], "outil_ocr")
            self.assertIn("Bonjour", resultat["message"])
        finally:
            os.unlink(chemin_rel)


if __name__ == "__main__":
    unittest.main()