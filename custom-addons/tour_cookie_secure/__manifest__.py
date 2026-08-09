# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Tour — cookie de session Secure",
    "version": "18.0.1.0.0",
    "summary": "Force l'attribut Secure sur le cookie de session (derriere Caddy HTTPS)",
    "description": """
Force Secure sur le cookie session_id
=====================================

Le build Odoo 18.0 pose le cookie de session avec HttpOnly mais sans Secure,
meme derriere un proxy HTTPS (constate le 06/08/2026 : le cookie repondu par
tour.matourdecontrole.fr et demo.matourdecontrole.fr n'a pas l'attribut
Secure). Un petit patch au chargement du module ajoute secure=True sur le
cookie session_id, rien d'autre.
""",
    "author": "Code Nomi Nomi",
    "license": "AGPL-3",
    "category": "Technical",
    "depends": ["base"],
    "installable": True,
    "application": False,
}
