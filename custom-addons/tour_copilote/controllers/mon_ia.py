# -*- coding: utf-8 -*-
"""« Mon IA » — chaque compte branche son moteur et sa clé (08/08, Merline).

Demande de Patrick : sur la démo, les gens n'ont aucun moyen de rajouter leur
propre clé DeepSeek ou opencode. Ça existe dans le backend Odoo (réglages du
copilote), mais on ne donne pas accès au backend aux invités. Il faut une
webapp comme les autres, liée à leur compte, qui leur permette de modifier le
moteur et la clé API.

LA CLE NE REMONTE JAMAIS. Le formulaire affiche seulement si une clé est
définie (…4 derniers caractères). Un champ vide + la case « effacer » supprime
la clé ; un champ rempli la remplace. La valeur n'est jamais renvoyée au
navigateur, ni ici ni par le chat.
"""
import logging

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

MOTEURS_AUTORISES = {"", "deepseek", "opencode"}


class MonIa(http.Controller):

    @http.route("/tour/mon-ia", type="http", auth="user", website=False,
                methods=["GET"], csrf=False)
    def mon_ia(self, **kw):
        user = request.env.user
        return request.render("tour_copilote.mon_ia_page", {
            "moteur": user.ia_moteur or "",
            "cle_definie": user.ia_cle_definie or "",
            "est_admin": user.has_group("base.group_system"),
            "message": request.params.get("message", ""),
            "ton": request.params.get("ton", "fait"),
        })

    @http.route("/tour/mon-ia", type="http", auth="user", website=False,
                methods=["POST"], csrf=True)
    def mon_ia_sauver(self, **kw):
        user = request.env.user
        moteur = (kw.get("ia_moteur") or "").strip().lower()
        if moteur not in MOTEURS_AUTORISES:
            moteur = ""
        effacer = kw.get("effacer_cle") == "1"
        cle = kw.get("ia_cle") or ""

        vals = {"ia_moteur": moteur}
        if effacer:
            vals["ia_cle"] = False
            message, ton = "Clé supprimée.", "fait"
        elif cle.strip():
            # On n'accepte qu'une clé plausible : assez longue, pas d'espace.
            if len(cle.strip()) < 8 or " " in cle.strip():
                message, ton = ("Clé refusée : une clé API fait au moins "
                                "8 caractères et ne contient pas d'espace.",
                                "attention")
                return request.redirect(
                    "/tour/mon-ia?message=%s&ton=%s" % (message, ton))
            vals["ia_cle"] = cle.strip()
            message, ton = "Clé enregistrée.", "fait"
        else:
            # Champ vide : on garde la clé existante, on ne change que le moteur.
            message, ton = "Réglages enregistrés.", "fait"

        user.sudo().write(vals)
        if request.env.user.id != user.id:
            # Impossible normalement, mais on ne se défend pas par surprise :
            # un write sur le mauvais compte serait un trou de sécurité.
            _logger.warning("Mon IA : tentative d'écriture croisée uid=%s",
                            user.id)
        return request.redirect(
            "/tour/mon-ia?message=%s&ton=%s" % (message, ton))
