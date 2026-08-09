# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Chat Community",
    "summary": "Chloé, l'assistante de l'édition Community : discute avec elle.",
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code Nomi Nomi)",
    "license": "AGPL-3",
    "category": "Productivity",
    "depends": ["base", "web", "mail"],
    "data": [
        "views/chat_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "tour_community_chat/static/src/chat.scss",
        ],
    },
    "installable": True,
    "application": False,
}
