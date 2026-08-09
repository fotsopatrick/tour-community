# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
{
    "name": "Tour — limite de connexions par IP (429)",
    "version": "18.0.1.0.0",
    "summary": "Repond 429 au-dela de 6 tentatives de connexion en 10 minutes par IP",
    "description": """
Limite de tentatives de connexion (429)
=======================================

Le build Odoo 18.0 laisse essayer sans fin. Ce module compte les POST
/web/login par IP et repond HTTP 429 (TooManyRequests) a partir de la
6e tentative dans une fenetre de 10 minutes. Un succes ne change rien :
la fenetre glisse toute seule (les compteurs sont purges chaque jour).

Le blocage se fait AVANT le controle CSRF : une attaque par force brute
n'envoie pas de jeton CSRF, et sans cette position la limite ne verrait
jamais rien (Odoo repond 400 avant d'atteindre l'authentification).

Regle de construction : la limite ne doit JAMAIS casser le login. Si le
comptage echoue (base indisponible, modele absent), la requete passe.
""",
    "author": "Code Nomi Nomi",
    "license": "AGPL-3",
    "category": "Technical",
    "depends": ["base"],
    "data": [
        "data/cron.xml",
    ],
    "installable": True,
    "application": False,
}
