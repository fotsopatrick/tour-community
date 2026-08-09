# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Mon CV",
    "version": "18.0.1.0.0",
    "summary": "Un CV en page web qui se met à jour tout seul",
    "description": """
Mon CV
======

Un CV est un fichier qui vieillit. On l'écrit une fois, on l'envoie, et six
mois plus tard il ne dit plus ce qu'on sait faire — mais on l'envoie quand
même, parce que le rouvrir coûte une soirée.

Ici il vit dans la tour, à côté du reste. On ajoute une réalisation le jour où
elle est finie, et la page publique est à jour dans la seconde. **Le CV cesse
d'être un travail pour devenir un affichage.**

Deux décisions de conception :

- **Une page, pas un PDF.** Le web permet de replier le détail : le lecteur
  choisit d'en lire plus. Un PDF impose une longueur, donc il oblige à couper
  ce qui explique le raisonnement — et c'est précisément ce qui distingue
  quelqu'un qui a construit de quelqu'un qui a suivi un tutoriel.
- **Publié par lien, jamais indexé par défaut.** Un CV trouvable par recherche
  reste consultable des années, y compris par un employeur qu'on n'a pas
  choisi.

Non publié, la page rend 404 — même avec la bonne adresse. On ne dit jamais
qu'un CV existe mais qu'il est caché.
    """,
    "author": "Code Nomi Nomi",
    "website": "https://matourdecontrole.fr",
    "category": "Tour de contrôle",
    "license": "AGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/cv_views.xml",
    ],
    "installable": True,
    "application": True,
}
