# -*- coding: utf-8 -*-
"""Flux RSS/Atom : un centre d'intérêt = un ou plusieurs flux gratuits.

Parsing en bibliothèque standard uniquement (urllib + ElementTree) pour
ne pas ajouter de dépendance pip à l'image Docker.
"""
import logging
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

MEDIA_NS = "{http://search.yahoo.com/mrss/}"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
MAX_PAR_FLUX = 15
RETENTION_JOURS = 7
TAG_RE = re.compile(r"<[^>]+>")


class ActusFlux(models.Model):
    _name = "actus.flux"
    _description = "Flux d'actualités"
    _order = "categorie, name"

    name = fields.Char("Source", required=True)
    url = fields.Char("URL du flux (RSS/Atom)", required=True)
    categorie = fields.Char("Centre d'intérêt", required=True,
                            help="Ex : Tech, Économie, France, Sciences… Les onglets du fil sont créés à partir de cette valeur.")
    # La langue est portée par la SOURCE, pas devinée article par article :
    # détecter la langue d'un titre de dix mots se trompe trop souvent, et
    # un flux ne change jamais de langue. Trois langues au départ (28/07) —
    # on en ajoute une en ajoutant une valeur ici et des sources.
    langue = fields.Selection(
        [("fr", "Français"), ("en", "English"), ("es", "Español")],
        "Langue", default="fr", required=True)
    actif = fields.Boolean("Suivi", default=True,
                           help="Décoche pour ne plus recevoir les actus de cette source.")
    derniere_maj = fields.Datetime("Dernière relève", readonly=True)
    article_ids = fields.One2many("actus.article", "flux_id", string="Articles")

    # ------------------------------------------------------------------
    # Relève des flux
    # ------------------------------------------------------------------
    def action_rafraichir(self):
        for flux in self:
            # POINT DE REPRISE PAR FLUX (05/08). Avant, le `except` attrapait
            # bien l'erreur — mais sans annuler la transaction. PostgreSQL la
            # laissait morte, et TOUS les flux suivants echouaient avec
            # « current transaction is aborted ». Un seul lien en double a
            # ainsi fige toutes les actualites pendant six jours, en silence.
            # Le savepoint annule ce qui casse pour CE flux, et pour lui seul.
            try:
                with self.env.cr.savepoint():
                    flux._relever()
            except Exception as exc:
                _logger.warning("Actus : échec de la relève de %s (%s)", flux.name, exc)
        self.env["actus.article"].sudo().search([
            ("date_pub", "<", fields.Datetime.now() - timedelta(days=RETENTION_JOURS)),
        ]).unlink()
        return True

    @api.model
    def _cron_rafraichir(self):
        self.search([("actif", "=", True)]).action_rafraichir()

    def _relever(self):
        self.ensure_one()
        req = Request(self.url, headers={"User-Agent": "TourDeControle/1.0 (+actus)"})
        with urlopen(req, timeout=15) as resp:
            racine = ElementTree.fromstring(resp.read())

        entrees = racine.findall(".//item") or racine.findall(f".//{ATOM_NS}entry")
        Article = self.env["actus.article"].sudo()
        # Les liens deja connus se cherchent sur TOUS les flux, pas seulement
        # le sien : la contrainte d'unicite porte sur `lien` pour toute la
        # table. Une depeche reprise par deux sources faisait sinon exploser
        # la creation — c'est ce qui cassait « Hugging Face Blog ».
        liens_page = [self._parser_entree(e) for e in entrees[:MAX_PAR_FLUX]]
        liens_page = [v["lien"] for v in liens_page if v]
        connus = set(Article.search([("lien", "in", liens_page)]).mapped("lien"))
        for entree in entrees[:MAX_PAR_FLUX]:
            valeurs = self._parser_entree(entree)
            if not valeurs or valeurs["lien"] in connus:
                continue
            # Seconde ceinture : si la creation echoue quand meme (course entre
            # deux releves, contrainte inattendue), on perd UN article, pas le
            # flux entier ni la transaction.
            try:
                with self.env.cr.savepoint():
                    Article.create(dict(valeurs, flux_id=self.id))
            except Exception as exc:
                _logger.warning("Actus : article ignore (%s) : %s",
                                valeurs.get("lien", "?"), exc)
            connus.add(valeurs["lien"])
        self.derniere_maj = fields.Datetime.now()

    def _parser_entree(self, entree):
        def texte(*balises):
            for balise in balises:
                node = entree.find(balise)
                if node is not None and (node.text or "").strip():
                    return node.text.strip()
            return ""

        titre = texte("title", f"{ATOM_NS}title")
        lien = texte("link", f"{ATOM_NS}id")
        if not lien:  # Atom : le lien est un attribut href
            node = entree.find(f"{ATOM_NS}link")
            lien = node.get("href", "") if node is not None else ""
        if not titre or not lien:
            return None

        resume = TAG_RE.sub(" ", texte("description", f"{ATOM_NS}summary", f"{ATOM_NS}content"))
        resume = re.sub(r"\s+", " ", resume).strip()[:300]

        image = ""
        for node in (entree.find(f"{MEDIA_NS}content"), entree.find(f"{MEDIA_NS}thumbnail"), entree.find("enclosure")):
            if node is not None and node.get("url") and "image" in (node.get("type") or "image"):
                image = node.get("url")
                break

        date_pub = fields.Datetime.now()
        brut = texte("pubDate", f"{ATOM_NS}published", f"{ATOM_NS}updated")
        if brut:
            try:
                dt = parsedate_to_datetime(brut)
            except (TypeError, ValueError):
                try:
                    dt = datetime.fromisoformat(brut.replace("Z", "+00:00"))
                except ValueError:
                    dt = None
            if dt is not None:
                date_pub = dt.replace(tzinfo=None) if dt.tzinfo is None else \
                    dt.astimezone(tz=None).replace(tzinfo=None)

        return {
            "name": titre[:250],
            "lien": lien,
            "resume": resume,
            "image_url": image,
            "date_pub": date_pub,
        }
