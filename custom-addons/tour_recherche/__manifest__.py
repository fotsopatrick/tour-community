# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Où chercher",
    "version": "18.0.1.0.0",
    "summary": "La liste des endroits où la tour a le droit de chercher, et qui a le droit d'y aller",
    "description": """
Où chercher
===========

Quand on demande à la tour « retrouve mes candidatures », il faut d'abord
répondre à une question bête : **chercher où ?** Aujourd'hui la réponse vit
dans la tête de celui qui demande. Elle se perd, et chaque agent invente son
propre chemin.

Ici, les endroits sont écrits. Une boîte mail, un dossier du disque, un site,
un service qui tourne sur le serveur : chacun devient une fiche. On coche, on
décoche. La recherche ne va que là où c'est coché.

Le deuxième problème est plus sérieux : **tout le monde n'a pas à fouiller
partout.** Une boîte mail personnelle n'est pas un dossier de démonstration.
Chaque endroit porte donc un cercle :

- **Cercle 1 — le cercle fermé** : Patrick, Raphaël, opencode.
- **Cercle 2 — les agents** : l'équipage, l'atelier.
- **Cercle 3 — réservé** : gardé libre, rien dedans pour l'instant.
- **Cercle 4 — les invités** : ce que voit quelqu'un en démonstration.

Un membre d'un cercle voit son cercle **et tous ceux d'après**. Un agent
(cercle 2) ne verra jamais un endroit marqué cercle 1. Un invité (cercle 4)
ne voit que le cercle 4.

La règle n'est pas écrite dans un document que personne ne lit : elle est
dans le code. `sources_pour()` refuse, et chaque passage laisse une trace
dans le journal — on peut donc vérifier qu'elle a vraiment refusé.
    """,
    "author": "Code Nomi Nomi",
    "website": "https://matourdecontrole.fr",
    "category": "Tour de contrôle",
    "license": "OPL-1",
    "depends": ["base", "mail"],
    "data": [
        "security/recherche_groups.xml",
        "security/ir.model.access.csv",
        "security/recherche_rules.xml",
        "views/recherche_views.xml",
        "data/recherche_data.xml",
    ],
    "installable": True,
    "application": True,
}
