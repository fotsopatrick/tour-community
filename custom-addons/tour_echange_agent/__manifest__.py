# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Échanges entre agents",
    "summary": "Un agent demande, un autre agent répond : le résultat revient au demandeur.",
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code No Mi) + Raphaël",
    "license": "OPL-1",
    "icon": "/tour_echange_agent/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["base", "tour_discussion", "tour_flux", "tour_equipage"],
    "data": [
        "security/ir.model.access.csv",
        "views/echange_views.xml",
        "data/cron.xml",
    ],
    "installable": True,
    "application": False,
}
