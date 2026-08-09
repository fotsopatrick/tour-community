# -*- coding: utf-8 -*-
"""Rappels récurrents.

Choix d'architecture : on ne réinvente pas un système de notification. Odoo a
déjà les **activités** (`mail.activity`) — l'horloge en haut à droite, la liste
« À faire », les relances par mail, le compteur en retard. Tout le monde qui a
touché à un Odoo sait s'en servir.

Ce module n'ajoute donc que ce qui manque vraiment : la **récurrence**. Une
fiche décrit quoi rappeler et à quel rythme ; un cron quotidien dépose une vraie
activité Odoo à l'échéance, puis reporte la fiche au tour suivant.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

PERIODES = {
    "quotidien": relativedelta(days=1),
    "hebdomadaire": relativedelta(weeks=1),
    "mensuel": relativedelta(months=1),
    "trimestriel": relativedelta(months=3),
    "semestriel": relativedelta(months=6),
    "annuel": relativedelta(years=1),
}


class TourRappel(models.Model):
    _name = "tour.rappel"
    _description = "Rappel récurrent"
    # mail.activity notifie le destinataire via message_notify() : le modèle
    # porteur doit donc avoir le fil de discussion et le mixin d'activités.
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "prochaine_echeance, name"

    name = fields.Char("Rappel", required=True,
                       help="Ce qui apparaîtra dans la liste des choses à faire.")
    note = fields.Text("Détail", help="Le mode d'emploi, si le titre ne suffit pas.")
    user_id = fields.Many2one(
        "res.users", string="Pour qui", required=True,
        default=lambda self: self.env.user, ondelete="cascade")
    periodicite = fields.Selection(
        [(k, k.capitalize()) for k in PERIODES],
        string="Tous les", required=True, default="mensuel")
    prochaine_echeance = fields.Date(
        "Prochaine fois", required=True, default=fields.Date.context_today)
    urgent = fields.Boolean(
        "Urgent", help="Le rappel est préfixé « URGENT » et daté du jour même.")
    actif = fields.Boolean("Actif", default=True)
    derniere_generation = fields.Date("Dernier rappel posé", readonly=True)
    nb_poses = fields.Integer("Rappels posés", readonly=True, default=0)

    # ------------------------------------------------------------------
    @api.model
    def _cron_poser_rappels(self):
        """Dépose une activité Odoo pour chaque rappel arrivé à échéance."""
        aujourdhui = fields.Date.context_today(self)
        dus = self.sudo().search([
            ("actif", "=", True),
            ("prochaine_echeance", "<=", aujourdhui),
        ])
        for rappel in dus:
            rappel._poser_activite()

    def _poser_activite(self):
        self.ensure_one()
        modele = self.env["ir.model"]._get_id("tour.rappel")
        deja = self.env["mail.activity"].sudo().search_count([
            ("res_model_id", "=", modele),
            ("res_id", "=", self.id),
            ("user_id", "=", self.user_id.id),
        ])
        # Un rappel non traité ne s'empile pas : inutile d'avoir douze fois
        # « récupérer la sauvegarde » dans la liste.
        if not deja:
            titre = _("URGENT — %s", self.name) if self.urgent else self.name
            self.env["mail.activity"].sudo().create({
                "res_model_id": modele,
                "res_id": self.id,
                "activity_type_id": self.env.ref("mail.mail_activity_data_todo").id,
                "summary": titre[:200],
                "note": self.note or "",
                "date_deadline": self.prochaine_echeance,
                "user_id": self.user_id.id,
            })
            self.sudo().nb_poses += 1

        suivante = self.prochaine_echeance + PERIODES[self.periodicite]
        # Si la tour a dormi plusieurs cycles, on rattrape jusqu'à aujourd'hui
        # sans poser un rappel par cycle manqué.
        aujourdhui = fields.Date.context_today(self)
        while suivante <= aujourdhui:
            suivante += PERIODES[self.periodicite]
        self.sudo().write({
            "prochaine_echeance": suivante,
            "derniere_generation": aujourdhui,
        })

    def action_poser_maintenant(self):
        """Bouton de test : pose l'activité tout de suite."""
        for rappel in self:
            rappel._poser_activite()
        return True
