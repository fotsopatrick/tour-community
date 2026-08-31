# -*- coding: utf-8 -*-
"""Un ticket remonté depuis la boîte mail.

Un message que l'on n'arrive pas à interpréter est conservé avec le drapeau
« non reconnu » plutôt que jeté : mieux vaut une ligne à trier qu'une
information perdue en silence.
"""
import re
from html import unescape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# L'adresse du ticket dans les notifications Jira.
RE_URL = re.compile(r"https?://[\w.-]+/browse/[A-Z][A-Z0-9_]+-\d+")
RE_BASE = re.compile(r"https?://([\w-]+\.atlassian\.net)")


class DevTicket(models.Model):
    _name = "dev.ticket"
    _description = "Ticket remonté"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char("Sujet", required=True)
    cle = fields.Char("Ticket", index=True, help="Par exemple PROJ-142.")
    boite_id = fields.Many2one("dev.boite", string="Boîte", required=True,
                               ondelete="cascade", index=True)
    user_id = fields.Many2one("res.users", string="Pour", required=True,
                              ondelete="cascade", index=True)
    message_id = fields.Char("Identifiant du message", index=True, required=True)
    expediteur = fields.Char("De")
    contenu = fields.Text("Contenu")
    # EN BREF : le coeur du ticket, sans IA (meme recette que reponse.fiche).
    # Un courriel de notification est souvent un mur de texte ; on lit le
    # resume, le message entier reste dans l'onglet Detail.
    resume = fields.Text(
        "En bref", compute="_compute_resume", store=True,
        help="Le coeur du ticket, en court. Le message complet est dans "
             "l'onglet Détail.")
    url = fields.Char("Lien", compute="_compute_url", store=True)
    reconnu = fields.Boolean("Reconnu", default=True,
                             help="Décoché : le message n'a pas pu être "
                                  "interprété, à regarder à la main.")
    traite = fields.Boolean("Traité", default=False)

    _sql_constraints = [
        ("message_unique", "unique(boite_id, message_id)",
         "Ce message a déjà été remonté."),
    ]

    @api.depends("contenu", "cle")
    def _compute_url(self):
        for rec in self:
            direct = RE_URL.search(rec.contenu or "")
            if direct:
                rec.url = direct.group(0)
                continue
            base = RE_BASE.search(rec.contenu or "")
            if base and rec.cle:
                rec.url = "https://%s/browse/%s" % (base.group(1), rec.cle)
            else:
                rec.url = False

    @api.depends("contenu")
    def _compute_resume(self):
        for rec in self:
            rec.resume = self._resumer(rec.contenu or "")

    @staticmethod
    def _resumer(html):
        """Un resume court, sans IA. On jette le decor, on garde la prose.

        Recopie de reponse.fiche : on travaille ligne par ligne, on ecarte le
        decor technique (barres, marqueurs ===, statistiques) et on garde les
        premieres vraies phrases. Deterministe, donc previsible.
        """
        if not html:
            return ""
        texte = unescape(re.sub(r"<[^>]+>", "\n", html))
        rejets = ("===", "---", "***", "tours", "jetons", "fichiers",
                  "appels", "attention", "moteur", "ce qu on", "ce qu'on",
                  "ce qui", "ce que", "voici ce qu", "trois lignes",
                  "trois phrases", "aucun fichier", "construit par")
        bonnes = []
        for ligne in texte.splitlines():
            l = ligne.strip().lstrip("-*#>• ").strip()
            if not l or re.fullmatch(r"[=\-_*·•\s]+", l):
                continue
            low = l.lower()
            if any(low.startswith(p) for p in rejets):
                continue
            if len(l) < 12 or not re.search(r"[A-Za-zÀ-ÿ]", l):
                continue
            bonnes.append(l)
            if sum(len(x) for x in bonnes) > 320:
                break
        resume = re.sub(r"\s+", " ", " ".join(bonnes)).strip()
        if len(resume) <= 300:
            return resume
        coupe = resume[:300]
        p = max(coupe.rfind(". "), coupe.rfind("! "), coupe.rfind("? "))
        return coupe[:p + 1] if p > 120 else coupe.rsplit(" ", 1)[0] + " …"

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        for ticket in tickets:
            ticket._notifier()
        return tickets

    def _notifier(self):
        """Dépose une activité pour la personne concernée.

        UNIQUEMENT pour un ticket reconnu. Le 25/07, un filtre expéditeur
        retiré le temps d'un test a fait remonter 97 courriels ordinaires : 97
        activités, donc 97 notifications par courriel dans la boîte de
        l'utilisateur. Une notification par message non identifié n'a aucune
        valeur et transforme l'outil en nuisance.

        Les messages non reconnus restent consultables dans la liste — ils ne
        sont pas perdus, ils ne réveillent simplement personne.
        """
        self.ensure_one()
        if not self.reconnu:
            return
        try:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                summary=(self.cle and "%s — %s" % (self.cle, self.name)
                         or self.name)[:200],
                note=self.url and _("Ouvrir : %s", self.url) or "",
                user_id=self.user_id.id,
            )
        except Exception:  # noqa: BLE001 — le ticket prime sur la notification
            pass

    def action_ouvrir_jira(self):
        self.ensure_one()
        if not self.url:
            return False
        return {"type": "ir.actions.act_url", "url": self.url, "target": "new"}

    def action_traiter(self):
        for rec in self:
            rec.traite = True
            rec.activity_ids.filtered(
                lambda a: a.user_id == rec.user_id).action_done()
        return True

    def action_confier_atelier(self):
        """Transforme ce ticket en mission d'atelier.

        Si un connecteur Jira est configuré et que le ticket a une clé, on va
        chercher l'état COURANT du ticket plutôt que de se contenter du
        courriel : une notification date du jour où elle est partie, et le
        ticket a souvent bougé depuis.
        """
        self.ensure_one()
        infos = None
        if self.cle:
            connecteur = self.env["dev.jira"].pour(self.user_id)
            if connecteur:
                try:
                    infos = connecteur.lire_ticket(self.cle)
                except UserError as exc:
                    # Jira injoignable n'est pas une raison de ne rien faire :
                    # le contenu du courriel reste exploitable.
                    self.message_post(body=_(
                        "Lecture directe dans Jira impossible (%s). La mission "
                        "part avec le contenu du courriel.", exc))

        if infos is None:
            infos = {
                "cle": self.cle or "",
                "titre": self.name or "",
                "description": self.contenu or "",
                "url": self.url or "",
            }

        mission = self.env["atelier.mission"].creer_depuis_ticket(infos)
        self.message_post(body=_("Confié à l'atelier (mission « %s »).",
                                 mission.name))
        return {
            "type": "ir.actions.act_window", "res_model": "atelier.mission",
            "res_id": mission.id, "view_mode": "form", "target": "current",
        }
