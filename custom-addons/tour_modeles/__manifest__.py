# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Recettes de produits",
    "version": "18.0.1.0.0",
    "summary": "Chaque produit livré laisse de quoi le reproduire",
    "description": """
Recettes de produits
====================

Une application est construite en une nuit, à partir d'une consigne, d'allers-
retours et de corrections. Trois mois plus tard on veut la même pour un autre
client — et on ne sait plus **ce qu'on avait demandé exactement**. On
recommence, on retombe sur les mêmes pièges, et on paie deux fois le même
apprentissage.

Chaque produit livré par l'atelier laisse donc sa **recette** : le texte à
donner tel quel pour le reproduire.

**La recette n'est pas la consigne de départ.** C'est la consigne PLUS ce qu'on
a appris en la réalisant. Une recette qui ne contient que la demande initiale
reproduit aussi les erreurs.

**C'est automatique**, sinon ce n'est pas fait : une recette qu'il faut penser
à écrire ne s'écrit jamais.
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["base", "tour_dashboard", "tour_atelier"],
    "data": [
        "security/ir.model.access.csv",
        "views/modele_views.xml",
        "views/page_apps.xml",
    ],
    "installable": True,
    "application": False,
}
