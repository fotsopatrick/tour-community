from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    # Sombre par défaut : web_dark_mode aligne le cookie color_scheme sur ce
    # champ à chaque requête (ir_http._post_dispatch).
    dark_mode = fields.Boolean(default=True)
