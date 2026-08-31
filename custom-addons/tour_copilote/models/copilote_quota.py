# -*- coding: utf-8 -*-
"""Quota d'usage du copilote, par utilisateur.

Sans garde-fou, dix-sept personnes partagent la même clé d'API et la même
facture : une seule d'entre elles peut vider la cagnotte en une soirée, sans
mauvaise intention. Le quota borne le nombre d'échanges par personne et par
période glissante.

Ce n'est pas de la sécurité, c'est de la maîtrise de dépense : le but est
qu'une consommation anormale s'arrête d'elle-même au lieu d'apparaître sur un
relevé un mois plus tard.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from datetime import timedelta

PARAM_QUOTA = "tour_copilote.quota_jour"
PARAM_QUOTA_ADMIN = "tour_copilote.quota_jour_admin"
DEFAUT = 30
DEFAUT_ADMIN = 500


class CopiloteBan(models.Model):
    """Le bannissement des tentatives de révélation des spécifications.

    Un utilisateur qui insiste pour obtenir les specs internes (guides,
    fiches, architecture) est d'abord refusé, puis, à la 2e tentative du jour,
    banni du copilote pour 48 h. Le garde-fou du copilote se protège lui-même.
    """
    _name = "copilote.ban"
    _description = "Utilisateur suspendu du copilote"

    user_id = fields.Many2one("res.users", string="Utilisateur", required=True,
                              index=True)
    jusqu_a = fields.Datetime("Suspendu jusqu'au", required=True)

    @api.model
    def _banni(self, user):
        return self.sudo().search(
            [("user_id", "=", user.id),
             ("jusqu_a", ">", fields.Datetime.now())], limit=1)

    @api.model
    def _signaler_refus(self, user):
        """Compte chaque refus de specs ; à 2 par jour, ban 48 h."""
        Usage = self.env["copilote.usage"].sudo()
        jour = fields.Date.context_today(self)
        Usage.create({"user_id": user.id, "jour": jour, "modele": "REFUS_SPECS"})
        refus = Usage.search_count([
            ("user_id", "=", user.id), ("jour", "=", jour),
            ("modele", "=", "REFUS_SPECS")])
        if refus >= 2:
            self.sudo().create({
                "user_id": user.id,
                "jusqu_a": fields.Datetime.now() + timedelta(days=2),
            })


class CopiloteUsage(models.Model):
    _name = "copilote.usage"
    _description = "Échange consommé au copilote"
    _order = "create_date desc"

    user_id = fields.Many2one("res.users", string="Utilisateur", required=True,
                              index=True, ondelete="cascade")
    jour = fields.Date("Jour", required=True, index=True,
                       default=fields.Date.context_today)
    tokens_entree = fields.Integer("Tokens entrée")
    tokens_sortie = fields.Integer("Tokens sortie")
    cout_estime = fields.Float("Coût estimé (€)", digits=(12, 5))
    modele = fields.Char("Modèle")

    # ------------------------------------------------------------------
    @api.model
    def _quota_du_jour(self, user):
        icp = self.env["ir.config_parameter"].sudo()
        if user.has_group("base.group_system"):
            return int(icp.get_param(PARAM_QUOTA_ADMIN) or DEFAUT_ADMIN)
        return int(icp.get_param(PARAM_QUOTA) or DEFAUT)

    @api.model
    def verifier_avant_appel(self, user):
        """Lève une erreur lisible si la personne a épuisé sa journée."""
        quota = self._quota_du_jour(user)
        if quota <= 0:
            return
        consomme = self.sudo().search_count([
            ("user_id", "=", user.id),
            ("jour", "=", fields.Date.context_today(self)),
        ])
        if consomme >= quota:
            raise UserError(_(
                "Vous avez utilisé vos %(quota)s appels du jour au "
                "copilote. Le compteur repart demain.\n\n"
                "Ce n'est pas une punition : chaque échange coûte réellement de "
                "l'argent au propriétaire de cette tour. Si vous avez besoin de "
                "plus, demandez-lui.",
                quota=quota))

    @api.model
    def enregistrer(self, user, usage, modele):
        """Trace un échange et son coût estimé.

        Les tarifs sont ceux du modèle utilisé, en euros par million de tokens.
        Approximatif et suffisant : le but est de voir une dérive, pas de tenir
        une comptabilité.
        """
        # Par PRÉFIXE, pas par nom exact : « deepseek-chat » et les
        # identifiants datés (claude-haiku-4-5-20251001) tombaient sur le
        # tarif Opus par défaut — du DeepSeek facturé ~20 fois trop cher,
        # affiché à Patrick comme une mesure (relecture de Lois, 29/07).
        tarifs = [
            ("claude-opus", (5.0, 25.0)),
            ("claude-sonnet", (3.0, 15.0)),
            ("claude-haiku", (1.0, 5.0)),
            ("deepseek", (0.25, 1.0)),
        ]
        entree = getattr(usage, "input_tokens", 0) or 0
        sortie = getattr(usage, "output_tokens", 0) or 0
        pe, ps = next((t for prefixe, t in tarifs
                       if (modele or "").startswith(prefixe)), (5.0, 25.0))
        cout = (entree / 1_000_000.0) * pe + (sortie / 1_000_000.0) * ps
        self.sudo().create({
            "user_id": user.id,
            "tokens_entree": entree,
            "tokens_sortie": sortie,
            "cout_estime": cout,
            "modele": modele,
        })


class ResUsers(models.Model):
    _inherit = "res.users"

    # groups : ces champs se lisent sur N'IMPORTE QUEL utilisateur — sans
    # garde, un invité lirait la consommation de ses voisins. L'invité voit
    # la SIENNE par l'accueil (le contrôleur compte en sudo pour lui).
    # « appels », pas « échanges » : un message à Chloé peut coûter jusqu'à
    # quatre appels au modèle (outils) — le mot « échange » mentait.
    copilote_echanges_jour = fields.Integer(
        "Appels copilote aujourd'hui", compute="_compute_copilote_jour",
        groups="base.group_system")
    copilote_quota_texte = fields.Char(
        "Quota du jour", compute="_compute_copilote_jour",
        groups="base.group_system")

    def _compute_copilote_jour(self):
        Usage = self.env["copilote.usage"].sudo()
        for user in self:
            # Le jour dans le fuseau de CELUI QUI CONSOMME, pas de celui qui
            # regarde : à minuit passé à Paris, les appels du soir d'un
            # testeur à Ouagadougou restent dans SA journée (Lois, cas 5).
            aujourdhui = fields.Date.context_today(
                self.with_context(tz=user.tz or "UTC"))
            consomme = Usage.search_count([
                ("user_id", "=", user.id), ("jour", "=", aujourdhui)])
            quota = Usage._quota_du_jour(user)
            user.copilote_echanges_jour = consomme
            # Quota nul ou négatif = pas de limite. L'écrire, sinon la page
            # affiche « 0 / 0 » et se lit « tout le monde est bloqué ».
            if quota > 0:
                user.copilote_quota_texte = _(
                    "%(quota)s (reste %(reste)s)",
                    quota=quota, reste=max(0, quota - consomme))
            else:
                user.copilote_quota_texte = _("sans limite")
