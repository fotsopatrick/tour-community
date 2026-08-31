# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Progression — jalons et série",
    "version": "18.0.1.0.0",
    "summary": "Voir ce qu'on a franchi, et ce qui vient après",
    "description": """
Progression
===========

La tour sait faire trente-quatre choses. On en utilise cinq, parce qu'on ne
sait pas que les autres existent — et un outil qu'on n'explore pas se réduit
à ce qu'on en a compris le premier jour.

Cette page montre des **jalons** : des choses concrètes qu'on a franchies, et
celles qui viennent après. Elle sert à découvrir ce qu'on a sous la main, pas
à féliciter.

**Un jalon se gagne, il ne se coche pas.** Chacun se lit dans les données de la
tour — un site en ligne, un paiement reçu, un guide écrit. Une case à cocher
serait un mensonge qu'on se raconte à soi-même ; ici, si le jalon est franchi,
c'est que la chose existe vraiment.

**Il n'y a ni points, ni badges, ni classement.** Récompenser l'activité pousse
à produire de l'activité — des tâches créées pour créer des tâches. Ce qu'on
veut, c'est qu'un jour on découvre qu'on peut mettre un site en ligne depuis la
tour, pas qu'on batte un score.
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["base", "web", "tour_dashboard"],
    "data": [
        "security/ir.model.access.csv",
        "data/jalons.xml",
        "views/jalon_views.xml",
        "views/page_progression.xml",
    ],
    "installable": True,
    "application": False,
}
