# -*- coding: utf-8 -*-
"""Boîte mail surveillée.

Chacun branche la sienne. Le mot de passe n'est jamais saisi ni stocké ici :
il vit dans le Coffre, et on n'en garde qu'une référence. Une boîte mail
appartient à une personne — même un administrateur ne lit pas celle d'un autre.
"""
import email
import imaplib
import logging
import re
from email.header import decode_header, make_header

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Une notification Jira porte la clé du ticket dans le sujet, entre crochets.
RE_CLE = re.compile(r"\[(?:JIRA\]?\s*)?\(?([A-Z][A-Z0-9_]+-\d+)\)?\]?")
RE_CLE_SIMPLE = re.compile(r"\b([A-Z][A-Z0-9_]{1,9}-\d+)\b")


class DevBoite(models.Model):
    _name = "dev.boite"
    _description = "Boîte mail surveillée"
    _rec_name = "adresse"

    adresse = fields.Char("Adresse surveillée", required=True)
    user_id = fields.Many2one("res.users", string="Propriétaire", required=True,
                              default=lambda self: self.env.user,
                              ondelete="cascade", index=True)
    secret_id = fields.Many2one(
        "vault.secret", string="Mot de passe (Coffre)", required=True,
        help="La fiche du Coffre qui contient le mot de passe d'application. "
             "Le mot de passe lui-même n'est jamais stocké ici.")
    serveur = fields.Char("Serveur IMAP", default="imap.gmail.com", required=True)
    port = fields.Integer("Port", default=993, required=True)
    expediteur = fields.Char(
        "Filtre expéditeur", default="atlassian.net", required=True,
        help="Ne relever que les messages venant de ces adresses ou domaines. "
             "Plusieurs valeurs séparées par des virgules. "
             "Obligatoire : sans lui, toute la boîte remonte.")
    plafond = fields.Integer(
        "Maximum par relève", default=20,
        help="Garde-fou : au-delà, la relève s'arrête et le signale plutôt que "
             "de créer des centaines de fiches d'un coup.")
    actif = fields.Boolean("Actif", default=True)
    derniere_releve = fields.Datetime("Dernière relève", readonly=True)
    dernier_message = fields.Char("Dernier état", readonly=True)
    nb_tickets = fields.Integer("Tickets remontés", compute="_compute_nb")

    def _compute_nb(self):
        Ticket = self.env["dev.ticket"]
        for rec in self:
            rec.nb_tickets = Ticket.search_count([("boite_id", "=", rec.id)])

    # ------------------------------------------------------------------
    @staticmethod
    def _decoder(valeur):
        if not valeur:
            return ""
        try:
            return str(make_header(decode_header(valeur)))
        except Exception:  # noqa: BLE001 — un sujet mal encodé ne bloque rien
            return str(valeur)

    @api.model
    def _extraire_cle(self, sujet):
        for regex in (RE_CLE, RE_CLE_SIMPLE):
            trouve = regex.search(sujet or "")
            if trouve:
                return trouve.group(1)
        return False

    @api.model
    def _corps_texte(self, message):
        """Texte brut du message, sans les pièces jointes ni le HTML."""
        if not message.is_multipart():
            charge = message.get_payload(decode=True) or b""
            return charge.decode(message.get_content_charset() or "utf-8",
                                 errors="replace")
        for partie in message.walk():
            if partie.get_content_type() == "text/plain":
                charge = partie.get_payload(decode=True) or b""
                return charge.decode(partie.get_content_charset() or "utf-8",
                                     errors="replace")
        return ""

    # ------------------------------------------------------------------
    def action_relever(self):
        """Relève les messages non lus et crée les tickets manquants.

        Ne marque JAMAIS un message comme lu dans la boîte : la tour observe,
        elle ne touche pas à la messagerie de la personne. Le suivi de ce qui
        a déjà été traité se fait de notre côté, par identifiant de message.
        """
        for boite in self:
            try:
                nouveaux = boite._relever_une()
                boite.write({
                    "derniere_releve": fields.Datetime.now(),
                    "dernier_message": _("%s nouveau(x) ticket(s)", nouveaux),
                })
            except Exception as exc:  # noqa: BLE001
                _logger.exception("Dev : releve de %s en echec", boite.adresse)
                boite.write({
                    "derniere_releve": fields.Datetime.now(),
                    "dernier_message": _("Échec : %s", str(exc)[:180]),
                })
        return True

    def _critere_imap(self):
        """Le critère de recherche IMAP, pour un ou plusieurs expéditeurs.

        IMAP n'a pas de « FROM parmi cette liste » : il faut composer avec
        l'opérateur OR, qui est PRÉFIXÉ et strictement binaire. Pour trois
        adresses a, b, c, cela s'écrit « OR FROM a OR FROM b FROM c » — chaque
        OR supplémentaire s'empile devant, jamais entre.
        """
        self.ensure_one()
        adresses = [a.strip() for a in (self.expediteur or "").split(",") if a.strip()]
        if not adresses:
            # Ne doit pas arriver (le champ est obligatoire), mais si ça
            # arrivait, tout relever serait exactement l'accident du 25/07.
            raise UserError(_("Aucun filtre expéditeur : relève refusée."))
        if len(adresses) == 1:
            return '(UNSEEN FROM "%s")' % adresses[0]
        morceaux = 'FROM "%s"' % adresses[-1]
        for adresse in reversed(adresses[:-1]):
            morceaux = 'OR FROM "%s" %s' % (adresse, morceaux)
        return "(UNSEEN %s)" % morceaux

    def _relever_une(self):
        self.ensure_one()
        mdp = self.secret_id.sudo().lire_secret()
        if not mdp:
            raise UserError(_("La fiche du Coffre « %s » ne contient aucun "
                              "mot de passe.", self.secret_id.display_name))

        Ticket = self.env["dev.ticket"].sudo()
        connus = set(Ticket.search([("boite_id", "=", self.id)]).mapped("message_id"))
        nouveaux = 0

        connexion = imaplib.IMAP4_SSL(self.serveur, self.port)
        try:
            connexion.login(self.adresse, mdp)
            connexion.select("INBOX", readonly=True)  # readonly : rien n'est marqué lu
            critere = self._critere_imap()
            code, donnees = connexion.search(None, critere)
            if code != "OK":
                return 0

            trouves = (donnees[0] or b"").split()
            plafond = self.plafond or 20
            if len(trouves) > plafond:
                # On préfère ne rien faire et le dire, plutôt que d'inonder la
                # personne. Le 25/07, 97 messages ont produit 97 notifications.
                raise UserError(_(
                    "%(n)s messages correspondent au filtre, au-delà du "
                    "maximum de %(max)s. Affinez le filtre expéditeur ou "
                    "relevez votre boîte avant de recommencer.",
                    n=len(trouves), max=plafond))

            for num in trouves[-plafond:]:
                code, brut = connexion.fetch(num, "(BODY.PEEK[])")
                if code != "OK" or not brut or not brut[0]:
                    continue
                message = email.message_from_bytes(brut[0][1])
                mid = self._decoder(message.get("Message-ID")) or str(num)
                if mid in connus:
                    continue

                sujet = self._decoder(message.get("Subject"))
                corps = self._corps_texte(message)
                cle = self._extraire_cle(sujet) or self._extraire_cle(corps)

                Ticket.create({
                    "boite_id": self.id,
                    "user_id": self.user_id.id,
                    "message_id": mid,
                    "cle": cle or False,
                    "name": sujet or _("(sans objet)"),
                    "expediteur": self._decoder(message.get("From")),
                    "contenu": corps[:6000],
                    "reconnu": bool(cle),
                })
                connus.add(mid)
                nouveaux += 1
        finally:
            try:
                connexion.logout()
            except Exception:  # noqa: BLE001
                pass
        return nouveaux

    @api.model
    def _cron_relever(self):
        self.sudo().search([("actif", "=", True)]).action_relever()
