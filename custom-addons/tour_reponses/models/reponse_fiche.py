# -*- coding: utf-8 -*-
"""Les réponses gardées.

Une console se relit mal : la réponse utile est noyée entre deux pages de
travail, et elle disparaît avec la session. Une fiche par couple
question / réponse rend la chose cherchable des mois plus tard, et surtout
attribuée — savoir QUI a répondu et QUAND change la confiance qu'on accorde
au contenu.

Volontairement pauvre en logique : ce module conserve, il ne raisonne pas.
Tout comportement automatique ajouté ici (résumé, classement, relance) devrait
d'abord répondre à la question « qu'est-ce qui se casse le jour où il se
trompe ? ».
"""
import logging
import re
from html import unescape

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

CONFIDENTIEL = re.compile(
    r"(?i)(sk-[a-z0-9_-]{6,}|(?:password|passwd|token|secret|api[_-]?key)\s*[:=]\s*\S+|"
    r"\b(?:0|\+33)\s?[1-9](?:[\s.-]?\d{2}){4}\b)")
MAX_MAILS_JOUR = 5


class ReponseFiche(models.Model):
    _name = "reponse.fiche"
    _description = "Réponse gardée"
    # La derniere reponse en premier : on cherche presque toujours la plus
    # recente, et l'ordre par defaut est ce qu'on lit sans y penser.
    _order = "date desc, id desc"

    name = fields.Char(
        "Question", required=True,
        help="Ce qui a été demandé, dans les mots de la question.")
    reponse = fields.Html(
        "Réponse",
        help="La réponse telle qu'elle a été donnée.")
    # LE RESUME (Patrick, 30/07 : « un enfant de 6 ans, pas un doctorant
    # en lecture »). Les comptes rendus des agents sont des murs de texte
    # qui rendent la tour illisible a la main. On extrait un resume COURT,
    # sans appeler aucune IA : les agents ecrivent deja leur propre resume
    # (« trois lignes simples »), on le recupere ; sinon on prend le debut
    # du vrai contenu, une fois retire l en-tete technique.
    resume = fields.Text(
        "En bref", compute="_compute_resume", store=True,
        help="Le coeur de la reponse, en court. Le detail complet est\n"
             "dans l onglet Detail.")
    # Champ texte et non many2one : « Claude », « Chloe » ou « Victor » ne sont
    # pas des utilisateurs Odoo, et forcer un compte pour chacun inventerait des
    # identites la ou on veut seulement une attribution lisible.
    auteur = fields.Char(
        "Répondu par", help="Qui a répondu : Claude, Chloe, un collègue…")
    # A qui appartient la fiche : c'est ce champ, et lui seul, qui decide de ce
    # que chacun voit (voir security/reponse_rules.xml).
    user_id = fields.Many2one(
        "res.users", string="Pour qui", required=True, ondelete="cascade",
        default=lambda self: self.env.user)
    date = fields.Datetime(
        "Répondu le", required=True, default=fields.Datetime.now,
        help="Une réponse sans date vieillit sans qu'on s'en aperçoive.")
    a_envoyer = fields.Boolean(
        "À envoyer par mail", default=False,
        help="Coché, la réponse part une fois par mail. Garde-fous : pas de "
             "contenu sensible, quota par jour, jamais deux envois.")
    envoye_le = fields.Datetime("Envoyée le", readonly=True)
    mail_erreur = fields.Char("Blocage mail", readonly=True)

    @api.model
    def create(self, vals):
        fiche = super().create(vals)
        if vals.get("a_envoyer"):
            fiche._traiter_envoi_mail()
        fiche._lancer_circuit_titre()
        return fiche

    def _lancer_circuit_titre(self):
        """Circuit « Titre des Reponses — style de Patrick » (02/08) : le
        titre de la question est reformule — ce que Patrick a mis dans sa
        question, condense, dans son style — par le Clone de Patrick, puis
        valide. Ne casse jamais la creation d'une fiche.

        PIÈGE (02/08) : les fiches créées PAR le circuit (missions « Circuit
        — », « Reproposition », « Suite », « Un agent est bloqué », « Envoyer
        la mission », « Titre — ») sont du bruit de métadonnées — leur lancer
        un circuit de titre les relançait à l'infini (cascade de décisions).
        On ne traite que les vraies questions."""
        nom = (self.name or "").strip()
        bruit = ("Circuit —", "Reproposition", "Suite :", "Titre —",
                 "Un agent est bloqué", "Envoyer la mission",
                 "Lancement commercial")
        if not nom or nom.startswith(bruit):
            return
        try:
            if "circuit.instance" in self.env and "circuit.modele" in self.env:
                Modele = self.env["circuit.modele"].sudo()
                gabarit = Modele.search(
                    [("name", "=", "Titre des Reponses — style de Patrick")],
                    limit=1)
                if gabarit:
                    self.env["circuit.instance"].sudo().create({
                        "modele_id": gabarit.id,
                        "name": "Titre — %s" % (nom[:60]),
                        "sujet": (
                            "<p>Fiche Réponse (id %s). Question : <b>%s</b>.</p>"
                            "<p>Reformuler le TITRE : ce que Patrick a mis dans "
                            "sa question, condense, dans son style.</p>"
                            % (self.id, nom)),
                    }).action_lancer()
        except Exception:  # noqa: BLE001 — jamais bloquer une creation
            pass

    def write(self, vals):
        resultat = super().write(vals)
        if vals.get("a_envoyer"):
            self._traiter_envoi_mail()
        return resultat

    def action_envoyer_mail(self):
        self._traiter_envoi_mail(force=True)
        return True

    def _traiter_envoi_mail(self, force=False):
        for fiche in self:
            if force or not fiche.envoye_le:
                fiche._envoyer_reponse_mail()

    def _signaler_blocage(self, raison):
        _logger.warning("Réponse %s : mail bloqué (%s)", self.id, raison)

    def _envoyer_reponse_mail(self):
        self.ensure_one()
        if self.envoye_le:
            return False
        texte = unescape(re.sub(r"<[^>]+>", " ", self.reponse or ""))
        if CONFIDENTIEL.search(texte):
            self.write({"mail_erreur": "contenu sensible", "a_envoyer": False})
            self._signaler_blocage("contenu sensible")
            return False
        debut = fields.Datetime.to_datetime(fields.Date.context_today(self))
        if self.search_count([("envoye_le", ">=", debut)]) >= MAX_MAILS_JOUR:
            self.write({"mail_erreur": "quota du jour", "a_envoyer": False})
            self._signaler_blocage("quota du jour")
            return False
        if "mail.mail" not in self.env:
            self.write({"mail_erreur": "mail indisponible"})
            return False
        Mail = self.env["mail.mail"]
        dest = (self.user_id.email or "").strip()
        if not dest or self.user_id.share:
            dest = self.env["tour.signal"]._destinataire() if "tour.signal" in self.env else False
        if not dest:
            self.write({"mail_erreur": "aucun destinataire"})
            return False
        Mail.sudo().create({
            "subject": "[Réponse] %s" % (self.name or "Sans titre"),
            "body_html": self.reponse or "<p>(vide)</p>",
            "email_from": self.env.company.email or "contact@matourdecontrole.fr",
            "email_to": dest,
            "auto_delete": False,
        }).send()
        self.write({"envoye_le": fields.Datetime.now(), "mail_erreur": False})
        return True

    @api.depends("reponse")
    def _compute_resume(self):
        for fiche in self:
            fiche.resume = self._resumer(fiche.reponse or "")

    @staticmethod
    def _resumer(html):
        """Un resume court, sans IA. On jette le decor, on garde la prose.

        Le format des comptes rendus varie d un agent a l autre : impossible de
        le parser proprement avec une seule regex. On travaille donc ligne par
        ligne — on ecarte tout ce qui ressemble a du decor technique (barres,
        marqueurs ===, statistiques, echafaudage << CE QUE J AI COMPRIS >>) et
        on garde les premieres vraies phrases. Deterministe, donc previsible.
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
            l = ligne.strip().lstrip("-*#>\u2022 ").strip()
            if not l or re.fullmatch(r"[=\-_*\u00b7\u2022\s]+", l):
                continue
            low = l.lower()
            if any(low.startswith(p) for p in rejets):
                continue
            if len(l) < 12 or not re.search(r"[A-Za-z\u00c0-\u00ff]", l):
                continue
            bonnes.append(l)
            if sum(len(x) for x in bonnes) > 320:
                break
        resume = re.sub(r"\s+", " ", " ".join(bonnes)).strip()
        if len(resume) <= 300:
            return resume
        coupe = resume[:300]
        p = max(coupe.rfind(". "), coupe.rfind("! "), coupe.rfind("? "))
        return coupe[:p + 1] if p > 120 else coupe.rsplit(" ", 1)[0] + " \u2026"
