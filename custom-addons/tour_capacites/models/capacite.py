# -*- coding: utf-8 -*-
"""Le degré de pilotage : la part des gestes de la tour que l'on fait en
discutant, sans lire de doc.

Un geste = une chose qu'un utilisateur veut obtenir de la tour (créer une
tâche, construire une app, relancer un invité...). Pour chacun, on note s'il
est « à la parole » :
- un agent le fait si on le lui demande (Chloe, discussion, échange) ;
- ou un circuit/cron automatique s'en charge sans que l'utilisateur lise rien.

Le degré = gestes à la parole / total. Recalculé à chaque lecture : ajouter
un geste, le passer à la parole, changer un agent → le chiffre suit.
"""
from odoo import api, fields, models

CATEGORIES = [
    ("piloter", "Piloter le travail"),
    ("construire", "Construire"),
    ("verifier", "Vérifier"),
    ("communiquer", "Communiquer"),
]


class TourCapacite(models.Model):
    _name = "tour.capacite"
    _description = "Geste de la tour, pilotable à la parole ou manuel"
    _order = "categorie, sequence, id"

    name = fields.Char("Le geste", required=True)
    categorie = fields.Selection(CATEGORIES, "Catégorie", required=True)
    pilote_parole = fields.Boolean(
        "Pilotable à la parole",
        help="On l'obtient en discutant (un agent le fait) ou par un circuit "
             "automatique, sans lire de doc ni cliquer dans les écrans.")
    sequence = fields.Integer(default=10)
    description = fields.Text("Comment ça se pilote")

    @api.model
    def _degre(self):
        """{total, pilote, pct, detail} — recalculé à chaque appel."""
        tous = self.sudo().search([])
        if not tous:
            return {"total": 0, "pilote": 0, "pct": 0, "detail": []}
        pilote = tous.filtered("pilote_parole")
        pct = round(100.0 * len(pilote) / len(tous))
        return {
            "total": len(tous),
            "pilote": len(pilote),
            "pct": pct,
            "detail": [{
                "name": c.name,
                "categorie": c.categorie,
                "pilote": c.pilote_parole,
            } for c in tous],
        }
