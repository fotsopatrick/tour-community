import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class BugRetour(models.Model):
    """Un retour de testeur : ce qui ne va pas, et de quoi le revoir.

    Le piège d'un module de bugs est de demander vingt champs et de
    n'obtenir qu'un titre. Ici trois champs portent tout le poids —
    ce que tu faisais, ce que tu attendais, ce qui est arrivé — parce
    qu'un bug qu'on ne sait pas reproduire ne se corrige pas, il se
    discute.

    Les captures d'écran vivent dans la conversation de la fiche : on en
    glisse autant qu'on veut, elles restent datées et signées.
    """

    _name = "bug.retour"
    _description = "Retour d'un testeur"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "gravite, create_date desc"

    name = fields.Char("En une phrase, ce qui ne va pas", required=True,
                       tracking=True)
    ou = fields.Char("Où ça s'est passé",
                     help="La page, l'écran, l'app. Ex : « la démo, page "
                          "des projets » ou « mon site Alaska Whisky ».")
    testeur = fields.Char(
        "Qui l'a vu", help="Le nom du testeur, s'il n'a pas de compte ici.")
    user_id = fields.Many2one("res.users", "Déposé par", required=True,
                              default=lambda self: self.env.user,
                              readonly=True, index=True)

    faisait = fields.Text("1. Ce que tu faisais", required=True,
                          help="Les gestes, dans l'ordre. « J'ai cliqué "
                               "sur X, puis sur Y. »")
    attendait = fields.Text("2. Ce que tu attendais", required=True)
    arrive = fields.Text("3. Ce qui est arrivé", required=True,
                         help="Le message exact s'il y en a un — recopié, "
                              "pas résumé.")

    gravite = fields.Selection(
        [("1", "Ça bloque — impossible de continuer"),
         ("2", "Gênant — il y a un contournement"),
         ("3", "Détail — c'est moche ou pas clair")],
        "Gravité", default="2", required=True, index=True, tracking=True)
    etat = fields.Selection(
        [("nouveau", "À regarder"),
         ("confirme", "Reproduit"),
         ("corrige", "Corrigé"),
         ("refuse", "Pas un bug")],
        "État", default="nouveau", required=True, tracking=True, index=True)
    reponse = fields.Text("Ce qu'on en a fait",
                          help="Obligatoire pour fermer : le testeur a "
                               "droit à une réponse, pas à un silence.")
    tache_id = fields.Many2one("project.task", "Tâche de correction",
                               readonly=True, copy=False)
    nb_captures = fields.Integer("Captures", compute="_compte_captures")

    def _compte_captures(self):
        for r in self:
            r.nb_captures = self.env["ir.attachment"].sudo().search_count([
                ("res_model", "=", "bug.retour"), ("res_id", "=", r.id)])

    @api.model_create_multi
    def create(self, vals_list):
        retours = super().create(vals_list)
        for r in retours:
            r._prevenir()
        return retours

    def _prevenir(self):
        """Un bloquant réveille quelqu'un ; le reste attend la lecture."""
        self.ensure_one()
        if self.gravite != "1" or "tour.signal" not in self.env:
            return
        try:
            self.env["tour.signal"]._signaler(
                agent="Les retours",
                titre=_("Bug bloquant : %s", self.name),
                corps_html=_(
                    "<p><b>Où :</b> %(o)s</p><p><b>Il faisait :</b> %(f)s</p>"
                    "<p><b>Il attendait :</b> %(a)s</p>"
                    "<p><b>Il a eu :</b> %(r)s</p>",
                    o=self.ou or "?", f=self.faisait or "", a=self.attendait or "",
                    r=self.arrive or ""),
                ton="echec")
        except Exception:  # noqa: BLE001
            _logger.exception("Retours : signal raté")

    def action_confirmer(self):
        """Reproduit : ça devient un travail, avec son prompt déjà écrit."""
        for r in self:
            if not r.tache_id:
                r.tache_id = self.env["project.task"].sudo().create({
                    "name": "Bug : %s" % r.name[:100],
                    "project_id": 1,
                    "description":
                        "<p><b>Où :</b> %s</p><p><b>Il faisait :</b> %s</p>"
                        "<p><b>Il attendait :</b> %s</p>"
                        "<p><b>Il a eu :</b> %s</p>"
                        "<p><b>PROMPT CLAUDE CODE :</b> reproduire ce défaut "
                        "d'abord (le contrôle qui le trouve doit exister "
                        "avant le correctif), corriger, puis repasser ce "
                        "même contrôle au vert. Retour n° %s dans la "
                        "tour.</p>" % (r.ou or "?", r.faisait or "",
                                       r.attendait or "", r.arrive or "", r.id),
                }).id
            r.etat = "confirme"
        return True

    def action_corrige(self):
        for r in self:
            if not (r.reponse or "").strip():
                from odoo.exceptions import UserError
                raise UserError(_(
                    "Écris ce qu'on en a fait avant de fermer : celui qui "
                    "a pris le temps de signaler a droit à une réponse."))
            r.etat = "corrige"
        return True

    def action_refuser(self):
        for r in self:
            if not (r.reponse or "").strip():
                from odoo.exceptions import UserError
                raise UserError(_(
                    "Dis pourquoi ce n'est pas un bug. Un refus sans motif "
                    "décourage le prochain signalement."))
            r.etat = "refuse"
        return True
