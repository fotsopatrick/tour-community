# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Générateur de sites",
    "summary": "Décrire un site, obtenir une adresse vivante",
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code No Mi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "icon": "/tour_generateur/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["base", "tour_copilote"],
    "data": [
        "security/ir.model.access.csv",
        "views/site_views.xml",
    ],
    "installable": True,
    "application": True,
}
