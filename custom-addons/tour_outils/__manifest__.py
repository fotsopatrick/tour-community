# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Outils",
    "summary": "La boîte à outils : chaque outil, son fichier et son mode d'emploi",
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code No Mi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "icon": "/tour_outils/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/outil_views.xml",
        "data/outil_data.xml",
    ],
    "installable": True,
    "application": True,
}
