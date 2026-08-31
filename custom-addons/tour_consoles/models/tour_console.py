# -*- coding: utf-8 -*-
"""Les tableaux de bord externes, rangés.

Une infrastructure moderne se pilote depuis huit consoles différentes. Quand il
faut faire une manipulation soi-même, le temps perdu n'est pas dans la manip :
il est à retrouver l'adresse et à se rappeler de quel compte il s'agit.
"""
from odoo import fields, models

CATEGORIES = [
    ("hebergement", "Hébergement et domaines"),
    ("paiement", "Paiement et facturation"),
    ("donnees", "Bases de données"),
    ("ia", "Intelligence artificielle"),
    ("boutique", "Boutiques et distribution"),
    ("vocal", "Assistants vocaux"),
    ("code", "Code et dépôts"),
    ("autre", "Autre"),
]


class TourConsole(models.Model):
    _name = "tour.console"
    _description = "Console externe"
    _order = "categorie, sequence, name"

    name = fields.Char("Service", required=True)
    url = fields.Char("Adresse", required=True)
    categorie = fields.Selection(CATEGORIES, string="Catégorie",
                                 default="autre", required=True, index=True)
    a_quoi = fields.Char("Sert à", help="Ce qu'on vient y faire, en quelques mots.")
    compte = fields.Char("Compte", help="Sous quelle identité on s'y connecte.")
    secret_id = fields.Many2one(
        "vault.secret", string="Identifiants (Coffre)",
        help="Fiche du Coffre contenant le mot de passe, si elle existe.")
    notes = fields.Text("À savoir")
    sequence = fields.Integer("Ordre", default=10)
    perso = fields.Boolean(
        "Console personnelle", default=False,
        help="Cochée : visible uniquement par la personne qui l'a créée.")
    user_id = fields.Many2one("res.users", string="Créée par",
                              default=lambda self: self.env.user, ondelete="cascade")

    def action_ouvrir(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": self.url, "target": "new"}
