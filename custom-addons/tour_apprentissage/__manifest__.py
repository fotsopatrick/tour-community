# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Apprentissage des agents",
    "summary": "Recherche & Résultat : ce que la tour apprend des livres, rangé leçon par leçon",
    "description": (
        "Demandé par Patrick le 05/08/2026 : lire les livres de manière "
        "incrémentale (page par page, chapitre par chapitre), étudier, "
        "analyser, comprendre — et stocker chaque leçon ici. "
        "Une source = un livre ou un dépôt. Une leçon = source exacte, "
        "constat reformulé, ce que ça change pour la tour, action, état. "
        "Une leçon sans impact tour est du bruit : refusée."
    ),
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code No Mi)",
    "license": "AGPL-3",
    "category": "Productivity",
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/apprentissage_views.xml",
    ],
    "installable": True,
    "application": True,
}
