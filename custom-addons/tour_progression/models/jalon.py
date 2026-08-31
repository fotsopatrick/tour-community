# -*- coding: utf-8 -*-
"""Les jalons : ce qu'on a franchi, et ce qui vient après.

La tour sait faire trente-quatre choses. On en utilise cinq — pas par manque
d'envie, mais parce qu'on ignore que les autres existent. Un outil qu'on
n'explore pas se réduit à ce qu'on en a compris le premier jour.

**Un jalon se gagne, il ne se coche pas.** Chacun se lit dans les données
réelles : un site en ligne, un paiement reçu, un guide écrit. Une case à cocher
serait un mensonge qu'on se raconte à soi-même — et c'est le défaut de toutes
les listes de progression qu'on abandonne au bout d'une semaine.

**Ni points, ni badges, ni classement.** Récompenser l'activité pousse à
produire de l'activité : des tâches créées pour créer des tâches. Ce qu'on veut,
c'est qu'un jour on découvre qu'on peut mettre un site en ligne depuis la tour.
La récompense, c'est la découverte, pas le score.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Ce qu'on compte pour chaque jalon : un modèle, un filtre, et le nombre qui
# déclenche. Rien d'autre — un jalon dont la condition ne tient pas en une
# ligne est un jalon qu'on ne saura pas expliquer.
MESURES = {
    "note": ("project.task", [], 1),
    "taches_10": ("project.task", [], 10),
    "projet_2": ("project.project", [], 2),
    "guide": ("tour.guide", [], 1),
    "rappel": ("tour.rappel", [], 1),
    "invite": ("res.users", [("active", "=", True)], 3),
    "actus": ("actus.article", [], 1),
    "mission": ("atelier.mission", [("etat", "=", "terminee")], 1),
    "conversation": ("discussion.fil", [], 1),
    "securite": ("securite.constat", [("etat", "in", ["accepte", "resolu"])], 1),
    "site": ("deploiement.site", [], 1),
    "offre": ("abonnement.offre", [("publie", "=", True)], 1),
    "paiement": ("abonnement.contrat", [], 1),
    "instance": ("abonnement.contrat", [("instance_etat", "=", "montee")], 1),
    "recette": ("recette.passage", [], 1),
    "etude": ("braignak.etude", [], 1),
    "version": ("roadmap.version", [("etat", "=", "figee")], 1),
    "cv": ("cv.profil", [], 1),
    "sauvegarde": ("tour.sauvegarde", [], 1),
    "chiffres": ("tess.releve", [], 1),
}


class TourJalon(models.Model):
    _name = "tour.jalon"
    _description = "Un jalon de progression"
    _order = "sequence, id"

    name = fields.Char("Jalon", required=True)
    description = fields.Char("Ce que ça t'apporte")
    code = fields.Char("Mesure", required=True,
                       help="Clef du catalogue MESURES : ce qui est réellement compté.")
    famille = fields.Selection(
        [("demarrer", "Démarrer"),
         ("organiser", "S'organiser"),
         ("automatiser", "Faire faire"),
         ("vendre", "Vendre")],
        "Étape", default="demarrer", required=True)
    sequence = fields.Integer(default=10)
    ou = fields.Char("Où ça se passe", help="Le menu ou l'adresse à ouvrir.")

    franchi = fields.Boolean("Franchi", readonly=True)
    valeur = fields.Integer("Compté", readonly=True)
    objectif = fields.Integer("À atteindre", readonly=True)
    mesure_le = fields.Datetime("Dernière mesure", readonly=True)

    def _mesurer(self):
        """Relit les compteurs. Chaque mesure est isolée : un module absent
        chez un client ne doit pas empêcher de mesurer les autres."""
        maintenant = fields.Datetime.now()
        for j in self:
            desc = MESURES.get(j.code)
            if not desc:
                continue
            modele, domaine, seuil = desc
            valeur = 0
            if modele in self.env:
                try:
                    with self.env.cr.savepoint():
                        valeur = self.env[modele].sudo().search_count(domaine)
                except Exception:
                    valeur = j.valeur or 0
            j.write({"valeur": valeur, "objectif": seuil,
                     "franchi": valeur >= seuil, "mesure_le": maintenant})

    @api.model
    def _etat(self):
        """Ce que la page affiche : les jalons par étape, et le prochain.

        On met en avant UN seul prochain jalon. Une liste de vingt choses à
        faire décourage ; une seule chose à essayer se tente.
        """
        jalons = self.search([])
        jalons._mesurer()
        familles = dict(self._fields["famille"].selection)
        groupes, prochain = [], None
        for code, libelle in self._fields["famille"].selection:
            dedans = jalons.filtered(lambda j: j.famille == code)
            if not dedans:
                continue
            groupes.append({
                "nom": libelle,
                "jalons": dedans,
                "faits": len(dedans.filtered("franchi")),
                "total": len(dedans),
            })
            if prochain is None:
                reste = dedans.filtered(lambda j: not j.franchi)
                if reste:
                    prochain = reste[0]
        return {
            "groupes": groupes,
            "prochain": prochain,
            "faits": len(jalons.filtered("franchi")),
            "total": len(jalons),
            "familles": familles,
        }

    @api.model
    def _cron_mesurer(self):
        self.search([])._mesurer()
        return True
