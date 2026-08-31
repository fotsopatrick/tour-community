# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour — Coût du logiciel",
    "version": "18.0.1.1.0",
    "summary": "Ce que chaque partie coûte vraiment, par mois et par projet — "
               "mesuré quand c'est mesurable, déclaré sinon, et jamais deviné.",
    # Patrick, 29/07 : « que nous coûte l'automatisation en ressource ? ça
    # signifie quoi en argent ? on peut sûrement déployer quelque chose qui
    # nous dit ce que coûte chaque partie du logiciel ».
    "license": "OPL-1",
    "author": "Code Nomi Nomi",
    "category": "Productivity",
    "depends": ["suivi_apps"],
    "data": [
        "security/ir.model.access.csv",
        "views/cout_views.xml",
        "data/cout_data.xml",
    ],
    "installable": True,
    "application": True,
}
