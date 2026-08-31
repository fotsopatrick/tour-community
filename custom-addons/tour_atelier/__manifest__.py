# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Atelier",
    "summary": "Confier une mission de développement, depuis le téléphone",
    "version": "18.0.1.3.9",
    "author": "Patrick Fotso (Code No Mi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "icon": "/tour_atelier/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["mail"],
    "data": [
        "security/ir.model.access.csv",
        "security/regles.xml",
        "views/mission_views.xml",
        "data/cron_data.xml",
    ],
    "installable": True,
    "application": True,
}
