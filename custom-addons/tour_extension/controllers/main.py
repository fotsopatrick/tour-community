# -*- coding: utf-8 -*-
"""Le pont navigateur : page de téléchargement + test de l'extension.

Le problème : les moteurs de recherche bloquent le VPS (datacenter). Braignak,
dont le métier est d'observer le web, ne peut pas chercher. L'extension fait
la recherche DANS LE NAVIGATEUR de Patrick (session humaine réelle) et renvoie
le résultat.

La page `/tour/extension` est protégée par un mot de passe (par défaut 3173,
modifiable depuis Réglages) : c'est un outil d'ADMIN, pas une page publique.
Elle permet de télécharger l'extension (zip) et donne la page de test.

GARDE-FOU ABSOLU (règle n°1, 31/07) : l'extension ne lit JAMAIS la session
privée de Patrick. Elle n'ouvre que la recherche demandée, et elle n'a aucune
permission sur les onglets existants ni l'historique.
"""
import io
import zipfile

from odoo import fields, http
from odoo.http import request

PARAM_MDP = "tour_extension.mdp"


class TourExtension(http.Controller):

    def _mdp(self):
        icp = request.env["ir.config_parameter"].sudo()
        return (icp.get_param(PARAM_MDP, "3173") or "3173").strip()

    def _mdp_ok(self, kw):
        saisi = (kw.get("mdp") or "").strip()
        return saisi == self._mdp()

    def _render(self, kw, message=None, erreur=None, telechargement=False):
        values = {
            "mdp_ok": self._mdp_ok(kw),
            "telechargement": telechargement,
            "message": message,
            "erreur": erreur,
            "mdp": kw.get("mdp") or "",
            "page": "extension",
        }
        return request.render("tour_extension.page_extension", values)

    @http.route("/tour/extension", type="http", auth="user", website=False)
    def extension(self, **kw):
        # POST = déverrouillage avec mot de passe, ou téléchargement.
        if request.httprequest.method == "POST":
            if kw.get("action") == "telecharger":
                if not self._mdp_ok(kw):
                    return self._render(kw, erreur="Mot de passe incorrect.")
                zip_data = self._construire_zip()
                return request.make_response(
                    zip_data,
                    headers=[
                        ("Content-Type", "application/zip"),
                        ("Content-Disposition",
                         'attachment; filename="tour-extension.zip"'),
                    ])
            # Sinon : déverrouillage de la page (mot de passe saisi).
            if self._mdp_ok(kw):
                return self._render(kw, telechargement=True)
            return self._render(kw, erreur="Mot de passe incorrect.")
        return self._render(kw)

    @http.route("/tour/extension/test", type="http", auth="user", website=False)
    def extension_test(self, **kw):
        # La page de test de l'extension. Aussi protégée : même mot de passe.
        if not self._mdp_ok(kw):
            # Redirige vers la page principale pour saisir le mot de passe.
            return request.redirect("/tour/extension?mdp=" + (kw.get("mdp") or ""))
        test = self._fichier("test.html")
        return request.make_response(
            test, headers=[("Content-Type", "text/html; charset=utf-8")])

    # ------------------------------------------------------------------
    def _construire_zip(self):
        """Assemble l'extension (manifest, content, background, extract, test)
        en un zip téléchargeable."""
        fichiers = {
            "manifest.json": self._fichier("manifest.json"),
            "content.js": self._fichier("content.js"),
            "background.js": self._fichier("background.js"),
            "search-extract.js": self._fichier("search-extract.js"),
            "test.html": self._fichier("test.html"),
        }
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for nom, contenu in fichiers.items():
                z.writestr("tour-extension/%s" % nom, contenu)
        return buf.getvalue()

    def _fichier(self, nom):
        """Lit un fichier de l'extension depuis le module (static/src/extension/)."""
        import os
        base = os.path.join(os.path.dirname(__file__), "..", "static", "src", "extension")
        chemin = os.path.join(base, nom)
        if not os.path.exists(chemin):
            return ""
        with open(chemin, "r", encoding="utf-8") as f:
            return f.read()
