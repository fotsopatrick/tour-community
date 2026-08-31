# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Déploiement",
    "version": "18.0.1.0.0",
    "summary": "Mettre un site en ligne depuis la tour, sans un seul clic ailleurs",
    "description": """
Déployer un site sans ouvrir une interface
==========================================

Jusqu'ici, livrer un site demandait d'ouvrir quatre onglets : créer le projet
de base de données, coller les migrations dans un éditeur SQL, créer le site
chez l'hébergeur, recopier les clés. Chaque geste manuel est un geste qu'on
oublie, qu'on fait dans le désordre, ou qu'on fait sur le mauvais projet.

Ce module fait les sept étapes à la suite et **rend compte de chacune**. Il
n'annonce jamais une réussite qu'il n'a pas constatée : la dernière étape
regarde la page livrée, parce qu'un site au CSS cassé et une boutique vide
répondent tous les deux 200.
    """,
    "author": "Code Nomi Nomi",
    "website": "https://matourdecontrole.fr",
    "category": "Tour de contrôle",
    "license": "LGPL-3",
    "depends": ["base", "mail", "tour_vault"],
    "data": [
        "security/ir.model.access.csv",
        "views/deploiement_views.xml",
    ],
    "installable": True,
    "application": True,
}
