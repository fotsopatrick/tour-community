# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour — Extension navigateur",
    "summary": "Le pont navigateur : Braignak cherche sur le web via le navigateur de Patrick.",
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code No Mi) + Raphaël",
    "license": "OPL-1",
    "icon": "/tour_extension/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["base", "tour_dashboard"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_views.xml",
        "views/template.xml",
    ],
    "installable": True,
    "application": False,
}
