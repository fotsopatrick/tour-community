# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Config Actions",
    "summary": "Choisir, pour chaque item du menu Actions de l'accueil, s'il est visible en PROD et/ou en DEMO.",
    "description": """
Milieu (06/08) — configurer la visibilité du menu « Actions ».

Chaque item du menu Actions du tableau de bord (Piloter, Équipe, Moi &
contenu, Sécurité & système, Public, Dehors) se coche séparément pour la
production et pour la démo. Le tableau de bord affiche ensuite les liens selon
ces réglages, en plus des règles de droits (admin / owner).

Privé : on n'y accède que connecté à la tour (groupes `base.group_user` +
`base.group_system` pour la modification). Jamais visible pour un compte
portail ni en public.
""",
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code No Mi)",
    "license": "OPL-1",
    "icon": "/tour_actions/static/description/icon.svg",
    "category": "Productivity",
    "depends": ["base", "tour_dashboard"],
    "data": [
        "security/ir.model.access.csv",
        "data/actions_data.xml",
        "views/tour_actions_views.xml",
        "views/actions_config_web.xml",
    ],
    "installable": True,
    "application": False,
}
