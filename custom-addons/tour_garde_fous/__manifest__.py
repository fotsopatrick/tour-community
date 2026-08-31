# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Garde-fous",
    "version": "18.0.1.0.0",
    "summary": "Le registre des garde-fous de la tour : qui protège quoi, et comment le vérifier",
    "description": """
Garde-fous
==========

Un garde-fou n'est pas une règle qu'on écrit dans un fichier : c'est un
contrôle qui continue de tenir quand personne ne le regarde. Une règle qui se
perd devient un script, et un script qui ne se vérifie pas redevient une
règle.

Ce module est le REGISTRE. Chaque garde-fou de la tour y est recensé avec :
- ce qu'il protège (la crainte qui l'a fait naître),
- où il vit (module, fichier, script),
- comment il s'applique (déterministe, processus, modèle),
- et surtout COMMENT LE VÉRIFIER : un garde-fou qu'on ne sait pas contrôler
  n'est pas un garde-fou, c'est une intention.

Le registre ne remplace rien : il POINTE. Modifier la protection ici ne
change rien au fonctionnement — le vrai garde-fou vit dans le code qu'il
décrit. Ce module est la mémoire, pas la main.
    """,
    "author": "Code Nomi Nomi",
    "website": "https://matourdecontrole.fr",
    "category": "Tour de contrôle",
    "license": "OPL-1",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "data/garde_fou_data.xml",
        "views/garde_fou_views.xml",
    ],
    "installable": True,
    "application": True,
}
