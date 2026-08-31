# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Tour de contrôle — Rappels d'abonnements",
    "summary": "Un rappel par mail pour ne pas oublier ses abonnements (Manning, etc.)",
    "version": "18.0.1.0.0",
    "description": """
Rappels d'abonnements
=====================

Patrick prend des abonnements (Manning, etc.) et risque de les oublier.
Chaque abonnement devient une fiche ; la tour envoie un courriel de rappel
un peu avant la fin (par défaut 4 jours), puis, si on n'a rien décidé,
relance chaque semaine.

Trois garde-fous :
- aucun courriel ne part sans adresse de rappel (`email_rappel`) ;
- un abonnement résilié ne rappelle plus ;
- un envoi qui échoue ne bloque pas les autres, il est loggé et repris.

Le rappel n'invente jamais ce qu'on attend : il dit ce qu'on a noté, et il
rappelle seulement ce qui court encore.
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Tour de contrôle",
    "depends": ["mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/abonnement_views.xml",
        "data/abonnements_data.xml",
    ],
    "installable": True,
    "application": False,
}
