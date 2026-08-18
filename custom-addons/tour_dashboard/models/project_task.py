# -*- coding: utf-8 -*-
"""Qui fait quoi.

Le journal mélangeait ce que Claude exécute et ce qui attend une action du
propriétaire. Le préfixe « [PATRICK] » servait de convention provisoire ; ce
champ le remplace et rend le tableau lisible d'un coup d'œil.
"""
from odoo import fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    qui = fields.Selection(
        [("claude", "Claude"), ("proprietaire", "Moi"), ("partage", "À deux")],
        string="Qui fait", index=True,
        help="Claude : je l'exécute. Moi : ça attend une action de ta part "
             "(un mot de passe, un clic dans une console, une décision). "
             "À deux : il faut les deux pour avancer.")
