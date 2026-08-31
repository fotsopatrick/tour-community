#!/usr/bin/env python3
# test_registre.py
# Vérifie que le dictionnaire familier/courant/soutenu est chargé et utilisable.

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from outils.registre_langue import (
    REGISTRES,
    detecter_registre,
    traduire_vers_courant,
    synonyme_soutenu,
    traduire_vers_soutenu,
)

class TestRegistreLangue(unittest.TestCase):

    def test_registres_presents(self):
        self.assertIn("familier", REGISTRES)
        self.assertIn("courant", REGISTRES)
        self.assertIn("soutenu", REGISTRES)

    def test_detecter_familier(self):
        self.assertEqual(detecter_registre("J'ai bouffé une pizza"), "familier")
        self.assertEqual(detecter_registre("Je vais pioncer"), "familier")

    def test_detecter_courant(self):
        self.assertEqual(detecter_registre("Je mange une pizza"), "courant")
        self.assertEqual(detecter_registre("Je dors"), "courant")

    def test_detecter_soutenu(self):
        self.assertEqual(detecter_registre("Je me sustente"), "soutenu")
        self.assertEqual(detecter_registre("Elle fait un somme"), "soutenu")

    def test_detecter_defaut_courant(self):
        self.assertEqual(detecter_registre("Le ciel est bleu"), "courant")

    def test_traduire_vers_courant(self):
        self.assertEqual(traduire_vers_courant("bouffer"), "manger")
        self.assertEqual(traduire_vers_courant("pioncer"), "dormir")
        self.assertEqual(traduire_vers_courant("mot_totalement_inconnu"), "mot_totalement_inconnu")

    def test_synonyme_soutenu(self):
        self.assertIn(synonyme_soutenu("manger"), ["se sustenter", "se restaurer"])
        self.assertEqual(synonyme_soutenu("dormir"), "faire un somme")

    def test_traduire_vers_soutenu(self):
        self.assertEqual(traduire_vers_soutenu("bouffer"), "se sustenter")
        self.assertEqual(traduire_vers_soutenu("pioncer"), "faire un somme")

    def test_familier_contient_registre_courant(self):
        """Le registre familier garde un lien vers sa version courante."""
        self.assertEqual(REGISTRES["familier"]["manger"][0], "bouffer")

if __name__ == "__main__":
    unittest.main()