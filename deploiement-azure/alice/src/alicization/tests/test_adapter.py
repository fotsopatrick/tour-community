# -*- coding: utf-8 -*-
"""
TESTS DE L'ADAPTER ALICIZATION
Vérifie que le routeur est bien intégré dans teach().
"""

import unittest
import tempfile
import json
import sys
from pathlib import Path

# Ajouter le chemin pour importer les modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from alicization_adapter import AlicizationAdapter


class TestAlicizationAdapter(unittest.TestCase):

    def setUp(self):
        """Crée un adapter temporaire pour les tests."""
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
                            "mots_cles": ["712", "procédure"],
                            "etapes": ["op_q9", "op_k7"]
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
        with open(self.chemin_carte, 'w', encoding='utf-8') as f:
            json.dump(self.carte_test, f)

        self.chemin_db = Path(self.dossier_temp.name) / "memoire.db"

        # Créer l'adapter
        self.adapter = AlicizationAdapter(
            chemin_carte=str(self.chemin_carte),
            chemin_db=str(self.chemin_db)
        )

    def tearDown(self):
        self.dossier_temp.cleanup()

    def test_adapter_trouve_circuit_dans_carte(self):
        """L'adapter doit trouver un circuit dans la carte."""
        resultat = self.adapter.teach("712")
        self.assertIsNotNone(resultat)
        self.assertEqual(resultat, ["op_q9", "op_k7"])

    def test_adapter_trouve_outil_dans_carte(self):
        """L'adapter doit trouver un outil dans la carte."""
        resultat = self.adapter.teach("op_k7")
        self.assertIsNotNone(resultat)

    def test_adapter_appelle_modele_si_rien_trouve(self):
        """L'adapter doit appeler le modèle si rien n'est trouvé."""
        appel_modele = []
        def mock_model(task):
            appel_modele.append(task)
            return ["etape1", "etape2"]

        resultat = self.adapter.teach("chose inconnue", model_call=mock_model)
        self.assertEqual(len(appel_modele), 1)
        self.assertEqual(resultat, ["etape1", "etape2"])

    def test_adapter_enregistre_nouvelle_procedure(self):
        """L'adapter doit enregistrer la nouvelle procédure dans la mémoire."""
        def mock_model(task):
            return ["nouvelle_etape"]

        self.adapter.teach("nouvelle tache", model_call=mock_model)

        # Vérifier que la procédure est enregistrée
        stats = self.adapter.get_stats()
        self.assertEqual(stats["memoire"]["total"], 1)

    def test_adapter_retrouve_procedure_apres_enregistrement(self):
        """L'adapter doit retrouver une procédure après l'avoir enregistrée."""
        # Premier appel : le modèle apprend
        def mock_model(task):
            return ["apprendre", "coder"]
        self.adapter.teach("apprendre coder", model_call=mock_model)

        # Deuxième appel : le routeur doit trouver la procédure
        resultat = self.adapter.teach("apprendre coder")
        self.assertIsNotNone(resultat)

    def test_adapter_stats(self):
        """Les stats doivent être cohérentes."""
        stats = self.adapter.get_stats()
        self.assertIn("routeur", stats)
        self.assertIn("memoire", stats)


if __name__ == "__main__":
    unittest.main()