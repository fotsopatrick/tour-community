# -*- coding: utf-8 -*-
"""Une heure sur les rappels.

`mail.activity` n'a qu'une date : pas d'heure, pas de créneau. Un rappel
« Dentiste » qui tombe aujourd'hui sans dire *quand* oblige à ouvrir la fiche,
et souvent l'information n'y est pas non plus — elle est dans le titre, en
texte libre, écrite différemment à chaque fois.

D'où un champ texte plutôt qu'une heure stricte. Beaucoup de rendez-vous ne
SONT pas à une heure précise : « vers 18 h », « après le travail », « en fin
de matinée ». Forcer 18:00 sur un « vers 18 h » fabriquerait une fausse
précision — on arriverait à l'heure à un rendez-vous qui n'en avait pas, ou on
raterait celui qui commençait à 17h45.

La case « approximatif » n'est donc pas un détail de confort : c'est ce qui
distingue « sois là à 18 h » de « c'est autour de 18 h, prends de la marge ».
"""
from odoo import fields, models


class MailActivity(models.Model):
    _inherit = "mail.activity"

    heure_texte = fields.Char(
        "Heure",
        help="Libre : « 18 h », « vers 18 h », « après le travail ». "
             "Ce qui compte est que l'information s'affiche, pas qu'elle soit "
             "au format d'une horloge.")
    heure_approx = fields.Boolean(
        "Heure approximative",
        help="Cochée, l'accueil écrit « environ » devant l'heure. Une heure "
             "approximative présentée comme exacte est pire qu'aucune heure.")

    def _quand(self):
        """Ce qu'on affiche à côté de la date, ou une chaîne vide."""
        self.ensure_one()
        if not self.heure_texte:
            return ""
        return ("environ %s" % self.heure_texte) if self.heure_approx else self.heure_texte
