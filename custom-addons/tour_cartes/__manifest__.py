# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Tour de contrôle — Cartes par zones",
    "summary": "La cartographie de la tour en cartes par zone (style Packet Tracer), dans le cockpit.",
    "description": """
La tour en cartes (06/08, Patrick : « il nous faudrait plusieurs cartes
comme celle de packet tracer », « par zone par groupe »).

Six zones, chacune sa carte : les webapps, l'equipe, les serveurs, les
conteneurs, les volumes, les outils. Les donnees sont RELEVEES par
`deploy/carte-zones.sh` (docker, psql, Caddyfile, menu Actions, equipe,
crons) et posees dans l'atelier (`/mnt/atelier/cartes.json`). Le controleur
lit ce fichier — jamais un relevé fait à la volée : ce qu'on ne peut pas
lire n'apparait pas.

La page porte le schema (types de noeuds et de liens), les conventions
d'ids et les 4 questions — pour qu'un agent aussi sache l'utiliser.

Privé : `auth="user"`, réservé au groupe `base.group_system` (comme le
reste du cockpit). Un compte ordinaire est redirigé vers l'accueil.
""",
    "version": "18.0.1.0.0",
    "author": "Patrick Fotso (Code Nomi Nomi)",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["base", "tour_cockpit"],
    "data": [
        "views/cartes_templates.xml",
    ],
    "installable": True,
    "application": False,
}
