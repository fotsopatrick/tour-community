# -*- coding: utf-8 -*-
"""Les interrupteurs d'urgence : couper les invités, changer de moteur.

Demandés par Patrick le 29/07, un soir où le crédit API, la limite de
l'abonnement et la patience ont sauté en même temps. Un interrupteur ne
vaut que s'il est bête : deux boutons, aucun réglage, et l'inverse
toujours possible d'un clic.
"""
import json
import logging
import urllib.request

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# La liste de qui a été coupé vit dans un paramètre, pas en mémoire :
# l'interrupteur doit savoir rouvrir même après un redémarrage.
PARAM_COUPES = "tour_securite.invites_coupes"


class SecuriteInterrupteur(models.TransientModel):
    _name = "securite.interrupteur"
    _description = "Interrupteurs d'urgence"

    fournisseur = fields.Char("Moteur du copilote", readonly=True)
    invites_actifs = fields.Integer("Invités avec accès", readonly=True)
    invites_coupes = fields.Integer("Invités coupés", readonly=True)
    invite_ids = fields.Many2many("res.users", string="Comptes concernés",
                                  readonly=True)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        icp = self.env["ir.config_parameter"].sudo()
        vals["fournisseur"] = icp.get_param(
            "tour_copilote.fournisseur") or "anthropic"
        candidats = self._invites()
        vals["invites_actifs"] = len(candidats)
        vals["invites_coupes"] = len(self._coupes())
        vals["invite_ids"] = [(6, 0, candidats.ids)]
        return vals

    def _invites(self):
        """Les comptes qu'on peut couper sans se couper soi-même.

        Tout utilisateur interne actif, sauf les administrateurs : couper
        l'admin depuis un bouton d'urgence, c'est fermer la porte de la
        cabine de pilotage de l'intérieur.
        """
        exclus = [self.env.ref("base.user_root").id,
                  self.env.ref("base.user_admin").id, self.env.uid]
        candidats = self.env["res.users"].sudo().search([
            ("active", "=", True),
            ("share", "=", False),
            ("id", "not in", exclus),
        ])
        return candidats - self.env.ref("base.group_system").sudo().users

    def _coupes(self):
        brut = self.env["ir.config_parameter"].sudo().get_param(
            PARAM_COUPES) or ""
        ids = [int(x) for x in brut.split(",") if x.strip().isdigit()]
        return self.env["res.users"].sudo().with_context(
            active_test=False).browse(ids).exists()

    # ------------------------------------------------------------------
    def action_couper_invites(self):
        self.ensure_one()
        invites = self._invites()
        if not invites:
            raise UserError(_("Aucun invité à couper."))
        icp = self.env["ir.config_parameter"].sudo()
        deja = icp.get_param(PARAM_COUPES) or ""
        anciens = {int(x) for x in deja.split(",") if x.strip().isdigit()}
        icp.set_param(PARAM_COUPES, ",".join(
            str(i) for i in sorted(anciens | set(invites.ids))))
        noms = ", ".join(invites.mapped("login"))
        invites.write({"active": False})
        _logger.warning("Interrupteur : %s invités coupés par %s : %s",
                        len(invites), self.env.user.login, noms)
        return self._notifier(_(
            "%s invités coupés. Le bouton « Rouvrir » les fait revenir.")
            % len(invites))

    def action_rouvrir_invites(self):
        self.ensure_one()
        coupes = self._coupes()
        if not coupes:
            raise UserError(_("Personne n'a été coupé par cet interrupteur."))
        coupes.write({"active": True})
        self.env["ir.config_parameter"].sudo().set_param(PARAM_COUPES, "")
        _logger.warning("Interrupteur : %s invités rouverts par %s",
                        len(coupes), self.env.user.login)
        return self._notifier(_("%s invités rouverts.") % len(coupes))

    # ------------------------------------------------------------------
    def action_moteur_deepseek(self):
        return self._basculer("deepseek")

    def action_moteur_claude(self):
        return self._basculer("anthropic")

    def _basculer(self, cible):
        self.ensure_one()
        self._tester_cle(cible)
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("tour_copilote.fournisseur", cible)
        # L'INTERRUPTEUR AGIT SUR TOUT, PAS SEULEMENT LA BULLE.
        # Avant le 31/07, « basculer le moteur » ne changeait que le
        # fournisseur du copilote (Chloe) : l'atelier continuait de partir
        # sur claude, et la bascule « d'urgence » laissait la dépense la
        # plus lourde intacte. Le bouton de l'accueil (/tour/moteur) savait
        # déjà forcer l'atelier via atelier.moteur_force — l'interrupteur
        # doit faire pareil, sinon deux boutons disent deux choses.
        if cible == "deepseek":
            icp.set_param("atelier.moteur_force", "deepseek-agent")
        else:
            icp.set_param("atelier.moteur_force", "")
        _logger.warning("Interrupteur : copilote basculé sur %s par %s",
                        cible, self.env.user.login)
        return self._notifier(_(
            "Le copilote parle maintenant via %s (clé testée avant bascule), "
            "et l'atelier est forcé sur %s."
            % (cible, "deepseek-agent" if cible == "deepseek" else "le moteur d'origine"))
        )

    def _tester_cle(self, cible):
        """Un appel d'un jeton avant de basculer : on ne branche pas le
        copilote sur un moteur qui ne répond pas — c'est le défaut qui a
        laissé la bulle muette un après-midi entier (29/07)."""
        icp = self.env["ir.config_parameter"].sudo()
        if cible == "deepseek":
            cle = (icp.get_param("tour_copilote.deepseek_key") or "").strip()
            if not cle and "vault.secret" in self.env:
                try:
                    cle = (self.env["vault.secret"].sudo()._lire(
                        "deepseek-api-key",
                        motif="interrupteur moteur") or "").strip()
                except Exception:
                    cle = ""
            url = "https://api.deepseek.com/chat/completions"
            corps = {"model": "deepseek-chat", "max_tokens": 1,
                     "messages": [{"role": "user", "content": "ping"}]}
            entetes = {"Authorization": "Bearer %s" % cle}
        else:
            cle = (icp.get_param("tour_copilote.api_key") or "").strip()
            url = "https://api.anthropic.com/v1/messages"
            corps = {"model": "claude-haiku-4-5", "max_tokens": 1,
                     "messages": [{"role": "user", "content": "ping"}]}
            entetes = {"x-api-key": cle, "anthropic-version": "2023-06-01"}
        if not cle:
            raise UserError(_("Aucune clé configurée pour %s.") % cible)
        entetes["content-type"] = "application/json"
        req = urllib.request.Request(url, data=json.dumps(corps).encode(),
                                     headers=entetes, method="POST")
        try:
            urllib.request.urlopen(req, timeout=20)
        except Exception as exc:
            detail = ""
            try:
                detail = exc.read().decode()[:200]
            except Exception:
                pass
            raise UserError(_(
                "La clé %(qui)s ne répond pas — bascule refusée "
                "(réponse %(err)s). %(detail)s",
                qui=cible, err=getattr(exc, "code", "?"), detail=detail))

    # ------------------------------------------------------------------
    def action_compromission(self):
        """Procédure de compromission : couper les invités + arrêter Braignak.

        Déclenchée en un clic quand la tour est attaquée :
        1. Coupe tous les invités (désactive leurs comptes)
        2. Arrête Braignak et supprime son autorisation via l'ordre hôte
        3. Bascule le copilote sur un moteur de repli

        Seul le propriétaire (admin) reste actif.
        """
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        journal = []

        # 1. Couper les invités
        invites = self._invites()
        if invites:
            deja = icp.get_param(PARAM_COUPES) or ""
            anciens = {int(x) for x in deja.split(",") if x.strip().isdigit()}
            icp.set_param(PARAM_COUPES, ",".join(
                str(i) for i in sorted(anciens | set(invites.ids))))
            invites.write({"active": False})
            noms = ", ".join(invites.mapped("login"))
            _logger.warning("COMPROMISSION : %s invités coupés par %s : %s",
                            len(invites), self.env.user.login, noms)
            journal.append(_("%s invités coupés") % len(invites))

        # 2. Arrêter Braignak et déposer l'ordre stop
        if "braignak.etude" in self.env:
            Etude = self.env["braignak.etude"].sudo()
            actives = Etude.search([("etat", "in", ("observation", "prototype"))])
            if actives:
                for e in actives:
                    e._journaliser(
                        "compromission",
                        "arrêt forcé par %s" % self.env.user.login)
                brouillons = actives.mapped("mission_ids").filtered(
                    lambda m: m.etat == "brouillon")
                brouillons.unlink()
                journal.append(_("%s étude(s) Braignak arrêtées") % len(actives))
            # Déposer l'ordre hôte
            self._deposer_ordre_braignak_stop()
            icp.set_param("tour_braignak.actif", "False")
            journal.append(_("Braignak désactivé"))

        # 3. Bascule automatique sur DeepSeek
        if icp.get_param("tour_copilote.fournisseur") != "deepseek":
            try:
                self._tester_cle("deepseek")
                icp.set_param("tour_copilote.fournisseur", "deepseek")
                journal.append(_("Copilote basculé sur DeepSeek"))
            except Exception:
                _logger.warning("COMPROMISSION : bascule DeepSeek impossible")

        message = _("Procédure de compromission exécutée.\n• %s") % "\n• ".join(journal)
        _logger.warning("COMPROMISSION exécutée par %s : %s",
                        self.env.user.login, "; ".join(journal))
        return self._notifier(message, "danger")

    def _deposer_ordre_braignak_stop(self):
        """Dépose l'ordre de suppression de l'autorisation Braignak côté hôte."""
        try:
            import os, tempfile
            ordres = "/mnt/atelier/ordres"
            if os.path.isdir(ordres) and os.access(ordres, os.W_OK):
                fd, path = tempfile.mkstemp(dir=ordres, prefix="compromission-", suffix=".ordre")
                os.close(fd)
                dest = os.path.join(ordres, "braignak-stop.ordre")
                os.rename(path, dest)
                _logger.warning("COMPROMISSION : ordre braignak-stop depose")
        except Exception:
            _logger.exception("COMPROMISSION : impossible de deposer l'ordre stop")

    def _notifier(self, message, notif_type="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"message": message, "type": notif_type,
                       "next": {"type": "ir.actions.act_window_close"}},
        }
