# -*- coding: utf-8 -*-
"""L'API du Pilote et son cockpit.

- /tour/pilote/... : la page web (réservée admin) pour voir les demandes et
  en créer une.
- /tour/pilote/api/tache, /repondre, /etat : le moteur hôte (pilote.py) parle
  ici en JSON. Protégé par un jeton (config ir.config_parameter), pas par une
  session navigateur : le moteur tourne côté serveur, il n'a pas de cookies.
"""
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PiloteController(http.Controller):

    def _token_ok(self, token):
        attendu = request.env["ir.config_parameter"].sudo().get_param(
            "tour_pilotage.token", "")
        return bool(attendu) and token == attendu

    # ------------------------------------------------------------------
    # API — le moteur hôte
    # ------------------------------------------------------------------
    @http.route("/tour/pilote/api/tache", type="http", auth="public",
                website=False, csrf=False, methods=["GET", "POST"])
    def api_tache(self, **kw):
        token = kw.get("token", "")
        if not self._token_ok(token):
            return request.make_json_response({"ok": False,
                                               "erreur": "jeton invalide"})
        return request.make_json_response(
            request.env["pilote.demande"].sudo()._api_tache(token=token))

    @http.route("/tour/pilote/api/repondre", type="http", auth="public",
                website=False, csrf=False, methods=["POST"])
    def api_repondre(self, **kw):
        # Le jeton peut venir de la query string OU du corps JSON : les deux
        # contrats sont acceptés (le moteur hôte envoie dans l'URL, mais un
        # client qui suit le contrat annoncé — jeton dans le corps — ne doit
        # pas être rejeté).
        data = json.loads(request.httprequest.get_data(as_text=True) or "{}")
        token = kw.get("token", "") or data.get("token", "")
        if not self._token_ok(token):
            return request.make_json_response({"ok": False,
                                               "erreur": "jeton invalide"})
        return request.make_json_response(
            request.env["pilote.demande"].sudo()._api_repondre(
                token=token,
                demande_id=int(data.get("demande_id", 0)),
                approuve=bool(data.get("approuve")),
                avis=str(data.get("avis", "") or "")))

    @http.route("/tour/pilote/api/etat", type="http", auth="public",
                website=False, csrf=False, methods=["GET"])
    def api_etat(self, **kw):
        token = kw.get("token", "")
        if not self._token_ok(token):
            return request.make_json_response({"ok": False,
                                               "erreur": "jeton invalide"})
        return request.make_json_response(
            request.env["pilote.demande"].sudo()._api_etat(token=token))

    # ------------------------------------------------------------------
    # Cockpit web (admin)
    # ------------------------------------------------------------------
    @http.route("/tour/pilote", type="http", auth="user", website=False,
                csrf=False)
    def cockpit(self, **kw):
        env = request.env
        if not env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        demandes = env["pilote.demande"].sudo().search(
            [], order="create_date desc, id desc", limit=50)
        gabarits = env["circuit.modele"].sudo().search(
            [("active", "=", True)], order="name")
        def echape(s):
            return (str(s or "").replace("&", "&amp;")
                    .replace("<", "&lt;").replace('"', "&quot;"))
        lignes = []
        for d in demandes:
            badge = {
                "brouillon": "neutre", "en_attente": "neutre",
                "en_cours": "ok", "termine": "ok", "refuse": "rouge",
                "patron": "or", "erreur": "rouge",
            }.get(d.etat, "neutre")
            lignes.append(
                '<div class="demande"><div class="tete">'
                '<span class="badge %s">%s</span>'
                '<b class="nom">%s</b>'
                '<span class="gabarit">%s</span></div>'
                '<div class="info">Porte %d/%d · %s</div>'
                '<pre class="journal">%s</pre></div>'
                % (badge, echape(d.etat), echape(d.name),
                   echape(d.modele_id.name), d.nb_faites, d.nb_portes,
                   echape(d.porte_nom or "—"), echape(d.journal or "")))
        options = "".join(
            '<option value="%d">%s (%d portes)</option>'
            % (g.id, echape(g.name), len(g.etape_ids))
            for g in gabarits)
        return request.render("tour_pilotage.pilote_cockpit", {
            "lignes": "".join(lignes) or
                      "<p class='vide'>Aucune demande de pilotage.</p>",
            "options": options,
            "token": env["ir.config_parameter"].sudo().get_param(
                "tour_pilotage.token", ""),
        })

    @http.route("/tour/pilote/demander", type="http", methods=["POST"],
                auth="user", csrf=False)
    def demander(self, **kw):
        env = request.env
        if not env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        modele_id = int(kw.get("modele_id", 0) or 0)
        sujet = (kw.get("sujet", "") or "").strip()
        detail = (kw.get("description", "") or "").strip()
        modele = env["circuit.modele"].sudo().browse(modele_id)
        if not modele.exists() or not sujet:
            return request.redirect("/tour/pilote?erreur=1")
        demande = env["pilote.demande"].sudo().create({
            "name": sujet[:120],
            "description": detail,
            "modele_id": modele.id,
        })
        # Le formulaire du cockpit ENVOIE directement au pilote : créer une
        # demande et la laisser en brouillon reviendrait à poser un post-it
        # que personne ne lit. (Trouvé le 10/08 : la demande 4 « rendre kana
        # plus top » était restée brouillon.)
        try:
            demande.action_envoyer()
        except Exception as exc:  # noqa: BLE001
            return request.redirect("/tour/pilote?erreur=1")
        return request.redirect("/tour/pilote")
