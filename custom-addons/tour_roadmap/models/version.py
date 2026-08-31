# -*- coding: utf-8 -*-
"""Valider une version — par projet, et sur les tâches directement.

Depuis le 28/07, une version n'engendre plus de tâches : les tâches SONT la
feuille de route (voir project_task.py). Valider ne fait donc qu'une chose —
figer. Et ça se fait projet par projet : la V2 de la tour et la V2 de Duelle
sont deux verrous distincts, parce que ce sont deux produits.

Ce que figer empêche : qu'une tâche entre ou sorte de cette version sans qu'on
s'en rende compte. Tant que la liste bouge, on ne peut pas commencer — chaque
matin elle n'est plus la même. Valider, c'est décider que la liste est le
contrat.

Rouvrir reste possible, mais demande d'écrire pourquoi, et ça reste inscrit.
Une version qu'on ne pourrait plus rouvrir forcerait à mentir le jour où le
monde change : on créerait une « V2 bis ». Ce qu'on veut éviter, ce n'est pas
de changer d'avis, c'est de changer d'avis sans s'en rendre compte.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .roadmap import VERSIONS


class RoadmapVersion(models.Model):
    _name = "roadmap.version"
    _description = "Version d'un projet"
    _inherit = ["mail.thread"]
    _order = "projet_id, sequence, id"

    projet_id = fields.Many2one(
        "project.project", "Projet", required=True, index=True, ondelete="cascade")
    code = fields.Selection(VERSIONS, "Version", required=True)
    name = fields.Char("Nom", compute="_compute_name", store=True)
    sequence = fields.Integer(default=10)

    etat = fields.Selection(
        [("ouverte", "Ouverte — les tâches bougent encore"),
         ("figee", "Validée — la liste est le contrat")],
        "État", default="ouverte", required=True, tracking=True)

    figee_le = fields.Datetime("Validée le", readonly=True)
    figee_par_id = fields.Many2one("res.users", "Validée par", readonly=True)
    motif_reouverture = fields.Text("Pourquoi rouverte", readonly=True)

    nb_taches = fields.Integer("Tâches", compute="_compter")
    # Le contenu d'une version, lisible d'un coup d'œil. Patrick, le 28/07 :
    # « la version un a ceci, la deux a ceci, ceci est déjà fait dans la deux
    # — en vert —, ceci reste à faire ». « Fait » = l'étape repliée du projet
    # (la colonne Fait), le même critère que le kanban : deux définitions du
    # mot « fait » finiraient par se contredire.
    nb_faites = fields.Integer("Faites", compute="_compter")
    nb_restantes = fields.Integer("Restantes", compute="_compter")
    avancement = fields.Integer("Avancement (%)", compute="_compter")
    # « La tour est à quelle version ? » — la réponse est CALCULÉE, jamais
    # cochée à la main : c'est la première version (dans l'ordre v1, v2, v3)
    # qui a encore du travail. Cocher à la main, c'est mentir un jour ou
    # l'autre ; compter, non.
    courante = fields.Boolean("On travaille ici", compute="_compter")

    _sql_constraints = [
        ("projet_code_unique", "unique(projet_id, code)",
         "Cette version existe déjà pour ce projet."),
    ]

    @api.depends("code", "projet_id")
    def _compute_name(self):
        libelles = dict(VERSIONS)
        for rec in self:
            rec.name = "%s — %s" % (rec.projet_id.display_name or "?",
                                    libelles.get(rec.code, rec.code or ""))

    def _compter(self):
        Task = self.env["project.task"]
        ordre = [c for c, _l in VERSIONS]
        for rec in self:
            base = [("project_id", "=", rec.projet_id.id),
                    ("tdc_version", "=", rec.code)]
            rec.nb_taches = Task.search_count(base)
            rec.nb_faites = Task.search_count(base + [("stage_id.fold", "=", True)])
            rec.nb_restantes = rec.nb_taches - rec.nb_faites
            rec.avancement = (100 * rec.nb_faites // rec.nb_taches) if rec.nb_taches else 0
        # La version courante d'un projet : la premiere qui a encore du
        # travail. Calculee apres coup, sur les compteurs frais.
        for rec in self:
            freres = self.search([("projet_id", "=", rec.projet_id.id)])
            en_cours = [f for f in freres
                        if f.nb_restantes > 0 and f.code in ("v1", "v2", "v3")]
            en_cours.sort(key=lambda f: ordre.index(f.code))
            rec.courante = bool(en_cours) and en_cours[0].id == rec.id

    @api.model
    def _figee(self, projet_id, code):
        """Cette version de ce projet est-elle figée ? Faux si elle n'existe pas.

        Une version inconnue ne bloque rien : un projet neuf n'a pas encore de
        ligne, et un verrou qui se referme sur du vide bloque quelqu'un qui n'a
        rien demandé.
        """
        if not projet_id or not code:
            return False
        v = self.sudo().search([("projet_id", "=", projet_id),
                                ("code", "=", code)], limit=1)
        return bool(v) and v.etat == "figee"

    def _taches(self):
        self.ensure_one()
        return self.env["project.task"].search([
            ("project_id", "=", self.projet_id.id),
            ("tdc_version", "=", self.code)])

    def action_figer(self):
        for rec in self:
            taches = rec._taches()
            if not taches:
                raise UserError(_(
                    "Aucune tâche en « %s ». Valider une version vide ne fige "
                    "rien et donne l'impression du contraire.") % rec.name)
            rec.write({"etat": "figee", "figee_le": fields.Datetime.now(),
                       "figee_par_id": self.env.user.id,
                       "motif_reouverture": False})
            rec.message_post(body=_(
                "Version validée par %(qui)s : %(n)s tâches figées. Elles ne "
                "peuvent plus entrer ni sortir de cette version.",
                qui=self.env.user.name, n=len(taches)))
        return True

    def action_voir_faites(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("%s — fait") % self.name,
            "res_model": "project.task",
            "view_mode": "list,form",
            "domain": [("project_id", "=", self.projet_id.id),
                       ("tdc_version", "=", self.code),
                       ("stage_id.fold", "=", True)],
        }

    def action_voir_restantes(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("%s — reste à faire") % self.name,
            "res_model": "project.task",
            "view_mode": "list,form",
            "domain": [("project_id", "=", self.projet_id.id),
                       ("tdc_version", "=", self.code),
                       ("stage_id.fold", "=", False)],
        }

    def action_voir_taches(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "project.task",
            "view_mode": "list,form",
            "domain": [("project_id", "=", self.projet_id.id),
                       ("tdc_version", "=", self.code)],
        }

    def action_rouvrir(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "roadmap.reouverture",
            "view_mode": "form",
            "target": "new",
            "name": _("Rouvrir %s") % self.name,
            "context": {"default_version_id": self.id},
        }


class RoadmapReouverture(models.TransientModel):
    _name = "roadmap.reouverture"
    _description = "Rouvrir une version validée"

    version_id = fields.Many2one("roadmap.version", required=True)
    motif = fields.Text(
        "Pourquoi rouvrir", required=True,
        help="Ce que le monde a changé depuis la validation. « On a changé "
             "d'avis » est une réponse acceptable — encore faut-il l'écrire.")

    def action_confirmer(self):
        self.ensure_one()
        self.version_id.write({"etat": "ouverte", "motif_reouverture": self.motif})
        self.version_id.message_post(body=_(
            "Version rouverte par %(qui)s. Motif : %(m)s",
            qui=self.env.user.name, m=self.motif))
        return {"type": "ir.actions.act_window_close"}
