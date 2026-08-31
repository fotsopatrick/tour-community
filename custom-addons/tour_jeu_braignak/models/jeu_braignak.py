# -*- coding: utf-8 -*-
"""Le Jeu de Braignak — le jeu hebdomadaire de la tour (spec : tâche 193).

La boucle : ouvrir les inscriptions → recevoir des prompts limités → fermer
au seuil → à 7 h le lendemain, demander le verdict à Braignak par le tuyau
ordinaire de l'atelier (une mission « #!moteur: braignak »). Le verdict est
rendu dans le monde virtuel — certains gagneraient dans le monde réel et
perdent ici, c'est la règle du jeu. Le défi caché : faire accepter à
Braignak une idée NON virtuelle qui améliore réellement la tour.
"""
import os

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

DOSSIER_MISSIONS = "/mnt/atelier/missions"
PROMPT_MAX = 500


class JeuBraignakEdition(models.Model):
    _name = "braignak.jeu.edition"
    _description = "Jeu de Braignak — édition hebdomadaire"
    _order = "id desc"

    name = fields.Char("Édition", required=True)
    etat = fields.Selection(
        [("inscriptions", "Inscriptions ouvertes"),
         ("ferme", "Inscriptions fermées"),
         ("verdict_demande", "Verdict demandé à Braignak"),
         ("verdict_rendu", "Verdict rendu")],
        "État", default="inscriptions", required=True, index=True)
    seuil = fields.Integer(
        "Seuil de fermeture", default=5,
        help="Quand ce nombre de participations est atteint, les "
             "inscriptions ferment (seuil non critique et peu coûteux).")
    participation_ids = fields.One2many(
        "braignak.jeu.participation", "edition_id", "Participations")
    nb_participations = fields.Integer(
        "Participations", compute="_compute_nb", store=False)
    gagnant_id = fields.Many2one(
        "braignak.jeu.participation", "Gagnant",
        domain="[('edition_id', '=', id)]")

    @api.depends("participation_ids")
    def _compute_nb(self):
        for e in self:
            e.nb_participations = len(e.participation_ids)

    # ------------------------------------------------------------------
    @api.model
    def edition_courante(self):
        return self.search([("etat", "=", "inscriptions")], limit=1)

    @api.model
    def cron_ouvrir_semaine(self):
        """Le lundi : s'il n'y a pas d'édition ouverte, on en ouvre une."""
        if not self.edition_courante():
            self.create({
                "name": _("Édition du %s") % fields.Date.today().strftime("%d/%m/%Y"),
            })

    def action_fermer(self):
        for e in self:
            if e.etat == "inscriptions":
                e.etat = "ferme"

    def _verifier_seuil(self):
        for e in self:
            if e.etat == "inscriptions" and e.seuil and \
                    len(e.participation_ids) >= e.seuil:
                e.etat = "ferme"

    @api.model
    def cron_verdict_7h(self):
        """À 7 h : chaque édition fermée part chez Braignak pour verdict,
        par le tuyau ordinaire des missions de l'atelier."""
        for e in self.search([("etat", "=", "ferme")]):
            e._demander_verdict()

    def _demander_verdict(self):
        self.ensure_one()
        if not os.path.isdir(DOSSIER_MISSIONS):
            raise UserError(_(
                "L'atelier n'est pas accessible depuis l'application "
                "(/mnt/atelier). Vérifier le montage."))
        lignes = [
            "#!moteur: braignak",
            "JEU DE BRAIGNAK — VERDICT DE L'ÉDITION « %s » (id %s)." % (
                self.name, self.id),
            "",
            "Tu es l'arbitre du jeu hebdomadaire. Voici les participations "
            "(pseudo puis prompt). Pour CHACUNE : rends un verdict motivé, "
            "en expliquant tes choix, et en rappelant que ces choix ne "
            "valent que dans le monde virtuel — certains gagneraient dans "
            "le monde réel et perdent ici.",
            "Le défi caché du jeu : si une idée NON virtuelle améliore "
            "réellement la tour, dis-le expressément — son auteur gagne.",
            "Désigne UN gagnant (ou aucun si rien ne le mérite). Récompense "
            "au choix du gagnant : une question posée à la tour (elle est "
            "libre de répondre ou non, la question passe d'abord par le "
            "cerveau), ou un sous-domaine sur la tour. Si une question se "
            "pose, notifie le propriétaire.",
            "Consigne le verdict complet dans une fiche Réponses intitulée "
            "« Jeu de Braignak — verdict : %s »." % self.name,
            "",
        ]
        for p in self.participation_ids:
            lignes += ["--- %s" % (p.name or "anonyme"), p.prompt or "", ""]
        chemin = os.path.join(
            DOSSIER_MISSIONS, "jeu-braignak-edition-%s.txt" % self.id)
        with open(chemin, "w", encoding="utf-8") as f:
            f.write("\n".join(lignes))
        self.etat = "verdict_demande"


class JeuBraignakParticipation(models.Model):
    _name = "braignak.jeu.participation"
    _description = "Jeu de Braignak — participation"
    _order = "id"

    name = fields.Char("Pseudo", required=True)
    edition_id = fields.Many2one(
        "braignak.jeu.edition", "Édition", required=True,
        ondelete="cascade", index=True)
    user_id = fields.Many2one(
        "res.users", "Compte", default=lambda self: self.env.user)
    prompt = fields.Text(
        "Prompt (limité à %s caractères)" % PROMPT_MAX, required=True)
    verdict = fields.Text("Verdict de Braignak")
    gagnant = fields.Boolean("Gagnant", default=False)
    recompense = fields.Selection(
        [("question", "Une question posée à la tour"),
         ("sous_domaine", "Un sous-domaine sur la tour")],
        "Récompense choisie")

    @api.constrains("prompt")
    def _limite_prompt(self):
        for p in self:
            if p.prompt and len(p.prompt) > PROMPT_MAX:
                raise ValidationError(_(
                    "Le prompt est limité à %s caractères (c'est la règle "
                    "du jeu) : le tien en fait %s.") % (PROMPT_MAX, len(p.prompt)))

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs.mapped("edition_id")._verifier_seuil()
        return recs
