# -*- coding: utf-8 -*-
"""
TEST DU ROUTEUR AVEC CARTE
Vérifie que le routeur trouve les éléments dans la vraie carte vivante.
"""

import unittest
import tempfile
import json
import sys
import os
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRouteurAvecCarte(unittest.TestCase):

    def setUp(self):
        """On crée une carte de test avec tous les types."""
        self.carte_test = {
            "zones": [
                {
                    "id": "connaissances",
                    "nom": "Ce qu'on sait",
                    "noeuds": [
                        {
                            "id": "circuit-1",
                            "nom": "Trouver 712",
                            "type": "circuit",
                            "mots_cles": ["712", "procédure", "17"],
                            "etapes": ["op_q9", "op_k7", "op_m2"]
                        },
                        {
                            "id": "outil-op_k7",
                            "nom": "op_k7",
                            "type": "outil",
                            "description": "x * 3 + 7"
                        },
                        {
                            "id": "processus-test",
                            "nom": "Tester une procédure",
                            "type": "processus",
                            "mots_cles": ["tester", "vérifier"]
                        },
                        {
                            "id": "acteur-clark",
                            "nom": "Clark",
                            "type": "agent",
                            "detail": "le developpeur — moteur: deepseek-agent"
                        },
                        {
                            "id": "demande-42",
                            "nom": "Trouver la procédure",
                            "type": "demande",
                            "mots_cles": ["procédure", "trouver"],
                            "detail": "mission active"
                        }
                    ]
                }
            ]
        }

        # Créer les fichiers temporaires
        self.dossier_temp = tempfile.TemporaryDirectory()
        self.chemin_carte = Path(self.dossier_temp.name) / "cartes.json"
        with open(self.chemin_carte, 'w', encoding='utf-8') as f:
            json.dump(self.carte_test, f)

        self.chemin_db = Path(self.dossier_temp.name) / "memoire.db"

        from routeur_avec_carte import Routeur
        self.routeur = Routeur(chemin_db=str(self.chemin_db), chemin_carte=str(self.chemin_carte))

    def tearDown(self):
        self.dossier_temp.cleanup()

    def test_circuit_trouve_dans_carte(self):
        """Le routeur doit trouver un circuit dans la carte."""
        resultat = self.routeur.router("Je cherche la procédure pour 712")
        self.assertEqual(resultat["decision"], "circuit")
        self.assertEqual(resultat["source"], "carte")
        self.assertEqual(resultat["info"]["type"], "circuit")

    def test_outil_trouve_dans_carte(self):
        """Le routeur doit trouver un outil dans la carte."""
        resultat = self.routeur.router("op_k7")
        self.assertEqual(resultat["decision"], "circuit")
        self.assertEqual(resultat["source"], "carte")
        self.assertEqual(resultat["info"]["type"], "outil")

    def test_processus_trouve_dans_carte(self):
        """Le routeur doit trouver un processus dans la carte."""
        resultat = self.routeur.router("Vérifier le test")
        self.assertEqual(resultat["decision"], "circuit")
        self.assertEqual(resultat["source"], "carte")
        self.assertEqual(resultat["info"]["type"], "processus")

    def test_acteur_trouve_dans_carte(self):
        """Le routeur doit trouver un acteur dans la carte."""
        resultat = self.routeur.router("Clark")
        self.assertEqual(resultat["decision"], "circuit")
        self.assertEqual(resultat["source"], "carte")
        self.assertEqual(resultat["info"]["type"], "acteur")

    def test_demande_trouvee_dans_carte(self):
        """Le routeur doit trouver une demande dans la carte."""
        # Utiliser "mission active" qui ne matche que la demande (pas le circuit)
        resultat = self.routeur.router("mission active")
        self.assertEqual(resultat["decision"], "circuit")
        self.assertEqual(resultat["source"], "carte")
        self.assertEqual(resultat["info"]["type"], "demande")

    def test_rien_trouve_alors_modele(self):
        """Si rien n'est trouvé, le routeur appelle le modèle."""
        resultat = self.routeur.router("chose totalement inconnue")
        self.assertEqual(resultat["decision"], "modele")
        self.assertEqual(resultat["source"], "nouveau")

    def test_message_carte_contient_type(self):
        """Le message doit mentionner le type trouvé."""
        resultat = self.routeur.router("op_k7")
        self.assertIn("carte", resultat["message"])
        self.assertIn("outil", resultat["message"])

    def test_stats_carte(self):
        """La carte doit avoir des statistiques."""
        stats = self.routeur.carte_stats()
        self.assertIn("total_noeuds", stats)
        self.assertGreater(stats["total_noeuds"], 0)


class TestAdaptateurCarte(unittest.TestCase):

    def setUp(self):
        self.carte_test = {
            "zones": [
                {
                    "id": "test",
                    "nom": "Zone test",
                    "noeuds": [
                        {"id": "n1", "nom": "Agent Test", "type": "agent", "detail": "testeur"},
                        {"id": "n2", "nom": "Outil X", "type": "outil", "detail": "outil de test"}
                    ],
                    "liens": [
                        {"de": "n1", "vers": "n2", "quoi": "utilise"}
                    ]
                }
            ]
        }
        self.dossier_temp = tempfile.TemporaryDirectory()
        self.chemin = Path(self.dossier_temp.name) / "cartes.json"
        with open(self.chemin, 'w', encoding='utf-8') as f:
            json.dump(self.carte_test, f)

    def tearDown(self):
        self.dossier_temp.cleanup()

    def test_chargement(self):
        """L'adaptateur doit charger la carte."""
        from adaptateur_carte import AdaptateurCarte
        carte = AdaptateurCarte(str(self.chemin))
        self.assertEqual(len(carte.get_zones()), 1)

    def test_get_par_type(self):
        """get_par_type doit retourner les bons noeuds."""
        from adaptateur_carte import AdaptateurCarte
        carte = AdaptateurCarte(str(self.chemin))
        agents = carte.get_par_type("agent")
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0]["nom"], "Agent Test")

    def test_stats(self):
        """Les stats doivent être correctes."""
        from adaptateur_carte import AdaptateurCarte
        carte = AdaptateurCarte(str(self.chemin))
        stats = carte.stats()
        self.assertEqual(stats["total_noeuds"], 2)
        self.assertEqual(stats["total_zones"], 1)


class TestMemoire(unittest.TestCase):

    def setUp(self):
        self.dossier_temp = tempfile.TemporaryDirectory()
        self.chemin_db = Path(self.dossier_temp.name) / "test.db"

    def tearDown(self):
        self.dossier_temp.cleanup()

    def test_stocker_et_chercher(self):
        """On doit pouvoir stocker et retrouver une procédure."""
        from memory import Memoire
        mem = Memoire(str(self.chemin_db))
        mem.stocker("Test proc", "Description test", ["mot1", "mot2"], ["étape1"])
        resultat = mem.chercher("mot1")
        self.assertIsNotNone(resultat)
        self.assertEqual(resultat["nom"], "Test proc")

    def test_compter(self):
        """Le compteur doit fonctionner."""
        from memory import Memoire
        mem = Memoire(str(self.chemin_db))
        self.assertEqual(mem.compter(), 0)
        mem.stocker("P1", "D1", ["m1"], [])
        self.assertEqual(mem.compter(), 1)


if __name__ == "__main__":
    unittest.main()