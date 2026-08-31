# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Consoles",
    "summary": "Tous les tableaux de bord externes au même endroit",
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code No Mi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "icon": "/tour_consoles/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/console_views.xml",
        "data/console_data.xml",
    ],
    "installable": True,
    "application": True,
}
