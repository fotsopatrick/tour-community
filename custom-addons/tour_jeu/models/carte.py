# -*- coding: utf-8 -*-
"""Les cartes du Duel de la Tour.

Chaque joueur peut créer ses cartes ET définir ce qu'elles font (l'effet)
avant le combat. La puissance de départ se base sur le travail réel (les
compétences mesurées) ; la carte qu'on crée peut la reprendre ou la réinventer
— c'est le joueur qui décide, avant de dueler.
"""

from odoo import fields, models


class JeuCarte(models.Model):
    _name = "jeu.carte"
    _description = "Carte du Duel de la Tour"
    _order = "sequence, id"

    name = fields.Char("Nom de la carte", required=True)
    effet = fields.Text(
        "Ce qu'elle fait",
        help="L'effet de la carte, annoncé pendant le duel.")
    attaque = fields.Integer("Attaque", default=10)
    defense = fields.Integer("Défense", default=5)
    sequence = fields.Integer(default=10)
    active = fields.Boolean("Active", default=True)
    user_id = fields.Many2one(
        "res.users", "Joueur", default=lambda self: self.env.user)
