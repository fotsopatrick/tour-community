# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Quoi de neuf — les nouveautés de la tour",
    "version": "18.0.1.0.0",
    "summary": "Chaque nouveauté expliquée simplement, une page qui les garde toutes, un courriel qui prévient",
    "description": """
Quoi de neuf — les nouveautés de la tour
========================================

Une fonctionnalité arrivait, et personne ne le savait : elle vivait dans un
commit et dans la tête de celui qui l'avait faite. Ici, chaque nouveauté a
une fiche : ce qui est arrivé, à quoi ça sert, où cliquer — écrite pour
qu'un enfant de 6 ans comprenne, c'est la règle de la maison.

La page /tour/nouveautes les garde toutes, les plus fraîches en tête. Et
chaque jour, si quelque chose de neuf n'a pas encore été annoncé, un
courriel part vers les utilisateurs qui ont une adresse : les nouveautés
du moment, et le lien vers la page complète.

L'annonce ne tourne que là où on l'a armée (paramètre
tour_nouveautes.annonces_actives) : la tour mère d'abord, les instances
clientes quand leur propriétaire le décide.
""",
    "author": "Code Nomi Nomi",
    "license": "AGPL-3",
    "category": "Productivity",
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/nouveaute_views.xml",
        "views/page_nouveautes.xml",
        "data/cron_data.xml",
    ],
    "installable": True,
    "application": False,
}
