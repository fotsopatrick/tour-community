# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettingsExtension(models.TransientModel):
    _inherit = "res.config.settings"

    tour_extension_mdp = fields.Char(
        "Mot de passe de la page Extension",
        config_parameter="tour_extension.mdp",
        help="Le mot de passe pour accéder à /tour/extension (télécharger "
             "l'extension navigateur). Par défaut : 3173.")
