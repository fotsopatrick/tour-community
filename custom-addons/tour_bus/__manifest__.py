# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Le bus des agents",
    "version": "18.0.1.2.0",
    "summary": "Un broker Redis pour que les agents se parlent, et le journal de leurs messages",
    "description": """
Le bus des agents.

Un agent qui travaille tout seul rend son rapport ; deux agents qui doivent
se parler n'avaient aucun chemin. Ce module ouvre le chemin : une file de
messages entre agents, portee par un broker Redis (le plus leger qui existe)
et un journal inalterable dans la tour, pour que personne ne s'ecrive dans
le vide.

Le transport est le broker (rapide, Docker). La memoire est la tour (le
journal tour.bus.message, qui ne s'efface pas). L'expediteur ecrit, le
destinataire lit, et Patrick voit tout.

Un agent de la tour appelle _envoyer(...) et le message est trace d'abord
dans le journal, le broker ensuite. Un agent de l'atelier (Claude Code sur
l'hote) appelle envoyer-bus.sh : le message part sur le broker, le cron de
la tour le ramasse dans le journal et previent Patrick. Et Patrick consulte
le journal dans le menu « Bus des agents ».
""",
    "author": "Code Nomi Nomi",
    "license": "OPL-1",
    "category": "Productivity",
    "depends": ["base", "tour_dashboard", "tour_atelier"],
    "data": [
        "security/ir.model.access.csv",
        "views/tour_bus_views.xml",
    ],
    "installable": True,
    "application": True,
}
