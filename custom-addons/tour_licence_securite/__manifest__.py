# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour — Sécurité licences",
    "summary": "Verrou anti-bruteforce des paquets livrés : 1 tentative → blocage + mot de passe de secours par mail",
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code No Mi)",
    "license": "OPL-1",
    "category": "Security",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/licence_alerte_views.xml",
    ],
    "installable": True,
    "application": False,
}
