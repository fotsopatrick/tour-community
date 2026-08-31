# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Braignak",
    "summary": "L'observateur : étudier une application, en tirer ce qui manque à la tour",
    "description": """
Braignak regarde une application, comprend ce qu'elle sait faire, et dit
lesquelles de ces capacités mériteraient d'entrer dans la tour.

Version 1 : il ne se lance jamais tout seul, ne publie rien, et n'envoie
aucune mission sans qu'un humain appuie sur le bouton. Deux verrous
l'empêchent de démarrer, dont un que la tour elle-même ne peut pas ouvrir.
    """,
    "version": "18.0.1.1.3",
    "author": "Patrick Fotso (Code Nomi Nomi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["tour_atelier", "tour_guides", "project", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rules.xml",
        "views/braignak_views.xml",
        "views/res_config_views.xml",
        "data/guide_data.xml",
    ],
    "installable": True,
    "application": True,
}
