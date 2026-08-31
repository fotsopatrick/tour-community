import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class AbonnementActif(models.Model):
    """Un abonnement qu'on paie, et qu'on risque d'oublier.

    Le piège des abonnements, c'est qu'ils sont silencieux : ils se
    renouvellent ou expirent pendant qu'on pense à autre chose. Cette fiche
    garde de quoi s'en souvenir — le service, la période, la date de fin —
    et la tour écrit un courriel de rappel avant que ça se passe, puis
    relance chaque semaine tant qu'on n'a rien décidé.

    Trois garde-fous, parce qu'un rappel mal bâti est pire que pas de
    rappel du tout :
    - aucun courriel ne part sans adresse (`email_rappel`) ;
    - un abonnement résilié ou inactif ne rappelle jamais ;
    - un envoi qui échoue est loggé, pas perdu : la date reste atteinte et
      le passage suivant retente.
    """

    _name = "abonnement.actif"
    _description = "Un abonnement en cours"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "rappel_le, date_fin, name"

    name = fields.Char("Service", required=True, tracking=True,
                       help="Ce qu'on a pris : Manning — AI Agents in Action…")
    site = fields.Char("Lien du service",
                       help="Où retrouver l'abonnement, ex. https://www.manning.com")
    cout = fields.Float("Coût", digits="Product Price")
    periode = fields.Selection(
        [("mois", "Par mois"),
         ("an", "Par an"),
         ("ponctuel", "Ponctuel")],
        "Période", default="mois", required=True)
    date_debut = fields.Date("Débute le")
    date_fin = fields.Date("Finit le", tracking=True)
    actif = fields.Boolean("Encore actif", default=True, tracking=True)
    notes = fields.Text("Notes")

    email_rappel = fields.Char("Adresse de rappel",
                               help="Où la tour enverra le courriel. Vide = "
                                    "jamais de rappel, par sécurité.")
    rappel_le = fields.Date("Prochain rappel le", tracking=True,
                            help="La date du prochain courriel. Sans elle, "
                                 "rien ne part.")
    dernier_rappel = fields.Datetime("Dernier rappel", readonly=True)
    nb_rappels = fields.Integer("Rappels envoyés", readonly=True,
                                default=0)

    etat = fields.Selection(
        [("en_cours", "En cours"),
         ("bientot", "Finit bientôt"),
         ("expire", "Expiré"),
         ("inactif", "Inactif")],
        "État", compute="_compute_etat", store=True, index=True)

    @api.depends("actif", "date_fin")
    def _compute_etat(self):
        hui = fields.Date.context_today(self)
        for a in self:
            if not a.actif:
                a.etat = "inactif"
            elif not a.date_fin:
                a.etat = "en_cours"
            elif a.date_fin < hui:
                a.etat = "expire"
            elif a.date_fin <= hui + timedelta(days=4):
                a.etat = "bientot"
            else:
                a.etat = "en_cours"

    @api.model_create_multi
    def create(self, vals_list):
        """À la naissance, on arme le premier rappel si rien n'est posé.

        Le défaut est « fin − 4 jours » : laisser assez de temps pour agir
        sans crier trop tôt. Jamais avant la date du jour, ni sans adresse.
        """
        for vals in vals_list:
            if not vals.get("rappel_le") and not vals.get("id"):
                fin = vals.get("date_fin")
                if fin and vals.get("email_rappel"):
                    valeurs = dict(vals)
                    rappel = fields.Date.to_date(fin) - timedelta(days=4)
                    hui = fields.Date.context_today(self)
                    if rappel < hui:
                        rappel = hui
                    valeurs["rappel_le"] = rappel
                    vals.update(valeurs)
        return super().create(vals_list)

    def _expediteur(self):
        if "tour.signal" in self.env:
            try:
                return self.env["tour.signal"]._expediteur()
            except Exception:  # noqa: BLE001
                pass
        return self.env.company.email or "rappels@matourdecontrole.fr"

    def action_envoyer_rappel(self):
        """Bouton « Envoyer le rappel maintenant » : envoie et rearme."""
        for a in self:
            if a.email_rappel:
                a._envoyer_rappel()
        return True

    def action_resilier(self):
        """Bouton « Résilié — couper les rappels » : plus un courriel."""
        for a in self:
            a.actif = False
            a.email_rappel = False
            a.rappel_le = False
        return True

    def _envoyer_rappel(self):
        """Le courriel d'un abonnement, et le rearmement de sa date.

        N'envoie que si tout est en place : adresse, date atteinte (ou
        demande explicite), abonnement encore actif. Jamais autrement.
        Quand le courriel part, la date est repoussée de 7 jours — on
        n'écrit pas deux fois le même jour.
        """
        self.ensure_one()
        if not self.email_rappel or not self.actif:
            return

        hui = fields.Date.context_today(self)
        if not self.rappel_le or self.rappel_le > hui:
            if not self.env.context.get("forcer_rappel"):
                return

        base_url = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url", "").rstrip("/")
        fin = self.date_fin or _("non précisée")
        corps = (
            "<div style='font-family:sans-serif'>"
            "<p><b>%s</b> court toujours.</p>"
            "<ul>"
            "<li>Période : %s</li>"
            "<li>Finit le : <b>%s</b></li>"
            "<li>Coût : %s</li>"
            "</ul>"
            "<p>Si tu veux encore évoluer, c'est le moment. Pour rappeler "
            "la tour d'y songer plus tard, rien à faire : elle relancera "
            "dans une semaine. Pour marquer la résiliation, ouvre la fiche "
            "et clique sur « Résilié ».</p>"
            "<p>Voir la fiche : <a href='%s'>%s</a></p>"
            "</div>" % (
                self.name, self.periode, fin,
                self.cout or _("non communiqué"),
                base_url, base_url))
        try:
            self.env["mail.mail"].sudo().create({
                "subject": "Rappel : %s court encore" % self.name,
                "body_html": corps,
                "email_from": self._expediteur(),
                "email_to": self.email_rappel,
                "auto_delete": False,
            }).send()
        except Exception:  # noqa: BLE001 — un envoi raté ne gèle pas le reste
            _logger.exception("Abonnements : envoi du rappel raté pour %s",
                              self.name)
            raise
        self.dernier_rappel = fields.Datetime.now()
        self.rappel_le = self.rappel_le + timedelta(days=7) if self.rappel_le \
            else hui + timedelta(days=7)
        self.nb_rappels = (self.nb_rappels or 0) + 1
        _logger.info("Abonnements : rappel envoyé pour %s (%s)",
                     self.name, self.email_rappel)

    @api.model
    def _cron_rappels(self):
        """Le tour quotidien : tout rappel dont la date est atteinte.

        Ne s'arrête jamais sur une fiche en erreur : on relance le tour et
        la fiche en faute retente au passage suivant — sa date est toujours
        atteinte. C'est la tolérance demandée.
        """
        hui = fields.Date.context_today(self)
        a_envoyer = self.sudo().search([
            ("actif", "=", True),
            ("email_rappel", "!=", False),
            ("rappel_le", "!=", False),
            ("rappel_le", "<=", hui),
        ])
        for a in a_envoyer:
            try:
                a.with_context(force_rappel=True)._envoyer_rappel()
            except Exception:  # noqa: BLE001
                _logger.exception("Abonnements : rapport %s en échec, "
                                  "sera retenté", a.name)
        return len(a_envoyer)
