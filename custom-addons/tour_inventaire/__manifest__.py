# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Inventaire des modules",
    "version": "18.0.1.0.0",
    "summary": "La liste de tout ce qui compose la tour, à jour, pour tout retrouver",
    "description": """
Inventaire des modules
======================

Quarante-neuf modules maison, personne ne savait où ils en étaient. Cette
liste vit dans la tour : un module = une ligne (installé ? version ? ce qu'il
fait ? qui en est responsable ? état). Elle se recale toute seule sur la
réalité chaque nuit — un module installé apparaît, un module retiré disparaît.

Le chemin pour la retrouver : menu « Modules » (Pilotage). C'est LA liste de
référence, consignée dans la connaissance de bord.
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["base", "tour_equipage"],
    "data": [
        "security/ir.model.access.csv",
        "views/tour_inventaire_views.xml",
    ],
    "installable": True,
    "application": True,
}
