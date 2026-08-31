# -*- coding: utf-8 -*-
from . import models
from . import controllers


def post_init(env):
    """Branche le compteur « Quêtes de carrière » sur la fiche de Patrick.

    Le compteur se MESURE (search_count des quêtes faites), il ne se saisit
    pas : la compétence naît sans valeur, et la relève de tour_equipage la
    remplit au premier passage. Jamais de point posé à la main.
    """
    membre = env["equipe.membre"].sudo().search(
        [("name", "=", "Patrick")], limit=1)
    if not membre:
        return
    Comp = env["equipe.competence"].sudo()
    if Comp.search([("code", "=", "patrick_quetes")], limit=1):
        return
    Comp.create({
        "membre_id": membre.id,
        "name": "Quêtes de carrière",
        "code": "patrick_quetes",
        "sequence": 10,
    })
