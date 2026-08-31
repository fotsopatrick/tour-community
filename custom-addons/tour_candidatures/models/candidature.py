# -*- coding: utf-8 -*-
"""Les candidatures : la trace se prend en postulant, pas en la cherchant après.

Le 06/08/2026, on a fouillé douze mois de la boîte mail de Patrick pour
retrouver ses candidatures. On en a trouvé quatre. Le problème n'était pas la
fouille — elle a bien marché — mais ce qu'elle révélait : **Patrick postule
presque toujours par formulaire.** Deux envois par courriel sur quatre. Le
reste passe par le site de l'entreprise.

Conséquence exacte : la boîte mail ne garde que les accusés de réception. Une
candidature déposée sur un site qui n'en envoie pas **n'existe nulle part**.
Pas de trace, pas de relance, pas de mémoire. On ne peut pas retrouver ce qui
n'a jamais été écrit.

D'où ce module : la trace se prend au moment où l'on postule. Trente secondes,
une fois, et la candidature existe.

Deux décisions de conception, et elles viennent de Patrick :

**Plusieurs portes, jamais une seule.** Une même entreprise s'aborde en
salarié, en consulting ou en mission. CGI est une ESN, Ixion un accélérateur :
on entre par un poste et on propose ensuite autre chose. Le module note la
porte, il n'en recommande aucune, et il ne dit jamais qu'une candidature est
« incohérente » ou « trop basse ».

**Ce qui compte, c'est l'argent.** La rémunération visée est un champ de
premier plan, pas une note en bas de fiche. Un état d'avancement sans montant
ne dit rien d'utile.

Le silence est compté, pas jugé : `jours_sans_reponse` se lit dans les dates,
il n'est jamais saisi. Un compteur tenu à la main finit toujours par mentir.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

# La porte par laquelle on entre. Aucune n'est meilleure qu'une autre.
PORTES = [
    ("salariat", "Salarié"),
    ("consulting", "Consulting"),
    ("mission", "Mission / freelance"),
    ("alternance", "Alternance"),
    ("autre", "Autre"),
]

# Par où la candidature est partie. Sert à savoir si une trace existe ailleurs.
CANAUX = [
    ("formulaire", "Formulaire du site"),
    ("mail", "Courriel"),
    ("linkedin", "LinkedIn"),
    ("cooptation", "Cooptation"),
    ("cabinet", "Cabinet / ESN"),
    ("autre", "Autre"),
]

ETATS = [
    # « Préparée » (21/08/2026, demande de Patrick). La lettre et le CV existent,
    # rien n'est parti. Sans cette case, une candidature preparee devait etre
    # notee « Envoyée » : le compteur de jours de silence se mettait alors a
    # tourner dans le vide, et un compteur qui compte du vide finit par mentir.
    # Elle ne compte pas comme une candidature vivante tant qu'elle n'est pas
    # envoyee : c'est une piece prete, pas une demarche faite.
    ("preparee", "Préparée, pas encore envoyée"),
    ("envoyee", "Envoyée"),
    ("accusee", "Accusé de réception"),
    ("entretien", "Entretien"),
    ("offre", "Offre reçue"),
    ("acceptee", "Acceptée"),
    ("refusee", "Refusée"),
    ("arretee", "Arrêtée par moi"),
    ("silence", "Sans réponse"),
]


class Candidature(models.Model):
    _name = "candidature.fiche"
    _description = "Une candidature"
    _inherit = ["mail.thread"]
    _order = "date_envoi desc, id desc"

    name = fields.Char("Le poste", required=True, tracking=True)
    entreprise = fields.Char("L'entreprise", required=True, tracking=True, index=True)
    porte = fields.Selection(
        PORTES, "La porte", default="salariat", required=True, tracking=True,
        help="Salarié, consulting, mission… Une même entreprise en a "
             "plusieurs. On note celle qu'on a prise, c'est tout.")
    canal = fields.Selection(
        CANAUX, "Par où", default="formulaire", required=True,
        help="Un formulaire ne laisse pas de trace dans la boîte mail : "
             "c'est justement pour ça que cette fiche existe.")

    date_envoi = fields.Date(
        "Envoyée le", required=True, default=fields.Date.context_today,
        tracking=True)
    etat = fields.Selection(ETATS, "Où ça en est", default="envoyee",
                            required=True, tracking=True, index=True)

    # ------------------------------------------------------------- l'argent
    remuneration = fields.Float(
        "Ce que je vise", tracking=True,
        help="En euros. C'est le chiffre qui décide, il est au premier plan.")
    remuneration_proposee = fields.Float(
        "Ce qu'ils proposent", tracking=True,
        help="À remplir dès qu'un montant est prononcé, même à l'oral.")
    unite = fields.Selection(
        [("annuel", "€ par an"), ("jour", "€ par jour"),
         ("mois", "€ par mois"), ("heure", "€ par heure")],
        "Unité", default="annuel", required=True)
    ecart = fields.Float(
        "Écart", compute="_compute_ecart", store=True,
        help="Ce qu'ils proposent moins ce que je vise. Lu, jamais saisi.")

    # ------------------------------------------------------------- le suivi
    contact = fields.Char("Qui suit le dossier")
    contact_mail = fields.Char("Son adresse")
    lien = fields.Char("Lien de l'offre")
    offre = fields.Text(
        "L'offre, collée telle quelle",
        help="Le texte de l'annonce. C'est la matière première d'une "
             "préparation d'entretien.")
    note = fields.Text("Ce qu'il faut retenir")

    source_id = fields.Many2one(
        "recherche.source", "Trouvée où",
        help="L'endroit d'où vient l'offre, dans « Où chercher ».")

    derniere_nouvelle = fields.Date(
        "Dernière nouvelle d'eux", tracking=True,
        help="Le jour où ils ont écrit ou appelé pour la dernière fois. "
             "Vide = ils n'ont jamais répondu.")
    jours_sans_reponse = fields.Integer(
        "Jours de silence", compute="_compute_silence",
        help="Compté depuis la dernière nouvelle, ou depuis l'envoi. "
             "Lu dans les dates, jamais saisi.")
    a_relancer = fields.Boolean(
        "À relancer", compute="_compute_silence", search="_search_a_relancer",
        help="Vivante, et silencieuse depuis plus de dix jours.")

    entretien_id = fields.Many2one(
        "entretien.fiche", "Préparation d'entretien", readonly=True,
        help="Créée par le bouton : l'offre part dans le module Entretiens.")

    _sql_constraints = [
        ("poste_entreprise_date",
         "unique(name, entreprise, date_envoi)",
         "Cette candidature est déjà notée (même poste, même entreprise, "
         "même jour)."),
    ]

    # ------------------------------------------------------------------
    @api.depends("remuneration", "remuneration_proposee")
    def _compute_ecart(self):
        for rec in self:
            rec.ecart = (rec.remuneration_proposee or 0.0) - (rec.remuneration or 0.0)

    @api.depends("date_envoi", "derniere_nouvelle", "etat")
    def _compute_silence(self):
        aujourdhui = fields.Date.context_today(self)
        vivantes = ("envoyee", "accusee", "entretien", "offre")
        for rec in self:
            depart = rec.derniere_nouvelle or rec.date_envoi
            rec.jours_sans_reponse = (aujourdhui - depart).days if depart else 0
            rec.a_relancer = (rec.etat in vivantes and rec.jours_sans_reponse > 10)

    def _search_a_relancer(self, operator, value):
        """Rendre « à relancer » cherchable : sinon le filtre ne marche pas."""
        cibles = self.search([]).filtered("a_relancer").ids
        if (operator == "=" and value) or (operator == "!=" and not value):
            return [("id", "in", cibles)]
        return [("id", "not in", cibles)]

    # ------------------------------------------------------------------
    def action_preparer_entretien(self):
        """Envoie l'offre dans le module Entretiens, qui sait déjà préparer."""
        self.ensure_one()
        if not self.offre:
            raise UserError(_(
                "Colle d'abord l'offre : c'est elle qu'on lit pour préparer."))
        if self.entretien_id:
            fiche = self.entretien_id
        else:
            fiche = self.env["entretien.fiche"].create({
                "name": self.name,
                "entreprise": self.entreprise,
                "offre": self.offre,
            })
            self.entretien_id = fiche
        return {"type": "ir.actions.act_window", "res_model": "entretien.fiche",
                "res_id": fiche.id, "view_mode": "form", "target": "current"}

    def action_noter_nouvelle(self):
        """Ils ont donné signe de vie : le compteur de silence repart."""
        for rec in self:
            rec.derniere_nouvelle = fields.Date.context_today(self)
        return True

    @api.model
    def _resume(self):
        """{vivantes, a_relancer, silence_max} — recalculé à chaque appel."""
        vivantes = self.search([("etat", "in",
                                 ("envoyee", "accusee", "entretien", "offre"))])
        return {
            "vivantes": len(vivantes),
            "a_relancer": len(vivantes.filtered("a_relancer")),
            "silence_max": max(vivantes.mapped("jours_sans_reponse") or [0]),
        }
