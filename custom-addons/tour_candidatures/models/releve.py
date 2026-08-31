# -*- coding: utf-8 -*-
"""Le relevé de la boîte : quand ils répondent, la fiche le sait.

Sans ça, le module des candidatures est un carnet : Patrick voit la réponse
dans Gmail, et la fiche continue de compter les jours de silence comme si
personne n'avait écrit. Un compteur qui ment est pire qu'un compteur absent —
« 32 jours de silence » alors qu'ils ont répondu hier fait rater une relance.

Ce que ça fait, une fois par heure : pour chaque candidature vivante, chercher
dans la boîte les messages ARRIVÉS APRÈS l'envoi, venant du contact noté ou du
domaine de l'entreprise. Si on en trouve un plus récent que la dernière
nouvelle connue, on met la date à jour et on écrit le sujet dans le fil de la
fiche.

Ce que ça NE fait PAS, volontairement : changer l'état. « Accusé de réception »,
« entretien », « refusée » — c'est une lecture humaine, un robot qui décide à
la place se trompe et efface une information juste. On note la date et le
sujet ; Patrick tranche.

Le mot de passe d'application vit dans le coffre, jamais dans ce fichier.
"""
import email
import imaplib
import logging
import re
from email.header import decode_header
from email.utils import parsedate_to_datetime

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Ce qu'on ne suit jamais : les alertes d'offres ne sont pas des réponses.
BRUIT = ("noreply@linkedin", "jobalerts", "notifications-noreply",
         "updates-noreply", "messages-noreply@linkedin")


def _texte(brut):
    """Un en-tête de courriel peut être encodé. On le rend lisible."""
    if not brut:
        return ""
    morceaux = []
    for valeur, code in decode_header(brut):
        if isinstance(valeur, bytes):
            try:
                morceaux.append(valeur.decode(code or "utf-8", "replace"))
            except LookupError:
                morceaux.append(valeur.decode("utf-8", "replace"))
        else:
            morceaux.append(valeur)
    return " ".join(morceaux).strip()


class CandidatureReleve(models.Model):
    _inherit = "candidature.fiche"

    @api.model
    def _identifiants_boite(self):
        """Le login et le mot de passe d'application, lus dans le coffre.

        On cherche la fiche par son libellé : celle qui parle de la boîte où
        arrivent les candidatures. Rien n'est écrit en dur ici.
        """
        V = self.env["vault.secret"].sudo()
        fiche = V.search([("name", "ilike", "candidatures"),
                          ("categorie", "=", "api")], limit=1)
        if not fiche:
            fiche = V.search([("name", "ilike", "boite des candidatures")], limit=1)
        if not fiche or not fiche.secret_chiffre or not fiche.identifiant:
            return None, None
        try:
            mdp = V._fernet().decrypt(fiche.secret_chiffre.encode()).decode()
        except Exception:
            _logger.warning("Relevé : le secret de la boîte est illisible.")
            return None, None
        return fiche.identifiant, mdp.replace(" ", "")

    @api.model
    def _cron_relever_la_boite(self):
        """Une fois par heure. Ne conclut rien quand il ne peut pas lire."""
        login, mdp = self._identifiants_boite()
        if not login or not mdp:
            _logger.info(
                "Relevé : aucun identifiant dans le coffre (fiche « Boîte des "
                "candidatures »). Rien relevé — et surtout rien conclu.")
            return 0

        vivantes = self.search([("etat", "in",
                                 ("envoyee", "accusee", "entretien", "offre"))])
        if not vivantes:
            return 0

        try:
            boite = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            boite.login(login, mdp)
            boite.select("INBOX")
        except Exception as exc:
            _logger.warning("Relevé : boîte injoignable (%s). Rien conclu.", exc)
            return 0

        touchees = self.browse()
        try:
            for fiche in vivantes:
                if fiche._relever_une(boite):
                    touchees |= fiche
        finally:
            try:
                boite.logout()
            except Exception:
                pass
        if touchees:
            self._prevenir_par_courriel(touchees)
        _logger.info("Relevé : %d fiche(s) mise(s) à jour sur %d vivantes.",
                     len(touchees), len(vivantes))
        return len(touchees)

    @api.model
    def _prevenir_par_courriel(self, fiches):
        """Un seul courriel par passage, qui dit qui a répondu.

        Écrire dans le fil d'une fiche suppose qu'on ouvre la fiche — donc
        qu'on sait déjà qu'il s'est passé quelque chose. Le courriel fait
        l'inverse : il vient chercher Patrick.

        Un seul message pour tout le passage : trois courriels d'affilée se
        lisent comme du bruit, et le bruit finit en règle de filtrage.
        """
        lignes = []
        for f in fiches:
            lignes.append(
                "<li><b>%s</b> — %s<br/>"
                "<span style='color:#5b6b83'>répondu le %s · "
                "état noté : %s</span></li>" % (
                    f.entreprise or "?", f.name or "?",
                    f.derniere_nouvelle.strftime("%d/%m/%Y")
                    if f.derniere_nouvelle else "?",
                    dict(f._fields["etat"].selection).get(f.etat, f.etat)))
        corps = (
            "<p><b>%d réponse(s) trouvée(s) dans la boîte.</b></p><ul>%s</ul>"
            "<p>L'état n'a pas été changé : savoir si c'est un accusé, un "
            "entretien ou un refus se lit à l'œil. Le compteur de silence, "
            "lui, est reparti de zéro.</p>"
            "<p>Les fiches : "
            "<a href='%s/odoo/action-818'>Mes candidatures</a></p>"
        ) % (len(fiches), "".join(lignes),
             (self.env["ir.config_parameter"].sudo().get_param("web.base.url")
              or "").rstrip("/"))
        try:
            self.env["mail.mail"].sudo().create({
                "subject": "Candidatures : %d réponse(s) reçue(s)" % len(fiches),
                "body_html": corps,
                "email_to": "fotsoorel95@gmail.com",
                "email_from": "contact@matourdecontrole.fr",
            }).send()
        except Exception as exc:
            # Un courriel qui ne part pas ne doit jamais faire perdre le relevé
            # lui-même : les dates sont déjà enregistrées, c'est l'essentiel.
            _logger.warning("Relevé : courriel non parti (%s).", exc)

    def _relever_une(self, boite):
        """Cherche une réponse pour CETTE candidature. Rend True si trouvée."""
        self.ensure_one()
        depuis = (self.derniere_nouvelle or self.date_envoi)
        if not depuis:
            return False

        # Qui peut nous écrire : le contact noté, ou le domaine de l'entreprise.
        pistes = []
        if self.contact_mail:
            pistes.append(self.contact_mail.strip())
        domaine = re.sub(r"[^a-z0-9]", "", (self.entreprise or "").lower())
        if len(domaine) > 3:
            pistes.append(domaine)
        if not pistes:
            return False

        depuis_imap = fields.Date.to_date(depuis).strftime("%d-%b-%Y")
        vus = []
        for piste in pistes:
            try:
                typ, data = boite.search(None, "SINCE", depuis_imap, "FROM", piste)
            except Exception:
                continue
            if typ == "OK" and data and data[0]:
                vus.extend(data[0].split())
        if not vus:
            return False

        meilleure_date, meilleur_sujet, meilleur_de = None, "", ""
        for num in vus[-20:]:
            try:
                typ, brut = boite.fetch(num, "(BODY.PEEK[HEADER])")
                if typ != "OK" or not brut or not brut[0]:
                    continue
                msg = email.message_from_bytes(brut[0][1])
            except Exception:
                continue
            expediteur = _texte(msg.get("From"))
            if any(b in expediteur.lower() for b in BRUIT):
                continue
            try:
                quand = parsedate_to_datetime(msg.get("Date")).date()
            except Exception:
                continue
            if meilleure_date is None or quand > meilleure_date:
                meilleure_date = quand
                meilleur_sujet = _texte(msg.get("Subject"))
                meilleur_de = expediteur

        if not meilleure_date or meilleure_date <= fields.Date.to_date(depuis):
            return False

        self.derniere_nouvelle = meilleure_date
        self.message_post(body=_(
            "<p><b>Ils ont répondu le %(quand)s.</b></p>"
            "<p>De : %(de)s<br/>Objet : %(sujet)s</p>"
            "<p><i>Relevé automatiquement dans la boîte. L'état n'a pas été "
            "changé : c'est une lecture humaine.</i></p>"
        ) % {"quand": meilleure_date.strftime("%d/%m/%Y"),
             "de": meilleur_de or "?", "sujet": meilleur_sujet or "(sans objet)"})
        return True
