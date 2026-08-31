# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Emil — la cohérence",
    "version": "18.0.1.0.2",
    "summary": "L'écart entre ce qu'on affiche et ce qu'on est",
    "description": """
Emil — la cohérence
===================

La page « équipe » du site public annonçait quatre agents alors qu'il y en
avait six. Ce n'était pas un oubli isolé : **personne ne comparait jamais ce
qu'on montre à ce qu'on a**. Un cahier qui promet trente capacités, une vitrine
qui vend un module désinstallé, un guide qui cite un menu renommé — chacun ment
tout seul, et rien ne le dit.

Le métier d'Emil tient en une phrase : il ne juge ni le fond ni la forme, il
**constate un écart entre deux sources qui devraient dire la même chose**.

Trois refus :

- **Zéro intelligence artificielle.** Ses contrôles comparent des nombres et
  des listes. Un contrôle doit rendre le même verdict deux fois de suite.
- **Il ne corrige jamais le contenu public.** Un agent qui réécrit la vitrine
  tout seul peut y mettre une bêtise que personne n'a relue.
- **Un écart assumé ne revient pas.** Ce qu'on a décidé de garder ainsi ne se
  repropose pas chaque semaine.
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["base", "mail", "tour_dashboard", "tour_equipage", "tour_guides"],
    "data": [
        "security/ir.model.access.csv",
        "views/ecart_views.xml",
    ],
    "installable": True,
    "application": False,
}
