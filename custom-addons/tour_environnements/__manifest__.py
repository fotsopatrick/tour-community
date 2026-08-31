# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Environnements — qui a quoi",
    "version": "18.0.1.1.0",
    "summary": "Comparer ce qui tourne en production, en démo et en test",
    "description": """
Environnements — qui a quoi
===========================

Trois copies d'un produit vivent en parallèle : la production, la démo qu'on
montre, la base de test où l'on essaie. Elles divergent forcément — et c'est
justement la divergence qu'on ne voit jamais.

Le jour où ça compte, c'est toujours le même : on teste sur une base qui n'a
pas le module dont on parle, on montre une démo qui n'a plus la fonctionnalité
qu'on vend, ou on déploie en croyant que la test ressemblait à la production.

Cette page répond à une question et une seule : **qu'est-ce qui est présent
ici et absent là ?**

Elle lit les modules réellement installés sur chaque base, en direct. Rien
n'est saisi à la main : une liste tenue à la main ment dès la semaine suivante.
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["tour_dashboard", "base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/environnement_views.xml",
        "views/page_environnements.xml",
    ],
    "installable": True,
    "application": False,
}
