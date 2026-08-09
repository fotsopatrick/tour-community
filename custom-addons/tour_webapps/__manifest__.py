# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Les webapps",
    "summary": "Les pages web de la tour, atteignables depuis Mes apps et pas seulement depuis la barre Actions",
    "description": """
Les pages web de la tour vivaient dans une seule porte : la barre « Actions »
du tableau de bord. Il fallait donc deja etre sur le tableau de bord pour
atteindre Duelle, la Zone Detresse, le Journal ou le Pentest — et rien de tout
cela n'existait dans « Mes apps », l'ecran par lequel on entre.

Ce module leur donne une tuile. Une entree = une adresse testee le 06/08/2026 :
aucune n'a ete ajoutee sans avoir repondu.
""",
    "version": "18.0.1.0.0",
    "category": "Productivity",
    "author": "Code Nomi Nomi",
    # Proprietaire : rend applicable une revente a un seul niveau.
    "license": "AGPL-3",
    "icon": "/tour_webapps/static/description/icon.svg",
    "depends": ["base", "web"],
    "data": [
        "data/webapps_data.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
