# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour — Clone de Patrick",
    "summary": "Le clone : apprend ton style, te propose, et n'agit jamais sans validation.",
    "version": "18.0.1.1.0",
    "author": "Patrick Fotso (Code No Mi) + Raphaël",
    "license": "OPL-1",
    "icon": "/tour_clone/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["base", "tour_equipage", "tour_atelier", "tour_circuits", "tour_decisions", "tour_actus", "tour_copilote"],
    "data": [
        "security/ir.model.access.csv",
        "data/clone_seed.xml",
        "views/decision_views.xml",
        "views/membre_views.xml",
        "views/page_atelier.xml",
        "views/app_menu.xml",
    ],
    "installable": True,
    "application": False,
}
