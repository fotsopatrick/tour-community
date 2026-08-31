# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Dev",
    "summary": "Remonte les tickets Jira et les confie à l'atelier",
    "version": "18.0.1.1.0",
    "author": "Patrick Fotso (Code No Mi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "icon": "/tour_dev/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["mail", "tour_vault", "tour_atelier"],
    "data": [
        "security/ir.model.access.csv",
        "security/dev_rules.xml",
        "views/dev_views.xml",
        "data/cron_data.xml",
    ],
    "installable": True,
    "application": True,
}
