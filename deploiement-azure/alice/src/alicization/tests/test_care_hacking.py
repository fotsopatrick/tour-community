#!/usr/bin/env python3
# test_care_hacking.py
# Le care hacking : détecter l'humeur, adapter le ton, ajouter des mots gentils.

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from outils.care_hacking import (
    detecter_humeur,
    adapter_ton,
    ajouter_petits_mots,
    envelopper,
)


class TestCareHacking(unittest.TestCase):

    def test_detecter_fatigue(self):
        self.assertEqual(detecter_humeur("Je suis vraiment fatigué aujourd'hui"), "fatigue")
        self.assertEqual(detecter_humeur("je suis épuisé, plus d'énergie"), "fatigue")

    def test_detecter_perdu(self):
        self.assertEqual(detecter_humeur("je ne comprends pas où est le fichier"), "perdu")
        self.assertEqual(detecter_humeur("je suis coincé comment faire"), "perdu")

    def test_detecter_content(self):
        self.assertEqual(detecter_humeur("Super ! Bravo, merci beaucoup"), "content")

    def test_detecter_frustre(self):
        self.assertEqual(detecter_humeur("j'en ai marre, ça ne marche jamais"), "frustre")

    def test_detecter_neutre(self):
        self.assertEqual(detecter_humeur("il fait beau ce matin"), "neutre")

    def test_adapter_ton(self):
        ton = adapter_ton("perdu")
        self.assertEqual(ton["ton"], "guidant")
        self.assertTrue(ton["introduction"])
        self.assertEqual(adapter_ton("fatigue")["ton"], "calme")
        self.assertEqual(adapter_ton("content")["ton"], "joyeux")
        self.assertEqual(adapter_ton("neutre")["ton"], "naturel")

    def test_ajouter_petits_mots(self):
        ligne = ajouter_petits_mots("Voici ta réponse", humeur="content")
        self.assertTrue(ligne.startswith("Voici ta réponse"))
        self.assertIn("Bravo", ligne)
        neutre = ajouter_petits_mots("Voici la réponse", humeur="neutre")
        self.assertEqual(neutre, "Voici la réponse")

    def test_ajouter_petits_mots_detecte_seul(self):
        ligne = ajouter_petits_mots("je me sens perdu, où sont les fichiers ?")
        self.assertGreater(len(ligne), len("je me sens perdu, où sont les fichiers ?"))

    def test_envelopper(self):
        reponse = envelopper("je n'y comprends rien, je suis perdu", "Voici les étapes.")
        self.assertIn("pas à pas", reponse)
        self.assertIn("Voici les étapes", reponse)


if __name__ == "__main__":
    unittest.main()