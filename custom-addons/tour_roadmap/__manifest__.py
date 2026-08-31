# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Versions",
    "version": "18.0.1.1.0",
    "summary": "Trancher ce qui entre en V2 et ce qui attend, en glissant une carte",
    "description": """
Versions
========

À chaque idée, on débat de savoir si c'est pour la prochaine version ou pour
plus tard. Le débat coûte du temps à chaque fois, il repart de zéro parce que
rien n'est écrit, et il se fait à l'oral — donc l'arbitrage dépend de qui parle
en dernier.

Le partage des rôles est explicite, et c'est lui qui fait marcher la chose :

- **On propose et on argumente.** Chaque fonctionnalité arrive avec une version
  suggérée et une raison écrite. Une proposition sans raison est un avis qu'on
  subit ; avec la raison, elle devient discutable — et souvent on n'a plus
  besoin d'en discuter.
- **On tranche en déplaçant la carte.** Pas en écrivant : en glissant. C'est
  plus rapide que n'importe quel échange, et surtout ça met les colonnes côte à
  côte — on ne juge pas une fonctionnalité dans l'absolu, on la juge à côté des
  autres.
- **La trace reste.** Un déplacement s'inscrit dans le fil de la carte, avec ce
  qui était proposé. Six mois plus tard, « pourquoi c'est en V3 déjà ? » a une
  réponse.

Aucun JavaScript : le glisser-déposer entre colonnes est natif dès qu'on groupe
sur un champ inscriptible. Du JS maison sur un tableau de bord est ce qui casse
en premier à la mise à jour suivante.

Utilisable pour n'importe quel produit, pas seulement pour la tour.
    """,
    "author": "Code Nomi Nomi",
    "website": "https://matourdecontrole.fr",
    "category": "Tour de contrôle",
    "license": "OPL-1",
    "depends": ["base", "mail", "project"],
    "data": [
        "security/ir.model.access.csv",
        "views/roadmap_views.xml",
        "views/version_views.xml",
    ],
    "installable": True,
    "application": True,
}
