# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Retours des testeurs — les bugs, avec leurs preuves",
    "version": "18.0.1.0.0",
    "summary": "Un endroit unique pour déposer un bug, sa capture d'écran et ce qu'il faut faire pour le revoir",
    "description": """
Retours des testeurs
====================

Un bug raconté dans un message se perd. Un bug déposé ici garde sa
capture d'écran, ce qu'on faisait au moment où c'est arrivé, et ce qu'on
en a fait — corrigé, refusé, ou pas encore.

Trois champs comptent plus que les autres, et l'écran le dit :
**ce que tu faisais**, **ce que tu attendais**, **ce qui est arrivé**.
Sans ces trois-là, personne ne peut reproduire — et un bug qu'on ne
reproduit pas ne se corrige pas, il se discute.

Chacun voit ses propres retours ; l'administrateur les voit tous. Les
captures se glissent dans la conversation de la fiche, autant qu'on veut.
""",
    "author": "Code Nomi Nomi",
    "license": "AGPL-3",
    "category": "Productivity",
    "depends": ["mail", "project"],
    "data": [
        "security/ir.model.access.csv",
        "security/regles.xml",
        "views/retour_views.xml",
    ],
    "installable": True,
    "application": False,
}
