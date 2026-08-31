# -*- coding: utf-8 -*-
"""La salle des débats : la couche vivante, façon Duolingo, PAR-DESSUS le débat.

Demandée par Patrick (30/07) : « débat devrait avoir la salle, inspiré de
Duolingo ; je veux voir toutes les tentatives, les revoir, et comment elles ont
fonctionné, sous un format ludique ». Étude Braignak #44.

Ce qui est repris de Duolingo, et ce qui ne l'est PAS
-----------------------------------------------------
On prend la **pédagogie** : la série qui ramène chaque jour, le déblocage
progressif (les paliers), la petite fête quand on accomplit quelque chose de
vrai. On laisse le **ressort anxiogène** : aucun « ta série va mourir », aucune
fausse tristesse. C'est le contre-Duolingo assumé (décision D7).

La règle qui tient tout : **un chiffre gagné en jouant décore, il n'informe
pas.** Donc ici aucun chiffre n'est saisi ni inventé — chaque nombre est une
SOMME d'enregistrements qui existent déjà (des débats, des avis, des synthèses).
C'est la même doctrine que l'expérience de l'équipe (`tour_equipage`) : la
mesure se lit, elle ne se fabrique pas. Un compteur qu'on pourrait écrire à la
main ne dirait que l'humeur de celui qui l'a écrit.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Les paliers du déblocage progressif. Chacun se gagne sur une activité RÉELLE
# et déjà comptée — jamais un badge décoratif. L'ordre est celui où on les
# franchit d'habitude.
PALIERS = [
    ("premier_debat", "Premier débat", "Tu as lancé ta première question."),
    ("dix_debats", "Dix débats", "Débattre est devenu un réflexe."),
    ("premier_tranche", "Premier débat tranché",
     "Tu as écrit une conclusion — un débat sans conclusion se rejoue à l'identique."),
    ("equipe_entiere", "Toute l'équipe consultée",
     "Un débat où tous ceux qui savent parler ont répondu."),
]


class DebatSalle(models.Model):
    """On greffe la salle sur le débat existant, sans toucher à `debat.py`.

    Séparer les fichiers n'est pas cosmétique : la salle est une lecture
    (des sommes, un affichage) posée sur un moteur (le débat) que d'autres
    mains font évoluer en même temps. Les garder distincts évite de se
    marcher dessus.
    """
    _inherit = "debat.sujet"

    # ------------------------------------------------------------------
    # Les chiffres comptés de la salle.
    # ------------------------------------------------------------------
    def _est_tranche(self):
        """Un débat est « tranché » quand sa synthèse est écrite. Pas quand les
        avis sont rendus : rendre des avis n'est pas décider. La conclusion
        écrite est le seul geste qui prouve que le débat a servi."""
        self.ensure_one()
        return bool((self.synthese or "").strip())

    @api.model
    def _stats_salle(self, debats):
        """Les quatre chiffres de l'en-tête, calculés sur les débats VISIBLES
        passés en argument (donc bornés par les droits de celui qui regarde).

        Rien n'est stocké : on relit à chaque affichage. Une salle qui
        montrerait les chiffres d'hier ferait douter de tous les autres.
        """
        avis = debats.mapped("avis_ids")
        avis_rendus = avis.filtered(lambda a: (a.reponse or "").strip())
        tranches = debats.filtered(lambda d: d._est_tranche())
        return {
            "serie": self._serie_jours(debats),
            "tranches": len(tranches),
            "total": len(debats),
            "avis": len(avis_rendus),
            "retenus": len(avis.filtered("retenu")),
            "paliers": self._paliers(debats),
        }

    @api.model
    def _serie_jours(self, debats):
        """La série : le nombre de jours consécutifs, jusqu'à aujourd'hui, où
        au moins un débat a été lancé OU tranché.

        Deux gestes comptent comme « un jour vivant » : lancer une question
        (`create_date`) et écrire une conclusion (`write_date` d'un débat
        tranché — Odoo ne date pas la synthèse à part, la dernière écriture en
        est la meilleure trace honnête).

        Volontairement PAS de menace : si la série est à zéro parce qu'on a
        sauté hier, la salle le montre sans le reprocher. Le manque se voit, il
        ne culpabilise pas.
        """
        jours = set()
        for d in debats:
            if d.create_date:
                jours.add(fields.Datetime.context_timestamp(d, d.create_date).date())
            if d._est_tranche() and d.write_date:
                jours.add(fields.Datetime.context_timestamp(d, d.write_date).date())
        if not jours:
            return 0
        aujourdhui = fields.Date.context_today(self)
        dernier = max(jours)
        # La série est « vivante » si la dernière activité est aujourd'hui ou
        # hier ; au-delà d'un jour d'écart, elle est retombée à zéro — sans
        # drame, c'est juste un fait.
        if dernier < aujourdhui - timedelta(days=1):
            return 0
        serie = 0
        curseur = dernier
        while curseur in jours:
            serie += 1
            curseur -= timedelta(days=1)
        return serie

    @api.model
    def _paliers(self, debats):
        """L'état de chaque palier (gagné ou pas), dans l'ordre. Chaque test est
        une somme d'enregistrements réels, jamais un drapeau posé à la main."""
        total = len(debats)
        tranches = len(debats.filtered(lambda d: d._est_tranche()))
        # « Toute l'équipe » = un débat où le nombre d'avis atteint le nombre
        # d'agents qui savent parler (ceux qui ont un moteur). S'il n'y a aucun
        # agent parlant, le palier reste hors d'atteinte plutôt que gagné par
        # défaut.
        parlants = 0
        if "equipe.membre" in self.env:
            parlants = self.env["equipe.membre"].sudo().search_count(
                [("moteur", "!=", False)])
        equipe_ok = bool(parlants) and any(
            len(d.avis_ids) >= parlants for d in debats)
        gagnes = {
            "premier_debat": total >= 1,
            "dix_debats": total >= 10,
            "premier_tranche": tranches >= 1,
            "equipe_entiere": equipe_ok,
        }
        return [
            {"code": code, "nom": nom, "aide": aide, "gagne": gagnes.get(code, False)}
            for code, nom, aide in PALIERS
        ]

    # ------------------------------------------------------------------
    # La petite fête — courte, liée à un vrai accomplissement.
    # ------------------------------------------------------------------
    def write(self, vals):
        """Quand une synthèse passe de vide à écrite, le débat vient d'être
        tranché : on le fête une fois, brièvement. C'est la célébration de
        Duolingo « liée à un vrai accomplissement », pas un confetti permanent.
        """
        avant = {}
        if "synthese" in vals:
            avant = {d.id: d._est_tranche() for d in self}
        res = super().write(vals)
        if "synthese" in vals:
            for d in self:
                if not avant.get(d.id) and d._est_tranche():
                    d._feter_tranche()
        return res

    def _feter_tranche(self):
        self.ensure_one()
        if "tour.signal" not in self.env:
            return
        base = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url", "").rstrip("/")
        lien = "%s/tour/debats" % base
        try:
            self.env["tour.signal"]._signaler(
                agent="La salle",
                titre="Débat tranché : %s" % (self.name or "")[:60],
                corps_html="<p>Tu as écrit ta conclusion. Un débat tranché ne se "
                           "rejoue pas trois semaines plus tard à l'identique.</p>"
                           "<p><a href='%s'>Revoir la salle</a></p>" % lien,
                ton="fait",
                enregistrement=self,
            )
        except Exception:  # noqa: BLE001
            _logger.exception("Salle : la fête n'a pas pu partir")

    # ------------------------------------------------------------------
    # Le cron quotidien : rien à recalculer (tout se lit à l'affichage), mais
    # on garde le point d'accroche pour une évolution v2 (rappel espacé des
    # débats jamais tranchés). Aujourd'hui il ne fait qu'un passage à blanc.
    # ------------------------------------------------------------------
    @api.model
    def _cron_salle(self):
        return True
