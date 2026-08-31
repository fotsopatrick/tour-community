# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Le Jeu de Braignak",
    "summary": "Le jeu hebdomadaire : des idées en prompt limité, un verdict de Braignak",
    "description": (
        "Le jeu hebdomadaire posé par le propriétaire (tâche 193, 26/07) : "
        "chaque semaine Braignak ouvre les inscriptions, les inscrits "
        "soumettent des idées d'amélioration de la tour sous forme de prompt "
        "limité. Au seuil, les inscriptions ferment. Le lendemain à 7 h, "
        "Braignak rend son verdict à chaque participant en expliquant ses "
        "choix — des choix qui ne valent que dans le monde virtuel. Le défi "
        "caché : lui faire accepter une idée qui améliore RÉELLEMENT la tour. "
        "Le gagnant débloque une question posée à la tour, ou un sous-domaine."
    ),
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code No Mi)",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "data/cron.xml",
        "views/jeu_braignak_templates.xml",
        "views/jeu_braignak_views.xml",
    ],
    "installable": True,
    "application": True,
}
