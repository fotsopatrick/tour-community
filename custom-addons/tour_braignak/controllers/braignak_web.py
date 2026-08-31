# -*- coding: utf-8 -*-
"""Webapp Braignak — la fenêtre dédiée (chat vers études).

Routes appelées par le webapp Node « Braignak » (servi par Caddy sous
/braignak-web). Le navigateur appelle ces routes sur la même origine : le
cookie de session passe tout seul, Odoo identifie l'utilisateur, et chacun ne
voit que ses études (champ demandeur_id).

- POST /braignak/web/demander   : crée l'étude + lance la mission directement
  (c'est la fenêtre dédiée à Braignak : pas de brouillon à envoyer).
- GET  /braignak/web/etudes     : la liste des études du demandeur.
- GET  /braignak/web/etude/<id> : le contenu complet d'une étude du demandeur.
"""
import json

from odoo import http
from odoo.http import request


class BraignakWeb(http.Controller):

    @http.route("/braignak/web/demander", type="http", auth="user",
                csrf=False, methods=["POST"])
    def web_demander(self, **kw):
        # Le front (webapp Node) envoie un corps JSON. Pour une route
        # type="http", Odoo ne le repartit pas dans `kw` : on le lit.
        try:
            corps = json.loads(request.httprequest.get_data() or b"{}")
        except Exception:
            corps = {}
        q = (corps.get("question") or kw.get("question") or "").strip()[:300]
        if not q:
            return self._json({"ok": False, "erreur": "Écris une question d'abord."})
        env = request.env
        try:
            etude = env["braignak.etude"].sudo().create({
                "name": q[:80],
                "source": "chat",
                "nature": "mienne",
                "demandeur_id": env.user.id,
            })
            etude._demander_depuis_chat(q, qui=env.user.name)
            return self._json({"ok": True, "id": etude.id})
        except Exception as exc:
            return self._json({"ok": False, "erreur": str(exc)[:250]})

    @http.route("/braignak/web/etudes", type="http", auth="user", csrf=False)
    def web_etudes(self, **kw):
        env = request.env
        etudes = env["braignak.etude"].sudo().search(
            [("demandeur_id", "=", env.user.id)], order="create_date desc")
        return self._json({"ok": True, "etudes": [{
            "id": e.id,
            "name": e.name,
            "etat": e.etat,
            "date": str(e.create_date)[:16],
            "verdict": e.verdict or "",
            "resume": e.resume or "",
        } for e in etudes]})

    @http.route("/braignak/web/etude/<int:eid>", type="http", auth="user",
                csrf=False)
    def web_etude(self, eid, **kw):
        env = request.env
        e = env["braignak.etude"].sudo().browse(eid).exists()
        if not e or e.demandeur_id.id != env.user.id:
            return self._json({"ok": False, "erreur": "Étude introuvable."})
        return self._json({"ok": True, "etude": {
            "id": e.id,
            "name": e.name,
            "etat": e.etat,
            "date": str(e.create_date)[:16],
            "verdict": e.verdict or "",
            "justification": e.justification or "",
            "resume": e.resume or "",
            "observations": e.observations or "",
        }})

    @staticmethod
    def _json(data):
        return request.make_json_response(data)
