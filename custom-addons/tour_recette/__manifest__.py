# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Recette (Vibe)",
    "summary": "Dérouler un cahier de recette sur ses sites et alerter aux régressions",
    "description": """
Vibe déroule un cahier de vérifications sur les sites qu'on lui confie et
prévient QUAND CE QUI MARCHAIT NE MARCHE PLUS.

La v1 ne pilote pas de navigateur : elle fait des contrôles HTTP en Python
standard. C'est délibéré — ça attrape ce qui casse vraiment (page morte,
image absente, catalogue vide, texte disparu), ça ne demande aucune
infrastructure nouvelle, et ça ne se trompe jamais. Un testeur qui crie au
loup est désactivé en une semaine, et plus rien n'est testé.
    """,
    "version": "18.0.1.0.4",
    "author": "Patrick Fotso (Code Nomi Nomi)",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "AGPL-3",
    "category": "Productivity",
    "depends": ["base", "project", "mail"],
    "data": [
        "views/bug_recette_views.xml",
        "security/ir.model.access.csv",
        "views/recette_views.xml",
        "views/tests_cockpit_templates.xml",
        "data/mail_data.xml",
        "data/cron_data.xml",
        "data/cahier_boutique.xml",
        "data/rendu_0908.xml",
    ],
    "installable": True,
    "application": True,
}
