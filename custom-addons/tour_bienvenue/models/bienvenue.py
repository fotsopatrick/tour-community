# -*- coding: utf-8 -*-
"""Retenir qui a déjà vu la page de bienvenue.

Un seul champ, sur l'utilisateur. Pas de modèle dédié : ce qu'on veut savoir
tient dans un oui/non par personne, et un modèle pour ça serait une table à
maintenir pour rien.
"""

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    bienvenue_vue = fields.Boolean(
        "A vu la page de bienvenue", default=False, copy=False,
        help="Passe à vrai à la première visite. La page ne revient plus — "
             "une page d'accueil qui s'affiche à chaque connexion devient un "
             "obstacle qu'on apprend à fermer sans lire.")
