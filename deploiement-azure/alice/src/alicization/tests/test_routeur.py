# ============================================================
# TESTS DU ROUTEUR (TDD : écrits AVANT le code)
# ============================================================

import unittest
import tempfile
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from routeur import Routeur

class TestRouteur(unittest.TestCase):

    def setUp(self):
        """On crée une carte de test et une mémoire temporaire."""
        # Créer une fausse carte vivante
        self.carte_test = {
            "zones": [
                {
                    "id": "test",
                    "nom": "Zone de test",
                    "noeuds": [
                        {
                            "id": "circuit-712",
                            "nom": "Trouver 712",
                            "type": "circuit",
                            "mots_cles": ["712", "procédure", "17"]
                        },
                        {
                            "id": "outil-op_k7",
                            "nom": "op_k7",
                            "type": "outil",
                            "mots_cles": ["op_k7", "multiplier"]
                        }
                    ]
                }
            ]
        }

        # Créer les fichiers temporaires
        self.dossier_temp = tempfile.TemporaryDirectory()
        self.chemin_carte = Path(self.dossier_temp.name) / "cartes.json"
        with open(self.chemin_carte, 'w') as f:
            json.dump(self.carte_test, f)

        self.chemin_db = Path(self.dossier_temp.name) / "memoire.db"
        self.routeur = Routeur(chemin_carte=str(self.chemin_carte), chemin_db=str(self.chemin_db))

    def tearDown(self):
        self.dossier_temp.cleanup()

    def test_routeur_trouve_circuit_dans_carte(self):
        """Le routeur doit trouver un circuit dans la carte."""
        resultat = self.routeur.router("712")
        self.assertEqual(resultat["decision"], "circuit")
        self.assertEqual(resultat["source"], "carte")

    def test_routeur_trouve_outil_dans_carte(self):
        """Le routeur doit trouver un outil dans la carte."""
        resultat = self.routeur.router("op_k7")
        self.assertEqual(resultat["decision"], "circuit")
        self.assertEqual(resultat["source"], "carte")

    def test_routeur_ne_trouve_pas_dans_carte(self):
        """Le routeur ne trouve pas une chose inconnue dans la carte."""
        resultat = self.routeur.router("chose totalement inconnue")
        self.assertEqual(resultat["decision"], "modele")
        self.assertEqual(resultat["source"], "nouveau")

    def test_routeur_trouve_dans_memoire_apres_ajout(self):
        """Le routeur doit trouver une procédure après l'avoir ajoutée à la mémoire."""
        self.routeur.memoire.ajouter("ma_procedure", ["op1", "op2"])
        resultat = self.routeur.router("ma_procedure")
        self.assertEqual(resultat["decision"], "circuit")
        self.assertEqual(resultat["source"], "memoire")

    def test_routeur_stats(self):
        """Les statistiques doivent être cohérentes."""
        stats = self.routeur.carte_stats()
        self.assertEqual(stats["total_zones"], 1)
        self.assertEqual(stats["total_noeuds"], 2)
        self.assertIn("circuit", stats["types"])
        self.assertIn("outil", stats["types"])