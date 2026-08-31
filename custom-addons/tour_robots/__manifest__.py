# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de Contrôle — Robots",
    "summary": "Qui sont les robots venus sur les sites, quand, et ce qu'ils ont fait",
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code No Mi)",
    # Proprietaire, comme le reste de la tour : revente a un seul niveau.
    "license": "OPL-1",
    "category": "Administration",
    "depends": ["base", "web", "tour_cockpit"],
    "data": [
        "security/ir.model.access.csv",
        "views/robots_views.xml",
        "views/robots_templates.xml",
        "data/cron_data.xml",
    ],
    "installable": True,
    "application": False,
}
