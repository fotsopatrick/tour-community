# -*- coding: utf-8 -*-
"""Lire un ticket directement dans Jira, à partir de sa clé.

Jusqu'ici la tour attendait qu'une notification arrive par courriel. C'est
passif : on ne reçoit que ce que Jira a bien voulu notifier, souvent tronqué,
et jamais l'état courant du ticket. Ici on va le chercher.

Le jeton n'est jamais stocké dans cette fiche : il vit dans le Coffre, et on
n'en garde qu'une référence. Un connecteur appartient à une personne — même un
administrateur ne lit pas le Jira d'un autre avec ses identifiants.
"""
import base64
import json
import logging
import re
import urllib.error
import urllib.request

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

RE_CLE = re.compile(r"^[A-Z][A-Z0-9_]{1,20}-\d{1,7}$")
RE_BALISE = re.compile(r"<[^>]+>")
DELAI = 20


class DevJira(models.Model):
    _name = "dev.jira"
    _description = "Connexion à Jira"
    _rec_name = "site"

    # Pas de « placeholder » ici : ce n'est pas un parametre de champ Odoo
    # (il est ignore et journalise en avertissement). Il se met dans la vue.
    site = fields.Char(
        "Adresse Jira", required=True,
        help="Le nom de domaine de votre Jira, sans https:// ni barre finale.")
    email = fields.Char(
        "Identifiant", required=True,
        help="L'adresse de courriel de votre compte Atlassian. C'est elle qui "
             "accompagne le jeton, pas votre mot de passe.")
    secret_id = fields.Many2one(
        "vault.secret", string="Jeton d'API (Coffre)", required=True,
        help="La fiche du Coffre qui contient le jeton d'API Atlassian. "
             "Le jeton lui-même n'est jamais stocké ici.")
    user_id = fields.Many2one("res.users", string="Propriétaire", required=True,
                              default=lambda self: self.env.user,
                              ondelete="cascade", index=True)
    actif = fields.Boolean("Actif", default=True)
    dernier_message = fields.Char("Dernier état", readonly=True)

    # ------------------------------------------------------------------
    def _appeler(self, chemin):
        """Un GET authentifié sur l'API de Jira."""
        self.ensure_one()
        jeton = self.secret_id.sudo().lire_secret()
        if not jeton:
            raise UserError(_(
                "La fiche du Coffre « %s » ne contient aucun jeton.",
                self.secret_id.display_name))

        site = (self.site or "").strip().rstrip("/")
        site = re.sub(r"^https?://", "", site)
        url = "https://%s%s" % (site, chemin)

        # Jira s'authentifie en Basic avec « courriel:jeton ». Ce n'est pas le
        # mot de passe du compte : un jeton se révoque sans changer le reste.
        identite = base64.b64encode(
            ("%s:%s" % (self.email or "", jeton)).encode()).decode()
        requete = urllib.request.Request(url, headers={
            "Authorization": "Basic %s" % identite,
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(requete, timeout=DELAI) as reponse:
                return json.loads(reponse.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise UserError(_(
                    "Jira a refusé la connexion (%s). Vérifier l'identifiant "
                    "et le jeton : un jeton d'API Atlassian n'est PAS le mot "
                    "de passe du compte, il se crée dans les paramètres de "
                    "sécurité du compte Atlassian.", exc.code))
            if exc.code == 404:
                raise UserError(_(
                    "Jira ne trouve pas ce ticket. Vérifier la clé, et que le "
                    "compte a le droit de le voir."))
            raise UserError(_("Jira a répondu %(c)s : %(m)s",
                              c=exc.code, m=exc.reason))
        except urllib.error.URLError as exc:
            raise UserError(_(
                "Impossible de joindre %(s)s : %(e)s", s=site, e=exc.reason))

    @api.model
    def _texte(self, html_ou_rien):
        """Le rendu HTML de Jira, ramené à du texte lisible."""
        if not html_ou_rien:
            return ""
        texte = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>", "\n", html_ou_rien)
        texte = re.sub(r"<li>", "- ", texte)
        texte = RE_BALISE.sub("", texte)
        for avant, apres in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                             ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
            texte = texte.replace(avant, apres)
        return re.sub(r"\n{3,}", "\n\n", texte).strip()

    def lire_ticket(self, cle):
        """L'état courant d'un ticket, tel que Jira le connaît maintenant."""
        self.ensure_one()
        cle = (cle or "").strip().upper()
        if not RE_CLE.match(cle):
            raise UserError(_(
                "« %s » ne ressemble pas à une clé de ticket. Une clé s'écrit "
                "PROJET-142.", cle))

        # renderedFields : Jira renvoie la description déjà mise en forme.
        # Sans ça, l'API rend un document structuré qu'il faudrait parcourir
        # nœud par nœud pour en tirer une phrase.
        donnees = self._appeler(
            "/rest/api/3/issue/%s?fields=summary,description,status,issuetype,"
            "priority,labels,components&expand=renderedFields" % cle)
        champs = donnees.get("fields") or {}
        rendus = donnees.get("renderedFields") or {}

        def nom(valeur):
            return (valeur or {}).get("name") or ""

        return {
            "cle": donnees.get("key") or cle,
            "titre": champs.get("summary") or "",
            "description": self._texte(rendus.get("description"))
                           or self._texte(champs.get("description") if
                                          isinstance(champs.get("description"), str)
                                          else ""),
            "statut": nom(champs.get("status")),
            "type": nom(champs.get("issuetype")),
            "priorite": nom(champs.get("priority")),
            "etiquettes": ", ".join(champs.get("labels") or []),
            "composants": ", ".join(nom(c) for c in (champs.get("components") or [])),
            "url": "https://%s/browse/%s" % (
                re.sub(r"^https?://", "", (self.site or "").strip().rstrip("/")),
                donnees.get("key") or cle),
        }

    # ------------------------------------------------------------------
    def action_tester(self):
        """Vérifie que la connexion marche, sans rien créer."""
        self.ensure_one()
        moi = self._appeler("/rest/api/3/myself")
        message = _("Connecté en tant que %s",
                    moi.get("displayName") or moi.get("emailAddress") or "?")
        self.dernier_message = message
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {"title": _("Jira"), "message": message,
                       "type": "success", "sticky": False},
        }

    @api.model
    def pour(self, user=None):
        """Le connecteur de cette personne, s'il en a un."""
        user = user or self.env.user
        return self.search([("user_id", "=", user.id), ("actif", "=", True)],
                           limit=1)

    # ------------------------------------------------------------------
    cle_a_confier = fields.Char(
        "Clé du ticket à confier", copy=False,
        help="Par exemple PROJ-301. Le ticket sera lu dans Jira, puis confié "
             "à l'atelier avec le moteur WinDev.")

    def action_confier_ticket(self):
        """Lit le ticket dans Jira et en fait une mission d'atelier."""
        self.ensure_one()
        if not self.cle_a_confier:
            raise UserError(_("Indiquez la clé du ticket, par exemple PROJ-301."))
        infos = self.lire_ticket(self.cle_a_confier)
        mission = self.env["atelier.mission"].creer_depuis_ticket(infos)
        self.cle_a_confier = False
        return {
            "type": "ir.actions.act_window", "res_model": "atelier.mission",
            "res_id": mission.id, "view_mode": "form", "target": "current",
        }
