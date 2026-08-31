# ============================================================
# ADAPTATEUR CARTE — comme le GPS d'Alice
# Il lit la carte vivante (cartes.json) et aide le routeur à se repérer.
# ============================================================

import json
from pathlib import Path

class AdaptateurCarte:
    """
    L'adaptateur carte est comme un GPS.
    Il lit la carte et dit où se trouve chaque chose.
    """

    def __init__(self, chemin_carte="carte-vivante/cartes.json"):
        self.chemin_carte = Path(chemin_carte)
        self.carte = None
        self._charger()

    def _charger(self):
        """Ouvre la carte et la lit."""
        if not self.chemin_carte.exists():
            self.carte = {"zones": []}
            return
        with open(self.chemin_carte, 'r', encoding='utf-8') as f:
            self.carte = json.load(f)

    def get_tous_les_noeuds(self):
        """
        Retourne tous les nœuds de la carte, avec leur type.
        Comme une liste de tous les endroits sur le GPS.
        """
        noeuds = []
        for zone in self.carte.get("zones", []):
            for noeud in zone.get("noeuds", []):
                noeuds.append({
                    "id": noeud.get("id"),
                    "nom": noeud.get("nom"),
                    "type": noeud.get("type"),
                    "zone": zone.get("nom"),
                    "detail": noeud.get("detail", ""),
                    "mots_cles": noeud.get("mots_cles", []),
                    "etapes": noeud.get("etapes", [])
                })
        return noeuds

    def get_noeuds_par_type(self, type_noeud):
        """Retourne tous les nœuds d'un type donné (ex: 'circuit', 'outil')."""
        return [n for n in self.get_tous_les_noeuds() if n["type"] == type_noeud]

    # Alias pour compatibilité avec les anciens tests
    def get_par_type(self, type_noeud):
        """Alias de get_noeuds_par_type pour compatibilité."""
        return self.get_noeuds_par_type(type_noeud)

    def get_zones(self):
        """Retourne les zones de la carte."""
        return self.carte.get("zones", [])

    def stats(self):
        """Retourne des statistiques sur la carte."""
        noeuds = self.get_tous_les_noeuds()
        types = {}
        for n in noeuds:
            t = n["type"]
            types[t] = types.get(t, 0) + 1
        stats = dict(types)
        stats["total_noeuds"] = len(noeuds)
        stats["total_zones"] = len(self.carte.get("zones", []))
        return stats