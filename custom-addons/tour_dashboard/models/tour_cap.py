# -*- coding: utf-8 -*-
"""Le cap : un seul objectif à la fois, écrit, et toujours sous les yeux.

Le problème qu'il résout, constaté le 27/07 : la V1 a bougé plusieurs fois
dans la même soirée. Chaque déplacement était justifié pris isolément — et
c'est exactement pour ça qu'on ne les voit pas passer. À la fin, « finir » ne
veut plus rien dire, parce que la ligne d'arrivée avance avec celui qui court.

Deux règles, et elles sont dans le code, pas dans les bonnes intentions :

**Un seul cap actif.** Pas deux, pas trois « priorités ». Activer un cap
désactive l'autre, et c'est visible : on ne peut plus se raconter qu'on mène
deux choses de front.

**Un critère de fin BINAIRE, écrit d'avance.** Pas « quand ce sera bien »,
mais « quand le paiement à 1 € aboutit à une connexion ». Un critère qu'on
peut interpréter est un critère qu'on interprétera — dans le sens qui
arrange, et de bonne foi. Le champ est obligatoire pour cette raison.

Ce que ce modèle ne fait PAS : suivre l'avancement en pourcentage. Un
pourcentage se négocie ; un critère binaire se constate.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TourCap(models.Model):
    _name = "tour.cap"
    _description = "Le cap en cours"
    _inherit = ["mail.thread"]
    _order = "actif desc, date_debut desc"

    name = fields.Char("Le cap, en une phrase", required=True, tracking=True)
    critere = fields.Text(
        "On saura que c'est fini quand…", required=True, tracking=True,
        help="Un fait observable, pas une impression. Si deux personnes "
             "peuvent en tirer des conclusions différentes, ce n'est pas un "
             "critère — c'est une intention.")
    pourquoi = fields.Text("Pourquoi celui-là")

    actif = fields.Boolean("En cours", default=False, tracking=True)
    date_debut = fields.Date("Depuis", default=fields.Date.context_today)
    date_fin = fields.Date("Atteint le", readonly=True)
    atteint = fields.Boolean("Atteint", readonly=True, tracking=True)

    projet_id = fields.Many2one("project.project", "Projet")
    tag = fields.Char(
        "Étiquette des tâches", help="Les tâches qui portent cette étiquette "
        "comptent dans l'avancement affiché.")

    reste = fields.Integer("Reste", compute="_compute_reste")
    total = fields.Integer("Total", compute="_compute_reste")

    @api.depends("tag", "date_debut")
    def _compute_reste(self):
        # EN SUDO, et c'est le point (29/07) : le compte se faisait avec les
        # droits du VISITEUR — un invité lisait 0/0, et le même cap racontait
        # un chiffre différent selon qui regardait. L'avancement d'un cap est
        # un fait de la tour, pas une opinion de session. (Le compute n'est
        # pas stocké : il se recalcule à chaque affichage — la mise à jour
        # est donc automatique par construction.)
        #
        # SEULES LES TÂCHES CRÉÉES DEPUIS LE DÉBUT DU CAP COMPTENT (31/07,
        # choix de Patrick) : les 25 tâches taguées « v3 » avaient été
        # collées en lot le 28/07, dont 4 déjà faites avant le cap — le
        # compteur affichait 4/25 sans qu'aucun chantier n'ait bougé.
        # La progression part donc de zéro au lancement, et chaque tâche
        # nouvelle entre dans le compte.
        Task = self.env["project.task"].sudo()
        for rec in self:
            rec.reste = rec.total = 0
            if not rec.tag:
                continue
            tag = self.env["project.tags"].sudo().search(
                [("name", "=", rec.tag)], limit=1)
            if not tag:
                continue
            taches = Task.search([("tag_ids", "in", tag.id),
                                  ("active", "=", True),
                                  ("create_date", ">=", rec.date_debut)])
            rec.total = len(taches)
            rec.reste = len(taches.filtered(lambda t: not t.stage_id.fold))

    @api.constrains("actif")
    def _un_seul_cap(self):
        for rec in self:
            if not rec.actif:
                continue
            autres = self.search([("actif", "=", True), ("id", "!=", rec.id)])
            if autres:
                raise UserError(_(
                    "« %(autre)s » est déjà le cap en cours.\n\n"
                    "Deux caps à la fois, c'est aucun cap : on travaille sur "
                    "ce qui est le plus agréable au moment où on s'y met. "
                    "Termine celui-là, ou désactive-le explicitement — mais "
                    "que ce soit une décision, pas un glissement.",
                    autre=autres[0].name))

    def action_activer(self):
        self.ensure_one()
        self.search([("actif", "=", True)]).write({"actif": False})
        self.write({"actif": True, "date_debut": fields.Date.context_today(self)})
        self.message_post(body=_("Cap repris."))

    def action_atteint(self):
        """On ne coche pas « atteint » à la légère : c'est le seul moment où
        le critère écrit sert vraiment à quelque chose."""
        self.ensure_one()
        self.write({"atteint": True, "actif": False,
                    "date_fin": fields.Date.context_today(self)})
        self.message_post(body=_(
            "Cap atteint. Critère qui était pose : %s") % (self.critere or ""))

    @api.model
    def courant(self):
        return self.search([("actif", "=", True)], limit=1)
