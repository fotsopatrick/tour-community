# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Sauvegardes",
    "summary": "Voir les sauvegardes, et être prévenu quand elles échouent",
    "version": "18.0.1.1.0",
    "author": "Patrick Fotso (Code No Mi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "AGPL-3",
    "icon": "/tour_sauvegardes/static/description/icon.svg",
    "category": "Administration",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/sauvegarde_views.xml",
        "data/cron_data.xml",
    ],
    "installable": True,
    "application": False,
}
