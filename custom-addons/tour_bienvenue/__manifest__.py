# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Première connexion",
    "version": "18.0.1.1.0",
    "summary": "Ce que voit quelqu'un qui ouvre la tour pour la première fois",
    "description": """
Première connexion
==================

Une tour vide, avec trente applications inconnues dans un menu, ne se
« découvre » pas : on la referme. C'est ce qui arrive à un outil qu'on offre à
un proche ou qu'un client vient d'acheter — il se connecte une fois, ne sait
pas par où commencer, et n'y revient pas.

Cette page s'affiche à la toute première connexion. Elle ne fait pas une visite
guidée de trente écrans : elle pose **trois gestes**, ceux qui rendent la tour
utile le premier jour. Le reste s'apprendra quand le besoin viendra.

Elle ne s'affiche qu'**une fois**, et un lien permet de la relire. Une page
d'accueil qui revient à chaque connexion devient un obstacle qu'on apprend à
fermer sans lire.
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["base", "web", "portal", "tour_dashboard"],
    "data": ["views/page_bienvenue.xml"],
    "installable": True,
    "application": False,
}
