# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Chrono",
    "summary": "Le temps passe sur chaque projet, par chaque agent — mesure, jamais devine",
    "version": "18.0.1.0.1",
    "author": "Code Nomi Nomi",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "icon": "/tour_chrono/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["base", "project", "tour_dashboard", "tour_atelier"],
    "data": [
        "security/ir.model.access.csv",
        "views/chrono_views.xml",
    ],
    "installable": True,
    "application": True,
}
