# -*- coding: utf-8 -*-
import secrets

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    alexa_token = fields.Char(
        "Jeton secret Alexa",
        config_parameter="tour_alexa.token",
        help="Colle ce jeton dans l'URL de l'endpoint de la skill : "
             "https://ton-domaine/tour_alexa/skill?token=LE_JETON",
    )
    alexa_skill_id = fields.Char(
        "ID de la skill (optionnel)",
        config_parameter="tour_alexa.skill_id",
        help="amzn1.ask.skill.xxx — si renseigné, seules les requêtes de "
             "cette skill sont acceptées (défense en plus du jeton).",
    )

    @api.model
    def action_generer_token_alexa(self):
        token = secrets.token_urlsafe(32)
        self.env["ir.config_parameter"].sudo().set_param("tour_alexa.token", token)
        return token
