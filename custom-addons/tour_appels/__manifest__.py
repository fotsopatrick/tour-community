# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Appels API",
    "version": "18.0.1.1.1",
    "summary": "Ce que la clé DeepSeek consomme encore : chaque appel consigné, borné, visible",
    "description": """
Appels API
==========

Un garde-fou n'est pas une décision, c'est un enregistrement : on ne peut pas
maîtriser une dépense qu'on ne voit pas. Ce module rend visible CHAQUE appel
fait avec la clé DeepSeek.

Le garde-fou vit à deux étages :
- sur l'HÔTE, `~/atelier/moteurs/compter_appel.py` consigne chaque appel dans
  `~/atelier/appels-api.jsonl` et refuse au-delà du budget du jour
  (`~/atelier/.budget-journalier`, jetons par jour) ;
- ici, la TOUR relève ce journal toutes les 5 minutes et l'affiche : par
  agent, par mission, par moteur, avec le coût estimé.

Les moteurs DeepSeek (deepseek-agent et toute future clé) sont branchés :
juste avant un appel ils demandent le feu vert (budget), juste après ils
consignent les jetons réels renvoyés par l'API. Ce que le garde-fou ne voit
pas n'existe pas — et ce qu'il refuse s'affiche aussi (case « refusé »).
    """,
    "author": "Code Nomi Nomi",
    "website": "https://matourdecontrole.fr",
    "category": "Tour de contrôle",
    "license": "OPL-1",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "data/appel_api_data.xml",
        "views/appel_api_views.xml",
        "views/appels_templates.xml",
    ],
    "installable": True,
    "application": True,
}
