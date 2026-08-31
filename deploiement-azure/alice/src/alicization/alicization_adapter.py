# -*- coding: utf-8 -*-
"""
ALICIZATION ADAPTER — L'interface entre Alice et le routeur.
Alice consulte le routeur AVANT de faire quoi que ce soit.
"""

import sys
from pathlib import Path

# Ajouter le chemin pour importer le routeur
sys.path.insert(0, str(Path(__file__).parent.parent))

from routeur import Routeur


class AlicizationAdapter:
    """
    L'adapter connecte Alice au routeur.
    Il s'assure qu'Alice consulte la carte et la mémoire avant d'appeler le modèle.
    """

    def __init__(self, chemin_carte="../carte-vivante/cartes.json", chemin_db="../state/alicization.db"):
        # 1. CRÉER LE ROUTEUR
        self.routeur = Routeur(
            chemin_carte=chemin_carte,
            chemin_db=chemin_db
        )

    def teach(self, task_description, model_call=None):
        """
        La fonction teach() — le cœur d'Alice.
        Elle consulte d'abord le routeur, puis appelle le modèle si nécessaire.
        """
        print(f"🎓 teach() appelée pour : {task_description}")

        # 2. CONSULTER LE ROUTEUR
        resultat_routeur = self.routeur.router(task_description)

        # 3. SI LE ROUTEUR TROUVE UNE PROCÉDURE → CIRCUIT
        if resultat_routeur["decision"] == "circuit":
            info = resultat_routeur["info"]
            nom_procedure = info.get("nom", info.get("data", {}).get("nom", "inconnue"))
            print(f"✅ Routeur : procédure trouvée dans {resultat_routeur['source']} → {nom_procedure}")

            # On essaie d'extraire les étapes
            etapes = info.get("etapes", info.get("data", {}).get("etapes", []))
            if etapes:
                return etapes
            else:
                # Si le nœud n'a pas d'étapes, on retourne son nom en tant que procédure
                return [nom_procedure] if nom_procedure != "inconnue" else None

        # 4. SI LE ROUTEUR NE TROUVE RIEN → MODÈLE (apprentissage)
        print("🔄 Routeur : aucune procédure trouvée → appel au modèle")

        # Appeler le modèle si une fonction est fournie
        if model_call:
            procedure_trouvee = model_call(task_description)
        else:
            # Simulation pour les tests
            procedure_trouvee = None

        # 5. ENREGISTRER LA NOUVELLE PROCÉDURE DANS LA MÉMOIRE
        if procedure_trouvee:
            nom_procedure = " ".join(procedure_trouvee)
            self.routeur.memoire.ajouter(
                nom_procedure,
                procedure_trouvee,
                description=f"Apprise pendant la tâche : {task_description}"
            )
            print(f"✅ Routeur : nouvelle procédure enregistrée → {nom_procedure}")

        return procedure_trouvee

    def get_stats(self):
        """Retourne les statistiques de l'adapter."""
        return {
            "routeur": self.routeur.carte_stats(),
            "memoire": self.routeur.memoire.get_stats()
        }