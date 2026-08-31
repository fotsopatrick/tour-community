# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Le Pilote",
    "summary": "Un moteur qui joue les gabarits de circuits via l'API Odoo : modèle simple + consultation en ligne, jamais le choix du gabarit.",
    "description": """
Le Pilote (10/08, Patrick : « un modèle simple qui ne réfléchit pas, à qui on
donne les méthodes et process de résolution ainsi que la consultation en
ligne »).

Ce module fait tourner un GABARIT DE CIRCUIT de bout en bout avec un modèle
simple (deepseek-chat, qui ne raisonne pas). Le modèle n'a PAS à choisir : il
reçoit le gabarit désigné, sa consigne (le sujet), et les portes une par une.
À chaque porte « agent », le pilote produit le contenu demandé en consultant
en ligne (lire_web / chercher_web) et en lisant la tour (API Odoo), puis
avance.

RÈGLE FERME (posée le 10/08, et c'est ce qui protège la tour) :
- le pilote n'ouvre JAMAIS un gabarit tout seul : il exécute celui que la
  demande de pilotage désigne ;
- les portes « patron » (Patrick) lui sont interdites : il s'arrête et
  attend Patrick ;
- chaque action est consignée dans le journal de la demande.

- pilote.demande : la demande de pilotage (gabarit + sujet + état + journal)
- contrôleur /tour/pilote/... : le moteur hôte communique par là (JSON)
- le moteur hôte pilote.py : boucle « demander la tâche → appeler le modèle
  simple avec la consigne → rendre la réponse → avancer la porte »
""",
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code No Mi)",
    "license": "OPL-1",
    "icon": "/tour_pilotage/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["base", "tour_dashboard", "tour_circuits", "tour_atelier",
                "tour_decisions"],
    "data": [
        "security/ir.model.access.csv",
        "views/pilote_views.xml",
        "views/pilote_cockpit.xml",
    ],
    "installable": True,
    "application": False,
}
