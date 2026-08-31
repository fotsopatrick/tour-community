# -*- coding: utf-8 -*-
"""
ALICIZATION — Point d'entrée principal
Utilise le routeur avec la carte vivante comme source principale de connaissance.
"""

import sys
import os

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from routeur_avec_carte import Routeur


def main():
    """Point d'entrée principal du système Alicization."""
    print("=" * 60)
    print("ALICIZATION — Routeur avec Carte Vivante")
    print("=" * 60)
    print()

    # Initialiser le routeur avec la vraie carte
    carte_path = os.path.join(os.path.dirname(__file__), '..', 'carte-vivante', 'cartes.json')
    db_path = os.path.join(os.path.dirname(__file__), 'state', 'alicization.db')

    routeur = Routeur(chemin_carte=carte_path, chemin_db=db_path)

    # Afficher les stats
    stats = routeur.carte_stats()
    print(f"Carte chargée : {stats.get('total_noeuds', 0)} noeuds "
          f"dans {stats.get('total_zones', 0)} zones")
    print()

    # Mode interactif
    print("Tapez une requête pour tester le routeur.")
    print("Tapez 'quit' pour quitter.")
    print()

    while True:
        try:
            requete = input("Requête > ").strip()
            if not requete or requete.lower() == 'quit':
                print("Au revoir!")
                break

            resultat = routeur.router(requete)

            print(f"  Décision : {resultat['decision']}")
            print(f"  Source   : {resultat['source']}")
            if resultat['decision'] == 'circuit':
                info = resultat['info']
                print(f"  Type     : {info['type']}")
                print(f"  Nom      : {info['data'].get('nom', 'N/A')}")
            print(f"  Message  : {resultat['message']}")
            print()

        except (KeyboardInterrupt, EOFError):
            print("\nAu revoir!")
            break


if __name__ == "__main__":
    main()