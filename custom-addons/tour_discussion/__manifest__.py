# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Clark",
    "summary": "Discuter avec Clark, l'agent qui écrit le code, depuis la tour",
    "version": "18.0.1.0.1",
    "author": "Patrick Fotso (Code No Mi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "icon": "/tour_discussion/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["base", "tour_atelier"],
    "assets": {
        "web.assets_backend": [
            "tour_discussion/static/src/programme.js",
        ],
    },
    "data": [
        "security/ir.model.access.csv",
        "security/discussion_security.xml",
        "views/discussion_views.xml",
        "data/cron.xml",
    ],
    "installable": True,
    "application": True,
}
