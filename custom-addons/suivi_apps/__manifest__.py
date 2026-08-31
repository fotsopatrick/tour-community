# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Suivi des apps",
    "summary": "Tableau vivant de l'etat des apps perso : en cours, fait, reste a faire, progression",
    "version": "18.0.1.6.0",
    "category": "Productivity",
    "author": "Code Nomi Nomi",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "OPL-1",
    "icon": "/suivi_apps/static/description/icon.svg",
    "depends": ["base", "project", "tour_atelier"],
    "data": [
        "security/ir.model.access.csv",
        "security/apporteur_security.xml",
        "views/app_suivi_views.xml",
        "views/app_capture_views.xml",
        "views/app_offre_views.xml",
        "views/app_apporteur_views.xml",
        "views/app_journal_views.xml",
        "views/app_liaison_views.xml",
        "data/app_suivi_data.xml",
    ],
    "installable": True,
    "application": True,
}
