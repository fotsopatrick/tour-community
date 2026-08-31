# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Dépôt",
    "summary": "La boîte à vrac : balancer du texte, des notes, des fichiers — lisible par le Copilote",
    "version": "18.0.1.2.1",
    "author": "Patrick Fotso (Code Nomi Nomi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "icon": "/tour_depot/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/depot_views.xml",
        "data/cron_data.xml",
    ],
    "installable": True,
    "application": True,
}
