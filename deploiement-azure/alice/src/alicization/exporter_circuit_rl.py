#!/usr/bin/env python3
# /home/orel/alicization/exporter_circuit_rl.py
# Exporte le circuit RL dans la carte vivante (et la politique sur disque).
#
# Usage :
#   # entraîne, sauvegarde la politique et ajoute/maj le circuit dans cartes.json
#   python3 exporter_circuit_rl.py

import os
import sys
import json

ICI = os.path.dirname(os.path.abspath(__file__))
if ICI not in sys.path:
    sys.path.insert(0, ICI)

from rl.environnement import DonjonSimpleEnv
from rl.entrainer import (
    q_learning,
    exporter_politique_vers_circuit,
    sauvegarder_politique,
)

CHEMIN_CARTE = "/home/alice/carte-vivante/cartes.json"
CHEMIN_POLITIQUE = os.path.join(ICI, "state", "politique_donjon.json")
ID_CIRCUIT = "se-deplacer-vers-la-cible-rl"

# Tailles par défaut de l'entraînement
TAILLE = 5
EPISODES = 1000


def ajouter_circuit_a_la_carte(chemin_carte, circuit):
    """
    Ajoute (ou met à jour, sans dupliquer) un circuit dans la zone 'connaissances'.
    Retourne le nombre de noeuds portant ce circuit après l'ajout.
    """
    with open(chemin_carte, "r", encoding="utf-8") as f:
        carte = json.load(f)

    zone = next((z for z in carte.get("zones", []) if z.get("id") == "connaissances"), None)
    if zone is None:
        raise ValueError("La zone 'connaissances' est absente de la carte.")

    noeuds = zone.setdefault("noeuds", [])
    for n in noeuds[:]:
        if n.get("id") == circuit.get("id"):
            noeuds.remove(n)
    noeuds.append(circuit)

    with open(chemin_carte, "w", encoding="utf-8") as f:
        json.dump(carte, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return len([n for n in noeuds if n.get("id") == circuit.get("id")])


if __name__ == "__main__":
    env = DonjonSimpleEnv(size=TAILLE)
    Q, politique, recompenses = q_learning(env, episodes=EPISODES)

    os.makedirs(os.path.dirname(CHEMIN_POLITIQUE), exist_ok=True)
    sauvegarder_politique(politique, CHEMIN_POLITIQUE)

    circuit = exporter_politique_vers_circuit(
        politique, nom="Se déplacer vers la cible (RL)", taille=TAILLE)
    circuit["id"] = ID_CIRCUIT

    nb = ajouter_circuit_a_la_carte(CHEMIN_CARTE, circuit)

    print("Récompense moyenne (100 dernières) :", sum(recompenses[-100:]) / 100)
    print("États appris :", len(politique))
    print("Règles dans le circuit (écarts cible-agent) :", len(circuit["etapes"]) - 1)
    print("Circuit", ID_CIRCUIT, "en place dans la carte :", nb, "noeud")