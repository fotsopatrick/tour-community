# -*- coding: utf-8 -*-
"""La langue des actualités, choisie par chacun.

Demandé le 28/07 : « l'user doit pouvoir choisir la langue de l'actualité
dans un dropdown à côté d'Actualités ». Le choix vit sur l'utilisateur —
pas en paramètre global : sur une même tour, l'un lit en français,
l'autre en anglais.
"""
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    actus_langue = fields.Selection(
        [("toutes", "Toutes les langues"), ("fr", "Français"),
         ("en", "English"), ("es", "Español")],
        "Langue des actus", default="toutes")

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["actus_langue"]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        # Sans cette ligne, seul un administrateur pourrait changer la
        # préférence — un choix personnel doit se changer soi-même.
        return super().SELF_WRITEABLE_FIELDS + ["actus_langue"]
