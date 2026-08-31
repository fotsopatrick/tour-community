# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Tour — Entretiens",
    "version": "18.0.1.0.0",
    "summary": "Coller une offre d'emploi, recevoir sa préparation, garder "
               "la trace de ce qui a vraiment été demandé.",
    # Le principe vient de QuestForge (projet perso de Patrick) : une offre
    # devient une préparation structurée. On reprend l'idée, pas le code.
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["mail", "tour_atelier"],
    "data": [
        "security/ir.model.access.csv",
        "views/entretien_views.xml",
    ],
    "installable": True,
    "application": True,
}
