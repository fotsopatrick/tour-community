# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Observateur Community",
    "summary": "Braignak, l'observateur de l'édition Community : analyse une app, dit ce qui manque.",
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code Nomi Nomi)",
    "license": "AGPL-3",
    "category": "Productivity",
    "depends": ["base", "web", "mail"],
    "data": [
        "views/braignak_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "tour_community_braignak/static/src/braignak.scss",
        ],
    },
    "installable": True,
    "application": False,
}
