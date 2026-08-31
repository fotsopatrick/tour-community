# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

SERVICE = "http://172.17.0.1:3212"
TOKEN_FICHIER = "/mnt/atelier/.conteneurs-token"


class PageConteneurs(http.Controller):

    def _token(self):
        try:
            with open(TOKEN_FICHIER, encoding="utf-8") as f:
                return (f.read().strip() or "")
        except OSError:
            return ""

    def _appeler(self, chemin, post=False):
        import urllib.request
        import urllib.error
        import json as jsonlib
        jeton = self._token()
        if not jeton:
            return {"error": "jeton introuvable (hôte)"}
        url = SERVICE + chemin
        try:
            if post:
                req = urllib.request.Request(
                    url, data=b"", method="POST",
                    headers={"X-TOKEN": jeton})
            else:
                req = urllib.request.Request(url, headers={"X-TOKEN": jeton})
            with urllib.request.urlopen(req, timeout=15) as r:
                return jsonlib.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                return jsonlib.loads(exc.read().decode("utf-8"))
            except Exception:  # noqa: BLE001
                return {"error": "service hôte : HTTP %s" % exc.code}
        except Exception as exc:  # noqa: BLE001
            return {"error": "service hôte indisponible (%s)" % exc}

    @http.route("/tour/conteneurs", type="http", auth="user", website=False)
    def page(self, **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        data = self._appeler("/conteneurs")
        conteneurs = data.get("conteneurs") if isinstance(data, dict) else []
        return request.render("tour_conteneurs.page_conteneurs", {
            "conteneurs": conteneurs,
            "erreur": data.get("error") if isinstance(data, dict) else None,
        })

    @http.route("/tour/conteneurs/<nom>/<action>", type="http", auth="user",
                website=False, methods=["POST"])
    def agir(self, nom, action, **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        if action not in ("start", "stop"):
            return request.redirect("/tour/conteneurs")
        import urllib.parse
        self._appeler("/tour/%s/%s" % (urllib.parse.quote(nom), action), post=True)
        return request.redirect("/tour/conteneurs")
