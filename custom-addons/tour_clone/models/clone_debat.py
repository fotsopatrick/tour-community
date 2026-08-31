# -*- coding: utf-8 -*-
"""LE CLONE QUI APPREND EN DEBATTANT (04/08, demande de Patrick).

« Si je me trompe il donne son avis, je réponds, c'est un débat d'idées et de
raisonnement, normal. »

Ce n'est donc PAS un questionnaire. Le clone n'est pas là pour faire préciser
Patrick : il a un avis, il le donne, et il tient sa position tant qu'on ne l'a
pas convaincu. C'est cette friction qui apprend quelque chose — un agent qui
approuve n'apprend rien de celui qu'il approuve.

Le sujet vient des Actus (1630 articles, 19 flux categorises). On ne fabrique
pas un sujet : on prend ce qui est arrive dans le monde aujourd'hui.

Ce qui est CONSERVE, c'est la reponse de Patrick — pas celle du clone. Le
clone se relit lui-meme quand il repond ensuite : sa matiere d'apprentissage,
c'est la facon dont Patrick raisonne, pas la facon dont lui-meme parle.
"""
from odoo import api, fields, models


class CloneDebat(models.Model):
    _name = "clone.debat"
    _description = "Débat entre Patrick et son clone"
    _order = "id desc"

    name = fields.Char("Sujet", required=True)
    theme = fields.Char("Thématique", index=True,
                        help="La catégorie choisie : IA, Dev, Économie…")
    article_id = fields.Many2one("actus.article", "Article de départ",
                                 ondelete="set null")
    lien = fields.Char("Lien de l'article")
    etat = fields.Selection(
        [("ouvert", "En cours"), ("clos", "Terminé")],
        "État", default="ouvert", required=True)
    user_id = fields.Many2one("res.users", "Avec", required=True,
                              default=lambda s: s.env.user)
    tour_ids = fields.One2many("clone.debat.tour", "debat_id", "Échanges")
    nb_tours = fields.Integer("Échanges", compute="_compute_nb", store=True)
    # Ce que le clone a retenu : ecrit a la cloture, relu au debat suivant.
    lecon = fields.Text("Ce que le clone en a retenu")

    @api.depends("tour_ids")
    def _compute_nb(self):
        for d in self:
            d.nb_tours = len(d.tour_ids)


class CloneDebatTour(models.Model):
    _name = "clone.debat.tour"
    _description = "Un échange dans un débat"
    _order = "id"

    debat_id = fields.Many2one("clone.debat", "Débat", required=True,
                               ondelete="cascade", index=True)
    qui = fields.Selection([("patrick", "Patrick"), ("clone", "Le clone")],
                           "Qui parle", required=True)
    texte = fields.Text("Ce qui est dit", required=True)
    # Un desaccord assume se compte : c est la mesure du debat. Un clone qui
    # n est jamais en desaccord ne debat pas, il acquiesce.
    desaccord = fields.Boolean("Le clone n'est pas d'accord", default=False)
