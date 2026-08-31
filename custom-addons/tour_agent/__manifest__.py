# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Agent",
    "summary": "Exécute seul les tâches qu'on lui confie, dans des limites strictes",
    "version": "18.0.1.1.0",
    "author": "Patrick Fotso (Code No Mi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "icon": "/tour_agent/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["project", "tour_atelier", "tour_dashboard"],
    "data": [
        "views/agent_views.xml",
        "data/cron_data.xml",
    ],
    "installable": True,
    "application": False,
}
