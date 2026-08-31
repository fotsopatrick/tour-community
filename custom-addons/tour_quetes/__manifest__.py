# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Quêtes",
    "summary": "Des offres d'emploi deviennent des quêtes qui couvrent toutes les compétences demandées",
    "description": (
        "Une offre d'emploi collée devient un registre de quêtes, comme dans un "
        "JRPG : chaque compétence demandée par l'annonce donne une quête "
        "« Maîtrise — X », les quêtes se rangent par domaine (la roue) et par "
        "guilde, et une quête accomplie rapporte de l'XP réel (compteur mesuré, "
        "registre equipe.exploit)."
    ),
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code No Mi)",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["mail", "tour_equipage", "tour_entretiens"],
    "data": [
        "security/ir.model.access.csv",
        "data/seed.xml",
        "views/quete_views.xml",
        "views/quetes_templates.xml",
    ],
    "installable": True,
    "application": True,
    "post_init_hook": "post_init",
}
