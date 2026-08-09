# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Actus",
    "summary": "Fil d'actualités par centres d'intérêt (flux RSS gratuits) sur la page d'accueil",
    "version": "18.0.1.1.0",
    "author": "Patrick Fotso (Code Nomi Nomi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "AGPL-3",
    "icon": "/tour_actus/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["web", "base"],
    "data": [
        "security/ir.model.access.csv",
        "views/actus_views.xml",
        "data/flux_data.xml",
        "data/cron_data.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "tour_actus/static/src/actus/actus.js",
            "tour_actus/static/src/actus/actus.xml",
            "tour_actus/static/src/actus/actus.scss",
        ],
    },
    "installable": True,
    "application": True,
}
