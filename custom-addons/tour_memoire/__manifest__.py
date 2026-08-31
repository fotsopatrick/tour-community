# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de Contrôle — Mémoire indexée (rappel)",
    "summary": "Outil de rappel : interroge la mémoire de la tour et des webapps",
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code No Mi)",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["base", "web"],
    "data": [
        "views/memoire_templates.xml",
        "views/menu.xml",
    ],
    "post_init_hook": "_installer_garde_fou",
    "installable": True,
    "application": True,
}
