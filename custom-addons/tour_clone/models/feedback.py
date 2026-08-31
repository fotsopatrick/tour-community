# -*- coding: utf-8 -*-
"""Les réponses de Patrick aux pré-décisions du clone (31/07).

Patrick : « corriger les décisions du clone pour lui dire si je suis
d'accord, pas d'accord et pourquoi — avec ça il pourra se rapprocher de moi,
de ma façon de penser ».

La veille du clone rend des propositions ; la relève les découpe ici, UNE
ligne par proposition. Patrick tranche chacune (d'accord / pas d'accord +
pourquoi). Le cron d'apprentissage relit ces lignes appariées : c'est la
matière la plus riche qui existe pour rapprocher le clone de son patron.

Une ligne non tranchée n'apprend rien : elle reste une proposition. C'est
l'acte de Patrick (verdict + pourquoi) qui devient matière.
"""
from odoo import fields, models


class CloneFeedback(models.Model):
    _name = "clone.feedback"
    _description = "Réponse de Patrick à une pré-décision du clone"
    _order = "decision_id, numero, id"

    decision_id = fields.Many2one(
        "decision.fiche", ondelete="cascade", required=True,
        index=True, string="Fiche Décisions du clone")
    mission_id = fields.Many2one(
        "atelier.mission", "Mission d'origine", readonly=True)
    numero = fields.Integer("N°", readonly=True)
    proposition = fields.Text("Ce que le clone a proposé", readonly=True)
    justif = fields.Text("Sa justification", readonly=True)
    verdict = fields.Selection(
        [("ok", "D'accord"), ("ko", "Pas d'accord")],
        "Ton verdict", help="Es-tu d'accord avec cette pré-décision ?")
    pourquoi = fields.Text(
        "Pourquoi (ta correction)",
        help="Ce qui va ou ne va pas, dans tes mots. C'est ce que le clone "
             "doit apprendre.")
    repondu_le = fields.Datetime(
        "Répondu le", readonly=True,
        help="Pris en compte par le cron d'apprentissage quand renseigné.")

    def write(self, vals):
        """Poser « répondu le » dès que Patrick tranche la ligne.

        Une ligne devient matière d'apprentissage au moment où le verdict est
        posé. Si le verdict est retiré, elle redevient une simple proposition.
        """
        if "verdict" in vals:
            verdict = vals.get("verdict") or self.verdict
            vals["repondu_le"] = (fields.Datetime.now()
                                  if verdict else False)
        return super().write(vals)
