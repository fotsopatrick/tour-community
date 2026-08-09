# -*- coding: utf-8 -*-
from odoo import fields, models


class ActusArticle(models.Model):
    _name = "actus.article"
    _description = "Article d'actualité"
    _order = "date_pub desc"

    name = fields.Char("Titre", required=True)
    lien = fields.Char("Lien", required=True)
    resume = fields.Char("Résumé")
    image_url = fields.Char("Image")
    date_pub = fields.Datetime("Publié le")
    flux_id = fields.Many2one("actus.flux", string="Source", required=True, ondelete="cascade")
    categorie = fields.Char(related="flux_id.categorie", store=True)
    langue = fields.Selection(related="flux_id.langue", store=True)

    _sql_constraints = [
        ("lien_unique", "unique(lien)", "Cet article est déjà dans le fil."),
    ]
