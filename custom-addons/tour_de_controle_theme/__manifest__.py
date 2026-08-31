# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Tour de contrôle — Thème",
    "version": "18.0.2.3.0",
    "summary": "Thème sombre DaisyUI (palette alder), navigation latérale gauche, "
    "login custom, débranding complet.",
    "license": "AGPL-3",  # aligné sur web_dark_mode (AGPL), dépendance directe
    "depends": [
        # mail + auth_signup : indispensables pour surcharger les gabarits de
        # courriel (data/mail_debrand.xml). Sans la dependance, l'ordre de
        # chargement n'est pas garanti et les xpath echouent a l'installation.
        "mail",
        "auth_signup",
        "web_responsive",  # OCA/web : menu apps plein écran + responsive
        "web_dark_mode",  # OCA/web : bundles dark + switch utilisateur
    ],
    "data": [
        "views/webclient_templates.xml",
        # L'ecran Apparence : le reglage du theme, sorti des Preferences pour
        # devenir une application avec sa tuile. Un reglage qu'on ne trouve pas
        # est un reglage qui n'existe pas.
        "views/apparence.xml",
        # La page 404 design maison (remplace le template Odoo).
        "views/page_404.xml",
        "data/res_users_dark.xml",
        "data/debrand_parameters.xml",
        # Retire les 21 publicites de l'edition payante, et coupe les
        # taches planifiees qui appellent les serveurs d'Odoo. Rejoue a
        # chaque mise a jour : Odoo repositionne `to_buy` tout seul.
        "data/masquer_entreprise.xml",
        "data/mail_debrand.xml",
    ],
    "assets": {
        # Marque (clair + inclus dans les deux schémas)
        "web._assets_primary_variables": [
            "tour_de_controle_theme/static/src/scss/primary_variables.scss",
        ],
        # Palette sombre : chargée AVANT celle de web_dark_mode pour la surcharger
        "web.assets_variables_dark": [
            (
                "before",
                "web_dark_mode/static/src/scss/primary_variables.dark.scss",
                "tour_de_controle_theme/static/src/scss/primary_variables.dark.scss",
            ),
        ],
        # Skin backend + sidebar + débranding JS
        "web.assets_backend": [
            "tour_de_controle_theme/static/src/backend/theme.scss",
            "tour_de_controle_theme/static/src/backend/navbar.xml",
            "tour_de_controle_theme/static/src/backend/apps_menu.xml",
            "tour_de_controle_theme/static/src/backend/apps_groupes.js",
            "tour_de_controle_theme/static/src/backend/navbar_patch.js",
            "tour_de_controle_theme/static/src/backend/debrand.js",
        ],
        # Page de connexion
        "web.assets_frontend": [
            "tour_de_controle_theme/static/src/login/login.scss",
        ],
    },
}
