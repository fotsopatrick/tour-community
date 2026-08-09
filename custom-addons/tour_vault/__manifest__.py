# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Vault",
    "summary": "Le coffre : mots de passe et clés d'API, chiffrés, jamais en clair dans la base",
    "version": "18.0.1.0.1",
    "author": "Patrick Fotso (Code Nomi Nomi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "icon": "/tour_vault/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["mail"],
    "data": [
        "security/vault_groups.xml",
        "security/ir.model.access.csv",
        "security/vault_rules.xml",
        "views/vault_views.xml",
    ],
    "installable": True,
    "application": True,
}
