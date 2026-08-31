# -*- coding: utf-8 -*-
"""Chaque produit livré laisse sa recette.

La règle posée par Patrick le 28/07 : « à la fin de chaque travail, si cela
aboutit à un produit, faire le prompt à partir de tout ce qui a été fait pour
reproduire le produit, et le stocker. Ça doit être automatique. »

Le problème qu'elle résout est réel et il coûte cher. Une application est
construite en une nuit, à partir d'une consigne, d'allers-retours et de
corrections. Trois mois plus tard on veut la même pour un autre client — et on
ne sait plus **ce qu'on avait demandé exactement**. On recommence, on retombe
sur les mêmes pièges, et on paie deux fois le même apprentissage.

**La recette n'est pas la consigne de départ.** C'est la consigne PLUS ce qu'on
a appris en la réalisant : ce qui a raté, ce qu'il fallait préciser, la
contrainte qu'on avait oubliée. Une recette qui ne contient que la demande
initiale reproduit aussi les erreurs.

**C'est automatique, sinon ce n'est pas fait.** Une recette qu'il faut penser à
écrire ne s'écrit jamais — c'est la même leçon que le journal des livraisons,
ratée deux fois avant d'être câblée.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Ce que chaque moteur SAIT et NE SAIT PAS faire. Écrit en clair dans la
# recette : sans ça, on relance un produit avec un outil incapable de le
# fabriquer, et on ne comprend pas pourquoi le résultat est vide.
OUTILS = {
    "claude": "Écrit du code et des fichiers, a le réseau et l'abonnement. "
              "C'est celui qui construit vraiment.",
    "discussion": "Comme claude, mais avec de la mémoire d'un échange à "
                  "l'autre, et travaille dans un dépôt.",
    "lois": "LECTURE SEULE (Read, Glob, Grep). Ne peut rien écrire — c'est "
            "voulu. Sert à relire, jamais à produire.",
    "braignak": "Observe l'extérieur. Refuse de publier, par construction, et "
                "s'arrête si son autorisation de 24 h a expiré.",
    "bac-a-sable": "Conteneur SANS RÉSEAU. Ne peut appeler aucune IA : il "
                   "exécute du code déjà écrit, il n'en invente pas. "
                   "Demander une création ici rend une page vide.",
    "windev": "Comme claude, avec le corpus PC SOFT chargé et l'interdiction "
              "d'inventer des signatures de fonctions.",
    "essai": "Aucune IA, aucun coût. Sert à vérifier que la chaîne fonctionne.",
    "aider": "Autres fournisseurs d'IA. Jamais éprouvé en réel.",
}


class ProduitModele(models.Model):
    _name = "produit.modele"
    _description = "Recette d'un produit livré"
    _order = "date desc, id desc"

    name = fields.Char("Le produit", required=True)
    quoi = fields.Char("Ce que ça fait, en une phrase")
    date = fields.Datetime("Livré le", default=fields.Datetime.now, required=True)

    prompt = fields.Text(
        "La recette", required=True,
        help="Le texte à donner tel quel pour reproduire ce produit. Il "
             "contient la demande ET ce qu'on a appris en la réalisant.")
    lecons = fields.Text(
        "Ce qu'on a appris en le faisant",
        help="Ce qui a raté, ce qu'il fallait préciser. C'est cette partie qui "
             "distingue une recette d'une commande — sans elle, on reproduit "
             "aussi les erreurs.")

    origine = fields.Selection(
        [("mission", "Une mission de l'atelier"),
         ("module", "Un module de la tour"),
         ("main", "Écrite à la main")],
        "D'où ça vient", default="mission", required=True)
    mission_id = fields.Many2one("atelier.mission", "Mission d'origine",
                                 ondelete="set null")
    url = fields.Char("Où c'est en ligne")
    fichiers = fields.Integer("Fichiers produits")

    rejoue_le = fields.Datetime("Rejouée le", readonly=True)
    rejoue_ok = fields.Boolean("Rejouée avec succès", readonly=True)

    _sql_constraints = [
        ("nom_unique", "unique(name)",
         "Une recette existe déjà sous ce nom : on la met à jour, on n'en "
         "crée pas une seconde."),
    ]

    # ------------------------------------------------------------------
    @api.model
    def _depuis_mission(self, mission):
        """Fabrique la recette d'un produit sorti de l'atelier.

        Appelée automatiquement à la relève, pour toute mission qui a
        RÉELLEMENT produit quelque chose. Une mission qui répond du texte n'est
        pas un produit — on ne garde une recette que de ce qui existe.
        """
        if not mission or mission.etat != "terminee":
            return False
        # Ce qui distingue un produit d'une réponse : des fichiers publiés.
        if not (mission.publier and mission.nb_fichiers):
            return False
        existante = self.search([("mission_id", "=", mission.id)], limit=1)
        recette = self._rediger(mission)
        vals = {
            "name": mission.name,
            "quoi": (mission.consigne or "").strip().split("\n")[0][:120],
            "prompt": recette,
            "origine": "mission",
            "mission_id": mission.id,
            "url": mission.url,
            "fichiers": mission.nb_fichiers,
        }
        if existante:
            existante.write(vals)
            return existante
        try:
            with self.env.cr.savepoint():
                return self.create(vals)
        except Exception:
            # Un nom déjà pris : on ne perd pas la recette, on la range sous
            # un nom voisin plutôt que de la jeter.
            vals["name"] = "%s (%s)" % (mission.name, mission.id)
            return self.create(vals)

    @api.model
    def _rediger(self, mission):
        """La recette = la consigne + ce que la réalisation a appris.

        On ne recopie pas seulement la demande : on y ajoute ce que le compte
        rendu révèle. Une recette qui ne contient que la demande initiale
        reproduit aussi les erreurs qu'on a mis une nuit à corriger.
        """
        morceaux = [
            "# %s" % mission.name,
            "",
            "## Ce qu'il faut produire",
            "",
            (mission.consigne or "").strip(),
            "",
            "## Ce qu'on sait de la réalisation",
            "",
        ]
        # LES OUTILS, EN DETAIL. Sans eux la recette est une intention : on sait
        # quoi obtenir, pas avec quoi. Et le choix du moteur change tout — le
        # bac a sable n a pas de reseau, donc il ne peut appeler aucune IA, ce
        # qu on a paye le 28/07 en publiant une page vide.
        moteur = mission.moteur_utilise or mission.moteur or "?"
        morceaux += [
            "## Avec quels outils",
            "",
            "- **Moteur** : `%s`" % moteur,
            "  %s" % OUTILS.get(moteur, "Moteur non documenté ici."),
        ]
        if mission.depot:
            morceaux.append(
                "- **Dépôt de travail** : `%s` — l'agent travaille DANS du code "
                "existant, il ne part pas d'un dossier vide." % mission.depot)
        else:
            morceaux.append(
                "- **Pas de dépôt** : l'agent part d'un dossier vide et "
                "construit de zéro.")
        if mission.publier:
            morceaux.append(
                "- **Publication** : activée, adresse `%s`. Le résultat est "
                "copié vers le dossier servi par le serveur web, en liste "
                "blanche d'extensions." % (mission.slug or "?"))
        morceaux += [
            "- **Fichiers produits** : %s" % (mission.nb_fichiers or 0),
        ]
        if mission.duree:
            morceaux.append("- Durée : environ %s secondes" % mission.duree)
        if mission.url:
            morceaux.append("- Résultat d'origine : %s" % mission.url)
        rendu = (mission.reponse or "").strip()
        if rendu:
            morceaux += ["", "## Ce que l'agent a rapporté en le faisant", "",
                         rendu[:3000]]
        morceaux += [
            "",
            "## À vérifier avant de livrer",
            "",
            "- Le résultat répond vraiment à l'adresse annoncée (pas seulement",
            "  « les fichiers sont là »).",
            "- La page principale contient du contenu, pas un gabarit vide.",
            "- Aucun appel réseau si le produit doit marcher hors ligne.",
        ]
        return "\n".join(morceaux)

    def action_rejouer(self):
        """Redéposer cette recette à l'atelier, pour vérifier qu'elle marche.

        C'est le seul contrôle qui vaut : une recette qu'on n'a jamais rejouée
        est une recette dont on ignore si elle produit encore quelque chose.
        """
        self.ensure_one()
        Mission = self.env["atelier.mission"].sudo()
        m = Mission.create({
            "name": _("Rejeu de la recette : %s") % self.name,
            "consigne": self.prompt,
            "moteur": "claude",
        })
        m.action_envoyer()
        self.write({"rejoue_le": fields.Datetime.now()})
        return {
            "type": "ir.actions.act_window",
            "res_model": "atelier.mission",
            "res_id": m.id,
            "view_mode": "form",
        }
