# -*- coding: utf-8 -*-
"""L'interrupteur de Braignak, dans les Réglages.

C'est le verrou pratique — celui qu'on coupe depuis un téléphone. Ce n'est pas
celui qui protège d'une attaque : quelqu'un qui tient la base peut le remettre
à « vrai ». Le verrou qui compte est le fichier d'autorisation posé sur la
machine hôte, hors de portée de la tour.
"""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    braignak_actif = fields.Boolean(
        "Braignak en marche",
        config_parameter="tour_braignak.actif",
        help="Décoché : Braignak refuse toute action. C'est l'état par "
             "défaut, et l'état normal tant que la conduite à tenir en cas "
             "d'attaque de la tour n'est pas écrite.")
