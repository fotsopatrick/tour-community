# -*- coding: utf-8 -*-
"""Le journal : qui est passé chercher quoi, où, et ce qu'il a trouvé.

Une garde qui refuse sans laisser de trace ne sert à rien : on ne peut pas
savoir si elle a refusé, ni si elle a seulement été appelée. On croit qu'elle
marche. Ici, chaque fouille — acceptée OU refusée — écrit une ligne. Le
contrôle du module consiste à provoquer un refus et à venir le lire.
"""
from odoo import fields, models

from .source import CERCLES


class RecherchePassage(models.Model):
    _name = "recherche.passage"
    _description = "Un passage dans un endroit"
    _order = "create_date desc, id desc"

    source_id = fields.Many2one(
        "recherche.source", "L'endroit", required=True,
        ondelete="cascade", index=True)
    cercle = fields.Selection(CERCLES, "Cercle du demandeur", required=True)
    qui = fields.Char(
        "Qui a cherché", required=True,
        help="Le nom en clair : Patrick, Raphaël, opencode, Clark…")
    cherche = fields.Char("Ce qu'il cherchait", required=True)
    trouve = fields.Integer("Trouvé", default=0, help="Combien de résultats.")
    refuse = fields.Boolean(
        "Refusé", default=False, index=True,
        help="Coché : la garde a dit non. C'est la ligne qui prouve "
             "qu'elle fonctionne.")
    note = fields.Text("Ce qu'il faut retenir")
