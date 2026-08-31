# -*- coding: utf-8 -*-
"""Décrire un site, obtenir une adresse vivante.

Première marche vers la promesse de la v1, volontairement étroite : une page
statique autonome, sans base de données, sans compte, sans processus qui tourne.
C'est précisément ce qui rend l'isolation simple — il n'y a rien à exécuter, le
serveur web se contente de servir des fichiers.

Le bac à sable complet (conteneur jetable pour compiler de vrais projets) reste
à construire ; il ne devient nécessaire que le jour où l'on générera des projets
qui doivent être compilés.
"""
import logging
import os
import re
import shutil

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

RACINE = "/srv/sites"
MAX_OCTETS = 400_000

CONSIGNE = """Tu produis une page web complète et autonome.

CONTRAINTES ABSOLUES :
- Un seul fichier HTML. Tout le style dans une balise <style>, tout le
  comportement dans une balise <script>. AUCUNE ressource externe : pas de CDN,
  pas de police distante, pas d'image distante, pas d'appel réseau. Une page qui
  dépend d'un serveur tiers casse le jour où ce serveur change.
- Pour les images, utilise des formes dessinées en SVG intégré ou des aplats de
  couleur. Jamais de lien vers une image que tu n'as pas.
- Responsive : lisible sur téléphone comme sur écran large.
- Accessible : contrastes suffisants, textes alternatifs, structure de titres
  cohérente.

QUALITÉ :
- Évite l'esthétique générique : pas de polices système par défaut, pas de
  dégradé violet sur fond blanc, pas de mise en page interchangeable. Donne un
  caractère au site, cohérent avec ce qu'il raconte.
- Le contenu doit être crédible et spécifique au sujet demandé. Pas de texte de
  remplissage en latin, pas de « Lorem ipsum », pas de « Votre texte ici ».

RÉPONSE :
Renvoie UNIQUEMENT le code HTML, en commençant par <!DOCTYPE html>. Aucune
explication avant ou après, aucun bloc de code entouré de balises.

DEMANDE :
%(demande)s
"""


class SiteGenere(models.Model):
    _name = "site.genere"
    _description = "Site généré"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char("Nom du site", required=True, tracking=True)
    slug = fields.Char("Adresse", readonly=True, copy=False,
                       help="Le morceau d'adresse sous lequel le site est servi.")
    demande = fields.Text(
        "Ce que doit être le site", required=True,
        help="Décrivez-le comme à quelqu'un : à qui il s'adresse, ce qu'il doit "
             "raconter, quel ton. Plus c'est précis, moins il faut recommencer.")
    url = fields.Char("Adresse publique", readonly=True, copy=False)
    etat = fields.Selection(
        [("brouillon", "Brouillon"), ("en_ligne", "En ligne"),
         ("echec", "Échec")],
        string="État", default="brouillon", readonly=True, tracking=True)
    taille = fields.Integer("Taille (octets)", readonly=True)
    message = fields.Char("Dernier message", readonly=True)

    # ------------------------------------------------------------------
    @api.model
    def _fabriquer_slug(self, nom):
        base = re.sub(r"[^a-z0-9]+", "-", (nom or "site").lower()).strip("-")[:40]
        base = base or "site"
        existant = self.sudo().search([("slug", "=like", base + "%")])
        pris = set(existant.mapped("slug"))
        if base not in pris:
            return base
        n = 2
        while "%s-%s" % (base, n) in pris:
            n += 1
        return "%s-%s" % (base, n)

    def action_generer(self):
        """Produit la page et la met en ligne."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        cle = (icp.get_param("tour_copilote.api_key") or "").strip()
        if not cle:
            raise UserError(_("Aucune clé d'API configurée."))

        try:
            import anthropic
        except ImportError:
            raise UserError(_("Le paquet anthropic est absent de l'image."))

        # Le quota du copilote s'applique : générer un site coûte comme le reste.
        self.env["copilote.usage"].verifier_avant_appel(self.env.user)

        modele = (icp.get_param("tour_copilote.model") or "claude-opus-4-8").strip()
        client = anthropic.Anthropic(api_key=cle, timeout=180.0, max_retries=1)
        try:
            reponse = client.messages.create(
                model=modele, max_tokens=16000,
                messages=[{"role": "user",
                           "content": CONSIGNE % {"demande": self.demande}}])
        except Exception as exc:  # noqa: BLE001
            self.write({"etat": "echec", "message": str(exc)[:200]})
            raise UserError(_("La génération a échoué : %s", str(exc)[:200]))

        try:
            self.env["copilote.usage"].enregistrer(self.env.user, reponse.usage, modele)
        except Exception:  # noqa: BLE001 — la mesure ne bloque jamais
            pass

        html = "".join(b.text for b in reponse.content if b.type == "text").strip()
        # Le modèle entoure parfois sa réponse de balises de code malgré la
        # consigne : on les retire plutôt que de servir une page cassée.
        html = re.sub(r"^```(?:html)?\s*|\s*```$", "", html).strip()
        if "<!DOCTYPE" not in html[:200].upper() and "<HTML" not in html[:200].upper():
            self.write({"etat": "echec",
                        "message": _("La réponse ne ressemble pas à une page HTML.")})
            raise UserError(_("La réponse ne ressemble pas à une page HTML."))
        if len(html.encode()) > MAX_OCTETS:
            html = html[:MAX_OCTETS]

        if not self.slug:
            self.slug = self._fabriquer_slug(self.name)

        dossier = os.path.join(RACINE, self.slug)
        try:
            os.makedirs(dossier, exist_ok=True)
            with open(os.path.join(dossier, "index.html"), "w", encoding="utf-8") as f:
                f.write(html)
        except OSError as exc:
            self.write({"etat": "echec", "message": str(exc)[:200]})
            raise UserError(_(
                "Impossible d'écrire le site sur le disque (%s). Vérifier que le "
                "dossier des sites est bien monté dans le conteneur.", exc))

        base = (icp.get_param("web.base.url") or "").rstrip("/")
        self.write({
            "url": "%s/sites/%s/" % (base, self.slug),
            "etat": "en_ligne",
            "taille": len(html.encode()),
            "message": _("Généré avec %s", modele),
        })
        self.message_post(body=_("Site mis en ligne : %s", self.url))
        return self.action_ouvrir()

    def action_ouvrir(self):
        self.ensure_one()
        if not self.url:
            return False
        return {"type": "ir.actions.act_url", "url": self.url, "target": "new"}

    def unlink(self):
        """Supprimer la fiche retire aussi les fichiers : pas de site orphelin."""
        for site in self:
            if site.slug:
                shutil.rmtree(os.path.join(RACINE, site.slug), ignore_errors=True)
        return super().unlink()
