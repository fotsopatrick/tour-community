# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Copilote IA",
    "summary": "Chat Claude flottant sur toutes les pages pour piloter la tour de controle",
    "version": "18.0.1.1.0",
    "category": "Productivity",
    "author": "Code Nomi Nomi",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "icon": "/tour_copilote/static/description/icon.svg",
    # tour_dashboard : la page Consommation vit sous le menu Pilotage.
    "depends": ["web", "base_setup", "project", "suivi_apps", "tour_dashboard"],
    "data": [
        "security/ir.model.access.csv",
        "security/copilote_regles.xml",
        "views/res_config_settings_views.xml",
        "views/copilote_usage_views.xml",
        "views/recherche.xml",
        "views/mon_ia_page.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "tour_copilote/static/src/copilote/copilote.js",
            "tour_copilote/static/src/copilote/code-render.js",
            "tour_copilote/static/src/copilote/copilote.xml",
            "tour_copilote/static/src/copilote/copilote.scss",
        ],
    },
    "installable": True,
}
