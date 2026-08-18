# -*- coding: utf-8 -*-
"""La condensation : un résumé court par texte long, le détail à un clic.

Tout texte long rendu par un agent ou un utilisateur doit s'afficher PAR
DÉFAUT comme un résumé court, compréhensible par un enfant de six ans. Le
texte d'origine reste entier, dans un onglet « Détail ». Rien n'est supprimé.

Deux règles, dans le code :
- Le résumé ne doit RIEN COÛTER en clé d'API quand c'est possible. On cherche
  d'abord la coupe intelligente : les comptes rendus sont écrits conclusion
  d'abord (« COMMENCE par ta conclusion, en UNE phrase qu'un enfant de six ans
  comprend »), donc les premières phrases sont déjà le résumé. On n'appelle
  un modèle que si la coupe ne suffit pas à être courte.
- Le résumé se stocke à côté, le texte d'origine ne bouge JAMAIS. Un résumé
  qui remplace l'original est une perte de données.
"""

import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Le catalogue des textes longs connus : modèle + champ + seuil de
# déclenchement. C'est l'inventaire tenu par ce module — on peut y ajouter
# une cible sans toucher au moteur.
CATALOGUE = [
    ("reponse.fiche", "reponse", 280),
    ("atelier.mission", "reponse", 280),
    ("debat.avis", "reponse", 280),
    ("discussion.echange", "reponse", 280),
    ("depot.note", "contenu", 400),
    ("tour.guide", "contenu", 600),
    ("securite.constat", "constat", 280),
    ("securite.constat", "preconisation", 280),
    ("echange.agent", "reponse", 280),
]

# Longueur cible du résumé.
LIMITE_COURT = 220
# Au-delà, la coupe est trop longue pour compter comme résumé : on tente l'IA.
LIMITE_COUPE_MAX = 360


class CondenseCible(models.Model):
    _name = "condense.cible"
    _description = "Un champ de texte long à condenser (l'inventaire)"
    _order = "model_id, champ"

    model_id = fields.Many2one("ir.model", "Modèle", required=True, ondelete="cascade")
    champ = fields.Char("Champ", required=True,
                        help="Le nom technique du champ texte/html à condenser.")
    seuil = fields.Integer(
        "Seuil (caractères)", default=280, required=True,
        help="Au-delà de cette longueur, le texte est condensé.")
    active = fields.Boolean("Active", default=True)
    nb_resumes = fields.Integer("Résumés", compute="_compter")
    nom_modele = fields.Char("Modèle (nom)", related="model_id.model", readonly=True)

    _sql_constraints = [
        ("cible_unique", "unique(model_id, champ)",
         "Cette cible existe déjà dans l'inventaire."),
    ]

    @api.depends("model_id", "champ")
    def _compter(self):
        Resume = self.env["condense.resume"].sudo()
        for c in self:
            c.nb_resumes = Resume.search_count([("cible_id", "=", c.id)])


class CondenseResume(models.Model):
    _name = "condense.resume"
    _description = "Le résumé d'un texte long"
    _order = "write_date desc"

    cible_id = fields.Many2one("condense.cible", "Cible", required=True,
                               ondelete="cascade", index=True)
    res_id = fields.Integer("Enregistrement", required=True, index=True)
    texte = fields.Text("Le résumé", required=True)
    mode = fields.Selection(
        [("coupe", "Coupe intelligente (sans API)"),
         ("ia", "Résumé IA")],
        "Comment", required=True, default="coupe")
    surlignes = fields.Integer("Signes du texte d'origine")

    _sql_constraints = [
        ("resume_unique", "unique(cible_id, res_id)",
         "Ce texte a déjà son résumé."),
    ]

    def _vers_le_detail(self):
        """L'URL du texte d'origine, pour la page web."""
        self.ensure_one()
        base = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url", "").rstrip("/")
        modele = self.cible_id.nom_modele
        return "%s/web#id=%s&model=%s&view_type=form" % (
            base, self.res_id, modele)


class CondenseEngine(models.AbstractModel):
    _name = "condense.engine"
    _description = "Le moteur de condensation"

    # ------------------------------------------------------------------
    # Le texte propre : HTML et balises retirés, espaces réapprivoisés.
    # ------------------------------------------------------------------
    @api.model
    def _nettoyer(self, brut):
        t = re.sub(r"<[^>]+>", " ", str(brut or ""))
        t = re.sub(r"&amp;", "&", t)
        t = re.sub(r"&lt;", "<", t)
        t = re.sub(r"&gt;", ">", t)
        t = re.sub(r"&nbsp;", " ", t)
        t = re.sub(r"\s+", " ", t)
        return t.strip()

    # ------------------------------------------------------------------
    # Retirer l'en-tête technique des comptes rendus d'atelier.
    #
    # Un CR d'agent commence par « === CONSTRUIT PAR DEEPSEEK === Tours :
    # N · jetons : … ==== » ou « === OBSERVE PAR DEEPSEEK (lecture seule)
    # === … ». C'est de la facture, pas du fond : le laisser en tête, c'est
    # faire résumer la facture à la place du travail. On ne le retire QUE
    # s'il est en TOUT début — le milieu d'un texte peut le contenir à
    # bon droit.
    # ------------------------------------------------------------------
    EN_TETE_DEEPSEEK = re.compile(
        r"^===.*?^\s*={40,}\s*", re.S | re.M)

    @api.model
    def _sans_entete(self, texte):
        t = texte or ""
        return self.EN_TETE_DEEPSEEK.sub("", t, count=1).strip()

    # ------------------------------------------------------------------
    # La coupe intelligente : les premières phrases, sans aucune API.
    # ------------------------------------------------------------------
    @api.model
    def _couper(self, texte, limite=LIMITE_COURT):
        if len(texte) <= limite:
            return texte
        # On coupe à la frontière d'une phrase dans les limites.
        extrait = texte[:limite]
        # Cherche la dernière frontière de phrase dans l'extrait.
        frontieres = [m.end() for m in re.finditer(r"[.!?]\s", extrait)]
        if frontieres:
            return extrait[:frontieres[-1]].strip()
        # Pas de phrase complète : on coupe à l'espace le plus proche.
        espaces = [m.start() for m in re.finditer(r"\s", extrait)]
        if espaces:
            return extrait[:espaces[-1]].strip() + "…"
        return extrait.strip() + "…"

    # ------------------------------------------------------------------
    # Le recours IA (DeepSeek, clé configurable) — seulement si la coupe
    # ne suffit pas. Toujours enrobé : si l'API tombe, on garde la coupe.
    # `bref=True` force UNE phrase courte (quelques mots, niveau 6 ans) :
    # c'est le format demandé par Patrick pour l'en-tête « En bref ».
    # ------------------------------------------------------------------
    @api.model
    def _resumer_ia(self, texte, bref=False):
        # Clé d'API : paramètre système « condense.api_key », ou variable
        # d'environnement CONDENSE_API_KEY en secours. Pas de dépendance à
        # un Coffre interne : ce module est autonome (version community).
        cle = self.env["ir.config_parameter"].sudo().get_param(
            "condense.api_key", "")
        if not cle:
            import os
            cle = os.environ.get("CONDENSE_API_KEY", "")
        if not cle:
            return ""
        import json
        import urllib.request

        systeme = (
            "Tu racontes à un enfant de six ans ce qui a été fait. UNE seule "
            "phrase, maximum 20 mots, des mots très simples. Pas de jargon, "
            "pas de liste, pas de chiffres. Dis ce qui a été fait (et ce qui "
            "reste, si on le sait)." if bref else
            "Tu résumes en UNE phrase simple, compréhensible par un enfant "
            "de six ans. Pas de jargon, pas de liste. Dis ce qui a été fait "
            "et ce qui reste, si on le sait. Maximum 60 mots.")
        payload = json.dumps({
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": systeme},
                {"role": "user", "content": texte[:4000]},
            ],
            "max_tokens": 120,
            "temperature": 0.2,
        }).encode()
        req = urllib.request.Request(
            "https://api.deepseek.com/chat/completions", data=payload,
            headers={"Authorization": "Bearer %s" % cle,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
                return (data["choices"][0]["message"]["content"] or "").strip()
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Condensation : appel IA échoué (%s)", exc)
            return ""

    # ------------------------------------------------------------------
    # Le moteur complet : résumer un texte.
    # ------------------------------------------------------------------
    @api.model
    def _resumer(self, texte):
        propre = self._sans_entete(self._nettoyer(texte))
        if len(propre) <= LIMITE_COURT:
            return propre, "coupe", len(propre)
        coupe = self._couper(propre)
        if len(coupe) <= LIMITE_COUPE_MAX:
            return coupe, "coupe", len(propre)
        # La coupe est encore trop longue : on tente l'IA, sinon on la garde.
        resume = self._resumer_ia(propre) or coupe
        mode = "ia" if resume != coupe else "coupe"
        return resume[:LIMITE_COUPE_MAX], mode, len(propre)

    # ------------------------------------------------------------------
    # Le résumé BREF : quelques mots, niveau enfant de six ans. C'est le
    # format de l'en-tête « En bref » (Patrick, 31/07 : « il faut quelques
    # mots pour un enfant de 6 ans »). L'IA reformule en une phrase courte ;
    # si elle tombe, on retombe sur la coupe, raccourcie.
    # ------------------------------------------------------------------
    @api.model
    def _resumer_bref(self, texte):
        propre = self._nettoyer(texte)
        if not propre:
            return ""
        if len(propre) <= 80:
            return propre
        resume = self._resumer_ia(propre, bref=True)
        if resume:
            return resume[:LIMITE_COUPE_MAX].strip()
        # Repli sans IA : la première vraie phrase, coupée court.
        # On retire d'abord l'en-tête technique du CR : la coupe prendrait
        # « === OBSERVE PAR DEEPSEEK === » sinon.
        sans = self._sans_entete(propre)
        coupe = self._couper(sans, limite=180)
        if len(coupe) <= 180:
            return coupe
        return coupe[:180].rsplit(" ", 1)[0] + "…"

    # ------------------------------------------------------------------
    # Condenser un enregistrement précis (création ou mise à jour).
    # ------------------------------------------------------------------
    @api.model
    def _condenser(self, cible, res_id):
        cible.ensure_one()
        modele = cible.nom_modele
        if modele not in self.env:
            return False
        rec = self.env[modele].sudo().browse(res_id)
        if not rec.exists() or cible.champ not in rec._fields:
            return False
        brut = rec[cible.champ]
        propre = self._nettoyer(brut)
        if len(propre) <= cible.seuil:
            # Texte court : pas de résumé, on retire l'ancien s'il existe.
            ancien = self.env["condense.resume"].sudo().search([
                ("cible_id", "=", cible.id), ("res_id", "=", res_id)])
            if ancien:
                ancien.unlink()
            return False
        resume, mode, longueur = self._resumer(brut)
        Resume = self.env["condense.resume"].sudo()
        existant = Resume.search([
            ("cible_id", "=", cible.id), ("res_id", "=", res_id)], limit=1)
        vals = {"texte": resume, "mode": mode, "surlignes": longueur}
        if existant:
            existant.write(vals)
        else:
            Resume.create(dict(vals, cible_id=cible.id, res_id=res_id))
        return True

    # ------------------------------------------------------------------
    # La balayeuse : garde-fou automatique, déclenchée par le cron.
    # ------------------------------------------------------------------
    @api.model
    def _condenser_recents(self, minutes=30):
        """Condense les textes longs créés ou modifiés depuis peu."""
        depuis = fields.Datetime.subtract(
            fields.Datetime.now(), minutes=minutes)
        total = 0
        Cible = self.env["condense.cible"].sudo()
        for cible in Cible.search([("active", "=", True)]):
            modele = cible.nom_modele
            if modele not in self.env:
                continue
            model = self.env[modele].sudo()
            if cible.champ not in model._fields:
                continue
            recs = model.search([("write_date", ">=", depuis)],
                                order="id desc", limit=200)
            for rec in recs:
                if self._condenser(cible, rec.id):
                    total += 1
        return total

    @api.model
    def _cron_condenser(self):
        self._condenser_recents(minutes=45)
        return True

    # ------------------------------------------------------------------
    # Le rattrapage : tout ce qui existe déjà, en une passe.
    # ------------------------------------------------------------------
    @api.model
    def _rattraper(self, cible_ids=None, limite=1000):
        total = 0
        Cible = self.env["condense.cible"].sudo()
        cibles = Cible.browse(cible_ids) if cible_ids else \
            Cible.search([("active", "=", True)])
        for cible in cibles:
            modele = cible.nom_modele
            if modele not in self.env:
                continue
            model = self.env[modele].sudo()
            if cible.champ not in model._fields:
                continue
            recs = model.search([], order="id desc", limit=limite)
            for rec in recs:
                if self._condenser(cible, rec.id):
                    total += 1
        return total

    @api.model
    def _inventorier(self):
        """Rebâtit l'inventaire depuis le catalogue + les champs existants."""
        cree = 0
        IrModel = self.env["ir.model"].sudo()
        Cible = self.env["condense.cible"].sudo()
        for nom_modele, champ, seuil in CATALOGUE:
            if nom_modele not in self.env:
                continue
            model = IrModel.search([("model", "=", nom_modele)], limit=1)
            if not model or champ not in self.env[nom_modele]._fields:
                continue
            existant = Cible.search(
                [("model_id", "=", model.id), ("champ", "=", champ)], limit=1)
            if not existant:
                Cible.create({"model_id": model.id, "champ": champ,
                              "seuil": seuil})
                cree += 1
        return cree

    def action_lancer(self):
        """Bouton : condenser tout de suite sur toutes les cibles."""
        self.ensure_one()
        n = self._rattraper(limite=2000)
        raise UserError(_("Condensation terminée : %s résumé(s) créé(s) ou "
                          "mis à jour.", n))

    def action_rattraper(self):
        """Bouton de la page : tout rattraper, sans message bloquant."""
        n = self._rattraper(limite=2000)
        return n
