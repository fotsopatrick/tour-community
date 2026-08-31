# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Mise en production par Décisions",
    "version": "18.0.1.0.0",
    "summary": "Valider un module en test, puis le déployer en prod d'un clic dans Décisions",
    "description": """
Le circuit test -> prod, gardé par une décision
===============================================

Patrick veut travailler en test (tour_test), puis déployer en production
UNIQUEMENT par son approbation dans le module Décisions. Ce module construit ce
chaînon, sur le même patron que la vitrine :

1. On valide un module sur tour_test (à l'écran).
2. On crée une « demande de mise en prod » (le nom du module).
3. Elle apparaît dans Décisions. Patrick approuve.
4. L'approbation dépose un ORDRE (un fichier, jamais une commande) que le cron
   de l'hôte ramasse : il fait `-u <module>` sur la base `tour` et redémarre.

La tour ne lance aucune commande elle-même : elle dépose un nom, l'hôte agit.
C'est la même règle de sécurité que l'atelier et la vitrine.
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["base", "mail", "tour_decisions", "tour_dashboard"],
    "data": [
        "security/ir.model.access.csv",
        "views/promotion_views.xml",
    ],
    "installable": True,
    "application": False,
}
