# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Tour — Décisions",
    "version": "18.0.1.2.1",
    "summary": "La deuxième porte : tout ce qui attend ton feu vert, en un "
               "écran — approuver, ou rejeter avec un mot qui relance l'agent.",
    # Regle de Patrick, 28/07 : « tout ca doit etre dans le module Decisions,
    # faire en console c'est chiant » — pour lui comme pour les utilisateurs.
    "license": "OPL-1",
    "author": "Code Nomi Nomi",
    "category": "Productivity",
    "depends": ["mail", "project"],
    "data": [
        "security/ir.model.access.csv",
        "security/decision_rules.xml",
        "views/decision_views.xml",
        "views/page_decisions.xml",
    ],
    "installable": True,
    "application": True,
}
