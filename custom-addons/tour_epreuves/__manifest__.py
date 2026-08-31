# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Épreuves des agents",
    "version": "18.0.1.0.0",
    "summary": "Savoir qu'un agent a régressé, avant qu'il ne serve",
    "description": """
Épreuves des agents
===================

Un module qui casse lève une erreur. **Un agent qui régresse répond quand
même** — juste moins bien, ou à côté. La panne est silencieuse et polie : on ne
s'en aperçoit qu'en relisant, c'est-à-dire jamais.

Chaque agent a ses épreuves. Elles tournent chaque jour, et **ne préviennent que
sur une régression** — une épreuve qui passait et qui ne passe plus.

On teste la **capacité**, pas la formulation : exiger une réponse identique mot
pour mot condamne l'épreuve à échouer dès la première évolution, et une épreuve
trop stricte finit désactivée.

Chaque épreuve vient d'une panne **réelle** : Lois rendue muette par un jeton
manquant, Chloe qui improvise faute d'outil, Braignak qui échoue sans le dire.
Une épreuve inventée passe toujours et ne prouve rien.
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["base", "tour_dashboard", "tour_equipage", "tour_copilote",
                "tour_decisions"],
    "data": [
        "security/ir.model.access.csv",
        "views/epreuve_views.xml",
        "data/epreuves.xml",
    ],
    "installable": True,
    "application": False,
}
