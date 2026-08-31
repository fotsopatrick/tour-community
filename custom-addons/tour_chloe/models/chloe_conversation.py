# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ChloeConversation(models.Model):
    """Une conversation de la webapp Chloe = un onglet.

    Le contexte d'un onglet, c'est la liste des messages {role, content}
    envoyee a executer_chat (le cerveau du copilote). Chaque onglet a la
    sienne : deux onglets ne melangent jamais leur contexte.
    """

    _name = "chloe.conversation"
    _description = "Conversation de la webapp Chloe"
    _order = "write_date desc"

    name = fields.Char("Sujet", required=True, default="Nouvelle conversation")
    user_id = fields.Many2one(
        "res.users", "Propriétaire", required=True, ondelete="cascade",
        default=lambda self: self.env.user, index=True)
    messages = fields.Text("Messages (JSON)", default="[]")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("user_id", self.env.user.id)
            vals.setdefault("messages", "[]")
        return super().create(vals_list)
