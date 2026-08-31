# -*- coding: utf-8 -*-
"""La page « Où chercher » : un écran à nous, posé sur le classeur d'Odoo.

Le cap de Patrick : se détacher d'Odoo petit à petit, en gardant Odoo pour ce
qu'il fait bien — ranger. Alors on lui laisse le rangement (la base, les
comptes, les droits) et on lui reprend l'écran.

Le piège qu'on évite ici : les webapps de la maison ont chacune leur propre
base (la veille de missions garde ses missions dans un SQLite à elle). Deux
rangements pour une même chose finissent toujours par se contredire, et on ne
sait plus lequel dit vrai. Cette page-ci ne stocke RIEN. Elle demande, elle
affiche. La vérité reste à un seul endroit.

L'autre raison de servir la page depuis Odoo plutôt qu'à côté : la session.
Une webapp posée sur un autre port devrait réinventer la connexion et les
cercles — c'est-à-dire réécrire à la main la garde qu'on vient de coder. Ici
`auth="user"` fait le travail, et le cercle est LU dans les groupes.
"""
import json

from odoo import http
from odoo.http import request

from .page import PAGE


class OuChercher(http.Controller):

    # ------------------------------------------------------------------
    # L'écran
    # ------------------------------------------------------------------
    @http.route("/ou-chercher", type="http", auth="user", website=False)
    def page(self, **kw):
        return request.make_response(PAGE, headers=[
            ("Content-Type", "text/html; charset=utf-8"),
            ("Cache-Control", "no-store"),
            ("X-Frame-Options", "SAMEORIGIN"),
        ])

    # ------------------------------------------------------------------
    # La porte : du JSON, rien d'autre
    # ------------------------------------------------------------------
    def _cercle(self):
        return request.env["recherche.source"].cercle_de(request.env.user)

    def _json(self, charge, code=200):
        return request.make_response(
            json.dumps(charge, ensure_ascii=False),
            headers=[("Content-Type", "application/json; charset=utf-8"),
                     ("Cache-Control", "no-store")],
            status=code)

    @http.route("/api/recherche/endroits", type="http", auth="user",
                methods=["GET"], csrf=False)
    def endroits(self, pour_quoi=None, **kw):
        cercle = self._cercle()
        Source = request.env["recherche.source"]
        # Tous les endroits du cercle, allumés ou non : sinon on ne peut pas
        # rallumer depuis la page ce qu'on a éteint.
        toutes = Source.sudo().search(
            [("cercle", ">=", cercle)] +
            ([("pour_quoi", "ilike", pour_quoi)] if pour_quoi else []))
        return self._json({
            "moi": request.env.user.name,
            "cercle": cercle,
            "endroits": [{
                "id": s.id,
                "nom": s.name,
                "resume": s.resume or "",
                "genre": s.genre,
                "genre_libelle": dict(s._fields["genre"].selection).get(s.genre, s.genre),
                "adresse": s.adresse or "",
                "pour_quoi": s.pour_quoi or "",
                "cercle": s.cercle,
                "actif": s.actif,
                "comment": s.comment_y_aller or "",
                "passages": s.passages_count,
            } for s in toutes],
        })

    @http.route("/api/recherche/basculer", type="http", auth="user",
                methods=["POST"], csrf=False)
    def basculer(self, **kw):
        """Allumer ou éteindre un endroit.

        Réservé au cercle 1 : décider où la tour a le droit de fouiller est
        une décision de Patrick, pas un réglage d'écran.
        """
        if self._cercle() != "1":
            return self._json({"erreur": "Seul le cercle 1 peut allumer ou "
                                         "éteindre un endroit."}, 403)
        try:
            corps = json.loads(request.httprequest.get_data() or b"{}")
            source_id = int(corps.get("id"))
        except (ValueError, TypeError):
            return self._json({"erreur": "Il manque l'endroit."}, 400)

        source = request.env["recherche.source"].sudo().browse(source_id)
        if not source.exists():
            return self._json({"erreur": "Cet endroit n'existe pas."}, 404)
        source.actif = not source.actif
        return self._json({"id": source.id, "actif": source.actif})

    @http.route("/api/recherche/journal", type="http", auth="user",
                methods=["GET"], csrf=False)
    def journal(self, limite=40, **kw):
        cercle = self._cercle()
        try:
            limite = max(1, min(int(limite), 200))
        except (ValueError, TypeError):
            limite = 40
        passages = request.env["recherche.passage"].sudo().search(
            [("source_id.cercle", ">=", cercle)], limit=limite)
        return self._json({"passages": [{
            "quand": p.create_date.strftime("%d/%m %H:%M") if p.create_date else "",
            "qui": p.qui,
            "cercle": p.cercle,
            "endroit": p.source_id.name,
            "cherche": p.cherche,
            "trouve": p.trouve,
            "refuse": p.refuse,
            "note": p.note or "",
        } for p in passages]})

    @http.route("/api/recherche/noter", type="http", auth="user",
                methods=["POST"], csrf=False)
    def noter(self, **kw):
        """Écrire dans le journal qu'on est allé chercher quelque part.

        C'est par ici que passent les agents et les outils. La garde tourne
        avant l'écriture : un refus est refusé ET écrit, sinon on ne saurait
        jamais qu'il a eu lieu.
        """
        try:
            corps = json.loads(request.httprequest.get_data() or b"{}")
            source_id = int(corps.get("id"))
            cherche = (corps.get("cherche") or "").strip()
        except (ValueError, TypeError):
            return self._json({"erreur": "Il manque l'endroit."}, 400)
        if not cherche:
            return self._json({"erreur": "Il manque ce qu'on cherchait."}, 400)

        cercle = self._cercle()
        source = request.env["recherche.source"].sudo().browse(source_id)
        if not source.exists():
            return self._json({"erreur": "Cet endroit n'existe pas."}, 404)

        from odoo.exceptions import AccessError
        try:
            source.noter_passage(
                cercle, request.env.user.name, cherche,
                trouve=int(corps.get("trouve") or 0),
                note=corps.get("note"))
        except AccessError as e:
            request.env["recherche.source"].noter_refus(
                source.id, cercle, request.env.user.name, cherche, str(e))
            return self._json({"erreur": str(e), "refus_note": True}, 403)
        return self._json({"ok": True})
