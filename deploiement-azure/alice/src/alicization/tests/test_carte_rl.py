#!/usr/bin/env python3
# test_carte_rl.py
# Vérifie l'export du circuit RL (vraie Q-table) et l'ajout dans une carte vivante.

import unittest
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rl.environnement import DonjonSimpleEnv
from rl.entrainer import (
    q_learning,
    exporter_politique_vers_circuit,
    sauvegarder_politique,
    charger_politique,
    action_pour_position,
)
from exporter_circuit_rl import ajouter_circuit_a_la_carte


class TestCarteRL(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.env = DonjonSimpleEnv(size=3)
        cls.Q, cls.politique, cls.recompenses = q_learning(cls.env, episodes=200)

    def test_exporter_circuit_format(self):
        """Le circuit exporté a la forme attendue d'un noeud de la carte."""
        circuit = exporter_politique_vers_circuit(self.politique, taille=3)
        self.assertEqual(circuit["type"], "circuit")
        self.assertIn("nom", circuit)
        self.assertIn("mots_cles", circuit)
        self.assertTrue(circuit["etapes"])
        self.assertLessEqual(len(circuit["etapes"]), 50)

    def test_etapes_issus_de_la_q_table(self):
        """Les étapes condensent la politique apprise (pas un texte figé)."""
        circuit = exporter_politique_vers_circuit(self.politique, taille=3)
        self.assertTrue(any("action" in e for e in circuit["etapes"]))

    def test_sauvegarde_chargement_politique(self):
        """Sauvegarde puis rechargement : boucle complète."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            chemin = tmp.name
        try:
            sauvegarder_politique(self.politique, chemin)
            recup = charger_politique(chemin)
            self.assertEqual(recup, self.politique)
        finally:
            os.unlink(chemin)

    def test_action_pour_position(self):
        """Depuis la politique, on retrouve une action pour un état donné."""
        action = action_pour_position(3, [0, 0], [2, 2], self.politique)
        self.assertIn(action, [0, 1, 2, 3])

    def test_ajout_circuit_dans_carte_temporelle(self):
        """L'ajout dans une carte (fichier temporaire) respecte le schéma."""
        carte_test = {
            "releve_le": "test",
            "zones": [{"id": "connaissances", "nom": "Connaissances", "noeuds": []}]
        }
        circuit = exporter_politique_vers_circuit(self.politique, taille=3)
        circuit["id"] = "se-deplacer-vers-la-cible-rl"
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            chemin_carte = tmp.name
        try:
            with open(chemin_carte, "w", encoding="utf-8") as f:
                json.dump(carte_test, f, ensure_ascii=False)
            conte = ajouter_circuit_a_la_carte(chemin_carte, circuit)
            with open(chemin_carte, "r", encoding="utf-8") as f:
                carte = json.load(f)
            zone = carte["zones"][0]
            trouves = [n for n in zone["noeuds"] if n["id"] == "se-deplacer-vers-la-cible-rl"]
            self.assertEqual(conte, len(trouves))
            self.assertEqual(trouves[0]["type"], "circuit")
            # Idempotent : un second ajout ne duplique pas
            conte2 = ajouter_circuit_a_la_carte(chemin_carte, circuit)
            self.assertEqual(conte2, 1)
        finally:
            os.unlink(chemin_carte)


if __name__ == "__main__":
    unittest.main()