# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Conteneurs",
    "version": "18.0.1.0.0",
    "summary": "Piloter les conteneurs du serveur depuis la tour (démarrer/arrêter)",
    "description": """
Conteneurs
==========

Le serveur est limité (7,6 Go de RAM) et certaines choses peuvent être
arrêtées sans rien casser : la démo, le bac à sable, des services légers.
Cette page les montre avec leur RAM réelle, et permet de les démarrer ou les
arrêter d'un clic.

La sécurité est à deux étages :
- le service hôte (`pilote-conteneurs`, port 3212) exige un jeton
  (`~/atelier/.conteneurs-token`) ;
- les conteneurs critiques (tour-odoo-1, tour-db-1, tour-caddy-1) sont
  PROTÉGÉS : le service refuse de les arrêter.

Administrateur seulement : arrêter un conteneur engage l'état du serveur.
    """,
    "author": "Code Nomi Nomi",
    "website": "https://matourdecontrole.fr",
    "category": "Tour de contrôle",
    "license": "OPL-1",
    "depends": ["base"],
    "data": [
        "views/conteneurs_templates.xml",
    ],
    "installable": True,
    "application": False,
}
