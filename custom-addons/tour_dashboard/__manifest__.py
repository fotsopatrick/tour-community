# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Dashboard",
    "summary": "La page d'accueil : ce qui t'attend, ce que je fais, puis les actus",
    "version": "18.0.1.3.0",
    "author": "Patrick Fotso (Code No Mi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "icon": "/tour_dashboard/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["project", "tour_actus", "tour_vault"],
    "data": [
        "security/ir.model.access.csv",
        "data/stage_data.xml",
        "data/stripe_cron.xml",
        "views/task_views.xml",
        "views/menu_pilotage.xml",
        "views/dashboard_templates.xml",
        "views/page_attention.xml",
        "views/cap_views.xml",
        "data/action_data.xml",
        "views/claude_action.xml",
    ],
    "installable": True,
    "application": False,
}
