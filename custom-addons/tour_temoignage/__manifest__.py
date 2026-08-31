# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Témoignages",
    "summary": "Chaque membre de l'équipe tient son témoignage — vécu, daté, jamais inventé",
    "version": "18.0.1.1.0",
    "author": "Code Nomi Nomi",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "icon": "/tour_temoignage/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["base", "mail", "tour_atelier", "tour_equipage"],
    "data": [
        "security/ir.model.access.csv",
        "views/temoignage_views.xml",
        "views/page_temoignages_public.xml",
    ],
    "installable": True,
    "application": True,
}
