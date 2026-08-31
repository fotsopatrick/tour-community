# -*- coding: utf-8 -*-
"""Les théories — ce qu'on croit, ce que ça a donné (03/08, Patrick).

Une théorie est une hypothèse étiquetée comme telle : on ne la présente jamais
comme un fait. Chaque fiche suit la vie de l'idée :
  - statut : théorie → en cours → validée / réfutée ;
  - ce qu'elle a DONNÉ (le résultat réel, mesuré) ;
  - les ressources de Braignak qui l'étayent (études, observations).

Règle : une théorie validée s'appuie sur des preuves réelles (« écrit ≠
posé »). Une théorie sans preuve reste une théorie.
"""
from odoo import api, fields, models

STATUTS = [
    ("theorie", "Théorie"),
    ("en_cours", "En cours de vérification"),
    ("validee", "Validée"),
    ("refutee", "Réfutée"),
]


class TheorieFiche(models.Model):
    _name = "theorie.fiche"
    _description = "Une théorie et ce qu'elle a donné"
    _order = "cree_le desc, id"

    name = fields.Char("La théorie", required=True)
    enonce = fields.Text("Énoncé")
    statut = fields.Selection(STATUTS, "Statut", default="theorie", required=True)
    cree_le = fields.Datetime("Posée le", default=fields.Datetime.now)

    donne = fields.Text(
        "Ce que la théorie a donné",
        help="Le résultat RÉEL, mesuré : ce qu'elle a produit, ou rien.")
    preuve = fields.Text(
        "Preuve",
        help="Ce qui la valide ou la réfute. Une théorie validée sans preuve "
             "n'est pas validée.")

    # Les ressources de Braignak : études, observations (03/08).
    etude_ids = fields.Many2many(
        "braignak.etude", string="Ressources de Braignak",
        help="Les études de Braignak qui étayent ou testent cette théorie.")
    nb_etudes = fields.Integer("Études liées", compute="_compter_etudes")

    @api.depends("etude_ids")
    def _compter_etudes(self):
        for r in self:
            r.nb_etudes = len(r.etude_ids)
