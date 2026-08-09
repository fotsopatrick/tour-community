import logging
import re

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class TourNouveaute(models.Model):
    """Une nouveauté de la tour, expliquée pour que tout le monde suive.

    La règle d'écriture est celle de Patrick : un enfant de 6 ans doit
    comprendre. Le champ « lisible » mesure ce qui se mesure — phrases
    courtes, mots courts — et la fiche le montre : un voyant, pas une
    interdiction, parce qu'aucune machine ne juge vraiment la clarté.
    """

    _name = "tour.nouveaute"
    _description = "Une nouveauté de la tour"
    _order = "date desc, id desc"

    name = fields.Char("Ce qui est arrivé", required=True,
                       help="Une ligne, comme on le dirait à voix haute.")
    explication = fields.Text(
        "À quoi ça sert", required=True,
        help="Phrases courtes, mots de tous les jours. Un enfant de 6 ans "
             "doit pouvoir suivre.")
    lien = fields.Char("Où cliquer",
                       help="Le chemin dans la tour, ex : /tour/equipe")
    date = fields.Date("Arrivée le", default=fields.Date.context_today,
                       required=True)
    annoncee_le = fields.Datetime("Annoncée le", readonly=True, copy=False)
    lisible = fields.Boolean("Écrit simple", compute="_compute_lisible",
                             store=True)

    @api.depends("name", "explication")
    def _compute_lisible(self):
        for n in self:
            texte = "%s. %s" % (n.name or "", n.explication or "")
            phrases = [p for p in re.split(r"[.!?\n]+", texte) if p.strip()]
            trop_longues = [p for p in phrases if len(p.split()) > 22]
            mots = [m for m in re.findall(r"[\w'-]+", texte)
                    if "/" not in m and "http" not in m]
            trop_gros = [m for m in mots if len(m) > 17]
            n.lisible = not trop_longues and not trop_gros

    @api.model
    def _cron_annoncer(self):
        """Le courriel du neuf : un par personne, seulement s'il y a du neuf.

        Il part vers les utilisateurs internes qui ont une adresse — pas
        de compte technique, pas d'adresse vide. Et seulement là où
        l'annonce est armée : une instance cliente ne se met pas à écrire
        à ses gens parce qu'un module est installé.
        """
        icp = self.env["ir.config_parameter"].sudo()
        if not icp.get_param("tour_nouveautes.annonces_actives"):
            return
        fraiches = self.sudo().search([("annoncee_le", "=", False)],
                                      order="date, id")
        if not fraiches:
            return
        base_url = icp.get_param("web.base.url", "").rstrip("/")
        expediteur = self._expediteur()
        destinataires = self.env["res.users"].sudo().search([
            ("active", "=", True), ("share", "=", False),
            ("email", "!=", False),
            ("login", "not in", ("admin", "odoo", "default", "__system__")),
        ])
        lignes = "".join(
            "<li style='margin-bottom:8px'><b>%s</b><br/>%s%s</li>" % (
                n.name, (n.explication or "").replace("\n", "<br/>"),
                (" <a href='%s%s'>Voir</a>" % (base_url, n.lien))
                if n.lien else "")
            for n in fraiches)
        corps = (
            "<div style='font-family:sans-serif'>"
            "<p>Du neuf dans la tour de contrôle :</p>"
            "<ul>%s</ul>"
            "<p><a href='%s/tour/nouveautes'>Voir toutes les "
            "fonctionnalités</a> — les nouvelles y sont en tête.</p>"
            "</div>" % (lignes, base_url))
        for u in destinataires:
            try:
                self.env["mail.mail"].sudo().create({
                    "subject": "Du neuf dans la tour — %d nouveauté(s)"
                               % len(fraiches),
                    "body_html": corps,
                    "email_from": expediteur,
                    "email_to": u.email,
                    "auto_delete": False,
                }).send()
            except Exception:  # noqa: BLE001 — un envoi raté ne bloque pas les autres
                _logger.exception("Nouveautés : envoi raté vers %s", u.login)
        fraiches.write({"annoncee_le": fields.Datetime.now()})
        _logger.info("Nouveautés : %d annoncée(s) à %d personne(s)",
                     len(fraiches), len(destinataires))

    def _expediteur(self):
        if "tour.signal" in self.env:
            try:
                return self.env["tour.signal"]._expediteur()
            except Exception:  # noqa: BLE001
                pass
        return self.env.company.email or "nouveautes@matourdecontrole.fr"
