# -*- coding: utf-8 -*-
"""Le coffre.

Un secret n'est jamais stocké en clair : la base ne contient qu'un jeton
Fernet. La clé de chiffrement vit dans la variable d'environnement
``ODOO_VAULT_KEY`` (posée dans ``~/tour/.env`` sur le VPS) — donc un dump de
la base volé ne suffit pas à déchiffrer quoi que ce soit.

Repli : si la variable est absente (dev local), la clé est générée dans
``ir.config_parameter``. C'est pratique mais moins solide — dans ce cas la
clé et les secrets voyagent ensemble dans le dump. Le champ « Protection »
de la fiche dit lequel des deux régimes s'applique.
"""
import base64
import logging
import os

from odoo import _, api, fields, models
from odoo.exceptions import UserError, AccessError

_logger = logging.getLogger(__name__)

PARAM_CLE = "tour_vault.master_key"
ENV_CLE = "ODOO_VAULT_KEY"
MASQUE = "••••••••••••"


class VaultSecret(models.Model):
    _name = "vault.secret"
    _description = "Coffre — secret"
    _inherit = ["mail.thread"]
    _order = "categorie, name"

    name = fields.Char("Libellé", required=True, tracking=True,
                       help="À quoi sert ce secret. Ex. « Supabase Duelle — mot de passe base ».")
    categorie = fields.Selection(
        [("infra", "Infrastructure"), ("api", "Clé d'API"),
         ("bancaire", "Bancaire / paiement"), ("client", "Client"),
         ("perso", "Perso"), ("autre", "Autre")],
        string="Catégorie", default="autre", required=True, tracking=True)
    identifiant = fields.Char("Identifiant", help="Le login, l'email ou l'utilisateur associé.")
    url = fields.Char("Adresse", help="Où ce secret sert (console, dashboard…).")
    notes = fields.Text("Notes")

    user_id = fields.Many2one(
        "res.users", string="Propriétaire", required=True, ondelete="cascade",
        default=lambda self: self.env.user,
        help="Chacun ne voit que ses propres secrets.")

    secret_chiffre = fields.Char("Jeton chiffré", readonly=True, copy=False, groups="base.group_system")
    secret = fields.Char(
        "Secret", compute="_compute_secret", inverse="_inverse_secret",
        store=False, copy=False,
        help="Saisis la valeur ici : elle est chiffrée à l'enregistrement et "
             "n'est plus jamais réaffichée telle quelle.")
    secret_defini = fields.Boolean("Renseigné", compute="_compute_secret_defini", store=True)
    protection = fields.Char("Protection", compute="_compute_protection")
    derniere_lecture = fields.Datetime("Dernière lecture", readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Chiffrement
    # ------------------------------------------------------------------
    @api.model
    def _fernet(self):
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:  # pragma: no cover
            raise UserError(_("La bibliothèque « cryptography » est absente de l'image Docker.")) from exc

        cle = (os.environ.get(ENV_CLE) or "").strip()
        if not cle:
            icp = self.env["ir.config_parameter"].sudo()
            cle = (icp.get_param(PARAM_CLE) or "").strip()
            if not cle:
                cle = Fernet.generate_key().decode()
                icp.set_param(PARAM_CLE, cle)
                _logger.warning(
                    "Vault : %s absente, cle de repli generee dans ir.config_parameter. "
                    "Poser %s dans l'environnement pour une vraie separation.", ENV_CLE, ENV_CLE)
        try:
            return Fernet(cle.encode() if isinstance(cle, str) else cle)
        except Exception as exc:
            raise UserError(_(
                "La clé de chiffrement du coffre est invalide. Elle doit être une clé "
                "Fernet (44 caractères base64).")) from exc

    @api.depends("secret_chiffre")
    def _compute_secret_defini(self):
        for rec in self:
            rec.secret_defini = bool(rec.sudo().secret_chiffre)

    def _compute_protection(self):
        fort = bool((os.environ.get(ENV_CLE) or "").strip())
        libelle = (_("Clé hors base (solide)") if fort
                   else _("Clé en base (repli — poser ODOO_VAULT_KEY)"))
        for rec in self:
            rec.protection = libelle

    def _compute_secret(self):
        """Jamais la vraie valeur : le formulaire n'affiche qu'un masque."""
        for rec in self:
            rec.secret = MASQUE if rec.sudo().secret_chiffre else False

    def _inverse_secret(self):
        for rec in self:
            valeur = rec.secret
            if not valeur or valeur == MASQUE:
                continue
            jeton = self._fernet().encrypt(valeur.encode()).decode()
            rec.sudo().write({"secret_chiffre": jeton})
            rec.message_post(body=_("Secret enregistré (chiffré)."))

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # LA SERRURE (05/08/2026)
    # ------------------------------------------------------------------
    def _garde_lecture_claire(self, porte):
        """Le clair ne sort que pour du code serveur privilégié.

        Avant cette méthode, la protection reposait sur le NOM des méthodes :
        un underscore devant, donc pas appelable en RPC. Deux trous :

        1. `lire_secret` n'avait pas d'underscore. Sa docstring affirmait
           « volontairement non exposé au RPC public » — c'était faux. En Odoo,
           toute méthode publique d'un modèle est appelable par `call_kw`.
           N'importe quel compte interne récupérait le mot de passe en clair
           depuis un navigateur, en contournant le `groups="base.group_system"`
           posé sur le champ.
        2. `_lire` cherche en `sudo()` puis appelle `_valeur_claire` sur le
           recordset sudo : à cet instant on est déjà superutilisateur, donc
           plus aucune vérification ne s'applique. Le sudo interne annulait la
           protection qu'il était censé servir.

        Constaté par `deploy/test-vault.sh`, confirmé compte en main.

        La serrure ne dépend plus d'un nom : soit l'appelant est du code
        serveur (`env.su`), soit c'est un administrateur. Sinon, refus tracé.
        """
        if self.env.su or self.env.user.has_group("base.group_system"):
            return
        _logger.warning(
            "Vault : %s (uid %s) a tente de lire un secret en clair par %s — refuse.",
            self.env.user.login, self.env.uid, porte)
        raise AccessError(_(
            "Le contenu du coffre ne se lit pas depuis un compte ordinaire. "
            "Demandez à un administrateur."))

    def _valeur_claire(self, motif="un module de la tour"):
        """La valeur en clair, pour du code — jamais pour un écran.

        Sans cette porte, un module qui a besoin d'un jeton oblige un humain à
        ouvrir le Coffre, révéler, copier, coller. Ce trajet-là est le vrai
        risque : la valeur passe par le presse-papier, l'historique du terminal
        et parfois une capture d'écran. Le Coffre servait à éviter ça.

        **Le préfixe `_` n'est pas une convention de style, c'est la serrure.**
        En Odoo, toute méthode publique est appelable en RPC : nommée
        `valeur_claire`, cette méthode aurait permis à n'importe qui ayant accès
        au modèle de sortir tous les secrets en une requête, depuis le
        navigateur. Ne jamais la renommer sans le souligne.

        Deux autres garde-fous :
        - chaque lecture est datée ET écrite dans le fil de la fiche, avec le
          motif : on doit pouvoir répondre à « qui a lu ce jeton, et pourquoi » ;
        - elle rend `False` si rien n'est enregistré, au lieu de lever : un
          déploiement doit pouvoir dire « il me manque cette clé » proprement,
          pas exploser au milieu.
        """
        self._garde_lecture_claire("_valeur_claire")
        self.ensure_one()
        jeton = self.sudo().secret_chiffre
        if not jeton:
            return False
        clair = self._fernet().decrypt(jeton.encode()).decode()
        self.sudo().write({"derniere_lecture": fields.Datetime.now()})
        self.message_post(body=_("Secret lu par %s.", motif))
        return clair

    @api.model
    def _lire(self, libelle, motif="un module de la tour"):
        """Le secret nommé `libelle`, ou False. Insensible à la casse.

        On cherche d'abord parmi les fiches RENSEIGNÉES. Sans ça, une fiche
        vide portant le même libellé masque la bonne — et le message d'erreur
        dit « le Coffre n'a pas de secret nommé X » alors que si, il l'a. C'est
        arrivé le 26/07 : trois fiches vides créées d'avance, trois fiches
        remplies créées à côté, et rien ne marchait sans qu'on comprenne
        pourquoi. Un doublon est une erreur d'usage banale ; y répondre par un
        message faux est une erreur de conception.
        """
        self._garde_lecture_claire("_lire")
        base = [("name", "=ilike", libelle)]
        rec = self.sudo().search(base + [("secret_chiffre", "!=", False)], limit=1)
        if not rec:
            rec = self.sudo().search(base, limit=1)
        return rec._valeur_claire(motif) if rec else False

    def action_reveler(self):
        """Déchiffre et affiche, en traçant l'accès dans le fil de la fiche."""
        self._garde_lecture_claire("action_reveler")
        self.ensure_one()
        jeton = self.sudo().secret_chiffre
        if not jeton:
            raise UserError(_("Aucun secret n'est enregistré sur cette fiche."))
        try:
            clair = self._fernet().decrypt(jeton.encode()).decode()
        except Exception as exc:
            raise UserError(_(
                "Impossible de déchiffrer : la clé actuelle n'est pas celle qui a "
                "servi à chiffrer ce secret.")) from exc
        self.sudo().write({"derniere_lecture": fields.Datetime.now()})
        self.message_post(body=_("Secret révélé par %s.", self.env.user.name))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.name,
                "message": clair,
                "sticky": True,
                "type": "warning",
            },
        }

    def lire_secret(self):
        """Accès programmatique, pour les autres modules de la tour.

        Volontairement non exposé au RPC public : à appeler en sudo() depuis
        du code serveur (ex. le module « dev » qui a besoin du mot de passe
        d'application Gmail)."""
        self._garde_lecture_claire("lire_secret")
        self.ensure_one()
        jeton = self.sudo().secret_chiffre
        if not jeton:
            return False
        return self._fernet().decrypt(jeton.encode()).decode()
