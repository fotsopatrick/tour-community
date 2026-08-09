# -*- coding: utf-8 -*-
"""Téléchargement d'une sauvegarde.

Deux vérifications avant de servir quoi que ce soit : l'appelant est
administrateur, et le chemin résolu reste bien à l'intérieur du dossier des
sauvegardes. Le nom de fichier vient de la base, mais on ne lui fait pas
confiance pour autant — un jour quelqu'un écrira un enregistrement à la main.
"""
import os

from odoo import http
from odoo.http import request

def _dossier():
    """Dossier des sauvegardes. Paramétrable (sauvegardes.dossier) pour
    brancher le vrai dossier de sauvegarde du serveur ; par défaut, un
    dossier local du module (édition Community)."""
    import os
    return request.env["ir.config_parameter"].sudo().get_param(
        "sauvegardes.dossier",
        os.path.join(os.path.dirname(os.path.dirname(__file__)),
                     "sauvegardes"))


class TourSauvegardeController(http.Controller):

    @http.route("/tour/sauvegarde/<int:sauvegarde_id>", type="http",
                auth="user", methods=["GET"])
    def telecharger(self, sauvegarde_id, **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.not_found()

        sauvegarde = request.env["tour.sauvegarde"].sudo().browse(sauvegarde_id)
        if not sauvegarde.exists() or not sauvegarde.presente:
            return request.not_found()

        DOSSIER = _dossier()
        chemin = os.path.realpath(os.path.join(DOSSIER, sauvegarde.name))
        racine = os.path.realpath(DOSSIER)
        if not chemin.startswith(racine + os.sep) or not os.path.isfile(chemin):
            return request.not_found()

        with open(chemin, "rb") as f:
            contenu = f.read()

        return request.make_response(contenu, headers=[
            ("Content-Type", "application/octet-stream"),
            ("Content-Length", str(len(contenu))),
            ("Content-Disposition",
             'attachment; filename="%s"' % sauvegarde.name),
        ])
