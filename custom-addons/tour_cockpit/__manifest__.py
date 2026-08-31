# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de Contrôle — Cockpit",
    "summary": "2e tableau de bord look cockpit : projets et tâches en direct",
    "version": "18.0.1.2.3",
    "author": "Patrick Fotso (Code No Mi)",
    # Proprietaire, comme tour_dashboard : revente a un seul niveau possible.
    "license": "OPL-1",
    "icon": "/tour_cockpit/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["base", "web", "project"],
    "data": [
        "views/cockpit_templates.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "application": True,
}
