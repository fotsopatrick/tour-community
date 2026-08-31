# -*- coding: utf-8 -*-
"""La webapp « Récompense » — ADMIN + mot de passe du Coffre.

Deux verrous, pas un :
  1. ADMIN : seuls les comptes internes (base.group_system) peuvent ouvrir
     la page — pas un invité, pas la démo (le compte démo est admin, lui, et
     c'est voulu : Patrick y teste).
  2. COFFRE : une fois admin, la page demande encore le mot de passe stocké
     dans le Coffre (vault.secret « Récompense — mot de passe »). C'est ce
     qu'a demandé Patrick : la page est sécurisée par des identifiants qui
     vivent dans le Coffre, pas en dur dans le code.

Le mot de passe du Coffre n'est relu qu'à la soumission du formulaire de
déverrouillage — jamais à chaque affichage (chaque lecture est tracée dans
le fil du secret, on ne la spamme pas). La réussite est mémorisée dans la
session, pour la durée de la session.
"""

from odoo import http
from odoo.http import request

from odoo.addons.tour_equipage.models.membre import COMPTEURS

SECRET_NOM = "Récompense — mot de passe"
SESSION_OK = "tour_recompense_ok"

# Les compteurs du catalogue, présentés dans l'ordre : pour attribuer une
# compétence MESURÉE, on la branche sur un compteur réel. « manuel » = une
# reconnaissance sans compteur (elle ne compte rien automatiquement).
COMPTEURS_CHOIX = [("manuel", "Reconnaissance libre (rien à compter)")] + [
    (code, libelle) for code, (libelle, *_rest) in COMPTEURS.items()
]


class PageRecompense(http.Controller):

    def _autorise(self):
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        return None

    def _deverrouille(self):
        return bool(request.session.get(SESSION_OK))

    def _coffre(self):
        """Le secret du Coffre qui ouvre la page, ou False."""
        if "vault.secret" not in request.env:
            return False
        try:
            return request.env["vault.secret"].sudo()._lire(SECRET_NOM)
        except Exception:  # noqa: BLE001
            return False

    @http.route("/tour/recompense", type="http", auth="user", website=False,
                methods=["GET", "POST"], csrf=False)
    def recompense(self, **kw):
        gate = self._autorise()
        if gate:
            return gate
        env = request.env
        # POST de déverrouillage : on vérifie contre le Coffre, UNE fois.
        if request.httprequest.method == "POST" and kw.get("deverrouiller"):
            saisi = (kw.get("mot_de_passe") or "").strip()
            if saisi and saisi == (self._coffre() or ""):
                request.session[SESSION_OK] = True
            else:
                return request.render("tour_equipage.page_recompense", {
                    "deverrouille": False, "erreur": "Mot de passe incorrect.",
                    "agents": [], "compteurs": [], "recompenses": [],
                    "ok": False})
        if not self._deverrouille():
            return request.render("tour_equipage.page_recompense", {
                "deverrouille": False, "erreur": False,
                "agents": [], "compteurs": [], "recompenses": [],
                "ok": False})

        Membre = env["equipe.membre"].sudo()
        agents = Membre.search([], order="sequence, id")
        agents.mapped("competence_ids")._mesurer()

        ok = False
        if request.httprequest.method == "POST" and kw.get("attribuer"):
            m = Membre.browse(int(kw.get("membre_id") or 0))
            if m.exists():
                rec = m._recompenser(
                    kw.get("nom_competence") or "",
                    kw.get("code") or "manuel",
                    kw.get("motif") or "")
                ok = bool(rec.id)
                # La nouvelle compétence peut être mesurée tout de suite.
                m.competence_ids._mesurer()

        recompenses = env["equipe.recompense"].sudo().search(
            [], limit=60) if "equipe.recompense" in env else []
        return request.render("tour_equipage.page_recompense", {
            "deverrouille": True, "erreur": False,
            "agents": agents,
            "compteurs": COMPTEURS_CHOIX,
            "recompenses": recompenses,
            "ok": ok,
        })
