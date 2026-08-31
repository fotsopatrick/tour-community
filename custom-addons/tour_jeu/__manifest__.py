# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Le Jeu de la Tour",
    "summary": "Un jeu façon Pokémon : la tour évolue quand on travaille vraiment",
    "description": (
        "La boucle Pokémon (explorer → rencontrer → faire évoluer) construite "
        "sur les DONNÉES réelles de la tour, pas sur des points inventés. "
        "Règle du jeu : « un chiffre compté informe, un chiffre gagné en "
        "jouant décore ». Ta tour monte quand tu conclus un circuit, tu passes "
        "un test au vert, tu poses un garde-fou, tu corriges un bug. Les tours "
        "des autres ne montrent que des métadonnées — jamais la clé de la porte."
    ),
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code No Mi)",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["tour_circuits", "tour_recette", "tour_garde_fous",
                "tour_retours"],
    "data": [
        "security/ir.model.access.csv",
        "views/jeu_templates.xml",
    ],
    "installable": True,
    "application": True,
}
