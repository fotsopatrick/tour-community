# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — thème Community",
    "summary": "Page de connexion, accueil et backend aux couleurs de la tour.",
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code Nomi Nomi)",
    "license": "AGPL-3",
    "category": "Theme",
    "depends": ["base", "web", "mail", "auth_signup"],
    "data": [
        "views/webclient_templates.xml",
        "views/accueil_templates.xml",
        "data/mail_debrand.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "tour_community_theme/static/src/login/login.scss",
        ],
        "web.assets_backend": [
            "tour_community_theme/static/src/backend/theme.scss",
        ],
    },
    "installable": True,
    "application": False,
}
