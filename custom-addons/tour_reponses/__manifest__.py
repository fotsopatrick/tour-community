# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Réponses",
    "summary": "Garder les réponses reçues : une question, sa réponse, qui et quand",
    "version": "18.0.1.0.3",
    "author": "Code Nomi Nomi",
    # Proprietaire, comme le reste du coeur de la tour.
    "license": "AGPL-3",
    "icon": "/tour_reponses/static/description/icon.svg",
    "category": "Productivity",
    # Aucune dependance au-dela du socle : une reponse conservee ne doit pas
    # exiger qu'un autre module de la tour soit installe.
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "security/reponse_rules.xml",
        "views/reponse_views.xml",
        "views/reponses_page.xml",
    ],
    "installable": True,
    "application": True,
}
