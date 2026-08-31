# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Mes candidatures",
    "version": "18.0.1.0.0",
    "summary": "Où j'ai postulé, quand, pour combien, et où ça en est",
    "description": """
Mes candidatures
================

On a fouillé douze mois de courriels pour retrouver quatre candidatures. La
fouille a marché — c'est ce qu'elle a montré qui pose problème : **on postule
presque toujours par formulaire.** Le site de l'entreprise, pas un courriel.

Donc la boîte mail ne garde que les accusés de réception. Une candidature
déposée sur un site qui n'en envoie pas **n'existe nulle part**. Pas de trace,
pas de relance, pas de mémoire. On ne retrouve pas ce qui n'a jamais été écrit.

Ici, la trace se prend au moment où l'on postule. Trente secondes, une fois.

Deux choix qui viennent de Patrick :

- **Plusieurs portes, jamais une seule.** Une même entreprise s'aborde en
  salarié, en consulting ou en mission. Le module note la porte prise ; il n'en
  recommande aucune et ne juge jamais une candidature.
- **L'argent d'abord.** Ce qu'on vise et ce qu'ils proposent sont au premier
  plan, avec l'écart entre les deux. Un avancement sans montant ne dit rien.

Le silence est compté, pas jugé : les jours sans réponse se lisent dans les
dates. Une candidature vivante et muette depuis plus de dix jours remonte
toute seule dans « À relancer ».
    """,
    "author": "Code Nomi Nomi",
    "website": "https://matourdecontrole.fr",
    "category": "Tour de contrôle",
    "license": "OPL-1",
    "depends": ["base", "mail", "tour_entretiens", "tour_recherche",
                "tour_vault"],
    "data": [
        "security/ir.model.access.csv",
        "views/candidature_views.xml",
        "data/releve_data.xml",
    ],
    "installable": True,
    "application": True,
}
