# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Tess — les chiffres",
    "version": "18.0.1.0.0",
    "summary": "Ce que ça coûte, ce que ça rapporte, et la date où ça coince",
    "description": """
Tess — analyste produit, contrôle de gestion, business analyst
==============================================================

Trois métiers, un seul agent, parce qu'ils répondent à la même question sous
trois angles : **est-ce que ça tient ?**

- **Contrôle de gestion** : ce qui sort (serveur, IA, frais de paiement).
- **Analyste produit** : ce qui est utilisé, et par combien de monde.
- **Business analyst** : ce que ça rapporte, la marge, et la DATE où un plafond
  sera atteint au rythme actuel.

Elle ne consomme aucune intelligence artificielle : ce sont des comptages et
des divisions. Un chiffre doit donner le même résultat deux fois de suite.

**Ce qu'elle ne fait pas : décider.** Elle donne le chiffre et l'échéance.
Arrêter une dépense, monter un prix, couper une offre — ce sont des décisions,
et une décision se prend par quelqu'un qui en assume les conséquences.
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["base", "tour_dashboard"],
    "data": [
        "security/ir.model.access.csv",
        "views/releve_views.xml",
        "data/cron.xml",
    ],
    "installable": True,
    "application": False,
}
