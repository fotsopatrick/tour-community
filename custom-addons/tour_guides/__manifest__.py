# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Guides",
    "summary": "Astuces d'utilisation et mémoire technique, cherchables",
    "version": "18.0.1.1.3",
    "author": "Patrick Fotso (Code No Mi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "icon": "/tour_guides/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["base", "project"],
    "data": [
        "security/ir.model.access.csv",
        "views/guide_views.xml",
        "views/guides_page.xml",
        "data/guide_data.xml",
        "data/cron_data.xml",
    ],
    "installable": True,
    "application": True,
}
