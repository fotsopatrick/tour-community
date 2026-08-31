# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Victor — sécurité",
    "version": "18.0.1.2.0",
    "summary": "Un agent qui surveille la sécurité, propose, et n'agit qu'avec ton accord",
    "description": """
Victor
======

Un agent de sécurité qui tient sur trois refus.

**Il refuse de consommer de l'IA.** Ses contrôles sont du code déterministe :
un contrôle de sécurité doit rendre le même verdict deux fois de suite. Une
réponse qui varie n'est pas un contrôle, c'est un avis. Il tourne donc
gratuitement, même quand plus aucun quota n'est disponible.

**Il refuse de réparer sans accord.** Chaque constat propose un correctif et
attend : accepté, plus tard, ou refusé. Un agent qui corrige seul la sécurité
modifie exactement les réglages dont dépend la capacité à l'arrêter.

**Il refuse d'insister.** Un constat refusé n'est pas reproposé. C'est ainsi
qu'un outil devient du bruit, et que le vrai problème finit ignoré avec les
autres.

La réponse se donne d'un clic depuis le courriel, sans se connecter — sinon
elle attend une semaine.
    """,
    "author": "Code Nomi Nomi",
    "website": "https://matourdecontrole.fr",
    "category": "Tour de contrôle",
    "license": "OPL-1",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/securite_data.xml",
        "views/securite_views.xml",
        "views/interrupteur_views.xml",
        "views/pentest_views.xml",
    ],
    "installable": True,
    "application": True,
}
