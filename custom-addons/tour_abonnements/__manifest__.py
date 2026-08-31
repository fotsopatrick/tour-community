# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
{
    "name": "Abonnements",
    "version": "18.0.1.0.2",
    "summary": "Vendre un abonnement mensuel — la brique que Community n'a pas",
    "description": """
Abonnements
===========

Odoo Enterprise vend `sale_subscription`. En Community il n'y a rien : pas de
récurrence, pas de relance, pas de carte qui expire. Trois offres mensuelles
n'ont donc aucun moteur.

Le choix qui commande tout : **Stripe est la source de vérité de la
facturation, la tour est la source de vérité du contrat.** On ne réimplémente
pas les relances ni le prorata — chaque bug s'y paie en argent qui ne rentre
pas, ou pire, qui rentre deux fois.

La tour n'appelle presque jamais Stripe : elle écoute un webhook signé. Un
système qui interroge manque l'événement qui compte ; un système qui écoute le
reçoit une fois, avec sa signature.

Aucun numéro de carte ne touche jamais la tour.
    """,
    "author": "Code Nomi Nomi",
    "website": "https://matourdecontrole.fr",
    "category": "Tour de contrôle",
    "license": "OPL-1",
    "depends": ["base", "mail", "account", "payment_stripe"],
    "data": [
        "security/ir.model.access.csv",
        "data/abonnement_data.xml",
        "views/abonnement_views.xml",
    ],
    "installable": True,
    "application": True,
}
