# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Circuits — chaînes d'approbation multi-agents",
    "version": "18.0.1.2.1",
    "summary": "Un moteur de circuits : un objet traverse des portes (agents, Patrick, prod)",
    "description": """
Le moteur de circuits
=====================

Tous les circuits de la tour (promotion, forge, article, revue) ont la même
forme : une chaîne de portes qui finit par Patrick puis la production. Ce module
code le moteur UNE fois ; chaque circuit devient une simple configuration.

- circuit.modele  : le gabarit (nom + portes ordonnées)
- circuit.etape   : une porte (agent qui relit / Patrick qui tranche / prod)
- circuit.instance: un objet qui avance de porte en porte
- circuit.passage : le journal de chaque porte

Réutilise l'atelier (missions de relecture), Décisions (la porte de Patrick) et
tour_promotion (la porte production). Deux circuits livrés en seed : Article et
Revue.
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["base", "mail", "tour_dashboard", "tour_equipage",
                "tour_atelier", "tour_decisions"],
    "data": [
        "security/ir.model.access.csv",
        "views/circuit_views.xml",
        "views/circuit_cockpit_templates.xml",
        "data/circuits_seed.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
