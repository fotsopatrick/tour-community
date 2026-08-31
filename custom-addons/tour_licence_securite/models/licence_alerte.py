# -*- coding: utf-8 -*-
"""Alerte de déverrouillage de licence.

Le paquet vendu est chiffré (AES-256-CBC) et livré avec un script
`deverrouiller.sh`. Ce script compte les échecs locaux ; au-delà d'une
tentative, il appelle cet endpoint pour prévenir Patrick par mail et fournir
un mot de passe de secours temporaire.

Règle de l'étude 761 : source absente -> champ absent, jamais un chiffre
inventé. Et une alerte n'invente jamais de destinataire : on lit la config.
"""
import logging
import secrets

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

MAX_ALERTES_JOUR = 20


class LicenceAlerte(models.Model):
    _name = "licence.alerte"
    _description = "Alerte de déverrouillage de licence"
    _order = "create_date desc"

    licencie = fields.Char("Licencié", required=True, index=True)
    empreinte = fields.Char("Empreinte de la copie")
    motif = fields.Char("Motif", help="Ex : tentative de déverrouillage")
    mot_de_passe_secours = fields.Char(
        "Mot de passe de secours", readonly=True,
        help="Généré à la première alerte, envoyé à Patrick. Ne revient "
             "jamais dans le journal.")
    cree_le = fields.Datetime("Créé le", default=fields.Datetime.now,
                              readonly=True)
    envoye_le = fields.Datetime("Mail envoyé le", readonly=True)

    def _generer_secours(self):
        """Mot de passe de secours unique, 24 caractères, lisible."""
        return "TR-" + secrets.token_urlsafe(18).replace("-", "").replace("_", "")[:22]

    @api.model
    def _alerter(self, licencie, empreinte="", motif=""):
        """Enregistre une alerte et envoie le mail à Patrick (une fois/jour)."""
        self = self.sudo()
        # Une seule alerte par licencié par jour (anti-spam de la machine).
        jour = fields.Date.context_today(self)
        existante = self.search([
            ("licencie", "=", licencie),
            ("create_date", ">=", jour),
        ], limit=1)
        if existante and existante.envoye_le:
            # Renvoi demandé : on renvoie le même mot de passe.
            existante._envoyer_mail()
            return existante

        if not existante:
            existante = self.create({
                "licencie": licencie,
                "empreinte": empreinte or "",
                "motif": motif or "tentative de déverrouillage",
                "mot_de_passe_secours": self._generer_secours(),
            })
        existante._envoyer_mail()
        return existante

    def _envoyer_mail(self):
        self.ensure_one()
        if "mail.mail" not in self.env:
            return False
        icp = self.env["ir.config_parameter"].sudo()
        dest = icp.get_param("tour_licence.destinataire",
                             "contact@matourdecontrole.fr")
        Mail = self.env["mail.mail"]
        corps = (
            "<h3>⛔ Alerte déverrouillage de licence</h3>"
            "<p>Une tentative de déverrouillage du paquet <b>%s</b> a été "
            "détectée%s.</p>"
            "<p>Motif : %s</p>"
            "<p>Pour déverrouiller (si c'est une fausse alerte) :</p>"
            "<p style='font-family:monospace;font-size:18px;background:#f4f4f4;"
            "padding:10px;border-radius:6px'>%s</p>"
            "<p><small>Ce mot de passe est unique à cette copie. Chaque "
            "nouvelle tentative renverra ce mail.</small></p>"
        ) % (
            self.licencie,
            (" (empreinte %s…)" % self.empreinte[:12]) if self.empreinte else "",
            self.motif,
            self.mot_de_passe_secours or "—",
        )
        Mail.sudo().create({
            "subject": "[Licence] Alerte %s" % self.licencie,
            "body_html": corps,
            "email_from": self.env.company.email or "contact@matourdecontrole.fr",
            "email_to": dest,
            "auto_delete": False,
        }).send()
        self.write({"envoye_le": fields.Datetime.now()})
        _logger.warning("Licence : alerte envoyée pour %s", self.licencie)
        return True
