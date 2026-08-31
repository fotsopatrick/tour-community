# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

SERVICE = "http://172.17.0.1:3213"
TOKEN_FICHIER = "/mnt/atelier/.mvp-token"


class PageMvp(http.Controller):

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
        try:
            if post:
                req = urllib.request.Request(
                    SERVICE + chemin, data=b"", method="POST",
                    headers={"X-TOKEN": jeton})
            else:
                req = urllib.request.Request(
                    SERVICE + chemin, headers={"X-TOKEN": jeton})
            with urllib.request.urlopen(req, timeout=15) as r:
                return jsonlib.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                return jsonlib.loads(exc.read().decode("utf-8"))
            except Exception:  # noqa: BLE001
                return {"error": "HTTP %s" % exc.code}
        except Exception as exc:  # noqa: BLE001
            return {"error": "service hôte indisponible (%s)" % exc}

    @http.route("/tour/mvp", type="http", auth="user", website=False)
    def page(self, **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        statut = self._appeler("/status")
        return request.render("tour_mvp.page_mvp", {
            "journal": statut.get("journal", "") if isinstance(statut, dict) else "",
            "erreur": statut.get("error") if isinstance(statut, dict) else None,
        })

    @http.route("/tour/mvp/install", type="http", auth="user",
                website=False, methods=["POST"])
    def install(self, **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        self._appeler("/install", post=True)
        return request.redirect("/tour/mvp")
