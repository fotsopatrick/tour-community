# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Rappels",
    "summary": "Rappels récurrents qui atterrissent dans les activités Odoo (horloge du haut)",
    "version": "18.0.1.0.1",
    "author": "Patrick Fotso (Code No Mi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "AGPL-3",
    "icon": "/tour_rappels/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["mail"],
    "data": [
        "security/ir.model.access.csv",
        "security/rappel_rules.xml",
        "views/rappel_views.xml",
        "data/cron_data.xml",
        "data/rappel_data.xml",
    ],
    "installable": True,
    "application": False,
}
