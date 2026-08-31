# -*- coding: utf-8 -*-
"""La détection de compétence, branchée sur les agents (31/07).

Patrick : « vois si la compétence détection de compétence peut se brancher à
toi, et si elle voit un truc qui peut servir de circuit elle le consigne en
brouillons et on pourra l'activer. Branche-la à tous les agents. »

Le geste : à la création d'une compétence (en direct, par un humain), on
demande au moteur de circuits de PROPOSER un gabarit en brouillon. La
proposition est inactive tant que Patrick ne l'active pas : la détection ne
décide jamais, elle propose.

Garde-fous :
- pendant l'installation du module (install_mode) on ne détecte rien, sinon
  les compétences de seed fabriqueraient un mur de brouillons ;
- pendant une mesure XP (mesure_xp) on ne détecte rien non plus ;
- une détection qui échoue ne casse jamais la création de la compétence.
"""
from odoo import _, api, models

import logging

_logger = logging.getLogger(__name__)


class EquipeCompetenceDetection(models.Model):
    _inherit = "equipe.competence"

    # Les motifs de mission qui se répètent chez les constructeurs (opencode,
    # raphael) deviennent des compétences DÉTECTÉES -> circuit brouillon.
    MOTEURS_CONSTRUCTEURS = ("opencode", "raphael")
    SEUIL_REPETITION = 3
    PREFIXES_A_OTER = (
        "suite :", "reproposition :", "donner suite :", "tache ",
        "[à confirmer]", "[a faire]", "[a confirmer]", "urgence :",
    )

    @api.model
    def _motif_mission(self, nom):
        """Normalise un nom de mission en motif : sans préfixes, sans numéro
        de tâche, minuscules, borné à 60 caractères. « Suite : Tache 892 —
        corriger X » devient « corriger x »."""
        import re
        n = (nom or "").lower()
        for prefixe in self.PREFIXES_A_OTER:
            if n.startswith(prefixe):
                n = n[len(prefixe):].lstrip("—:- ").strip()
        n = re.sub(r"[0-9]+", "", n)
        n = re.sub(r"[^a-zàâäéèêëîïôöùûüç\s]", " ", n)
        n = re.sub(r"\s+", " ", n).strip()[:60]
        return n or None

    @api.model
    def _slug(self, texte):
        import re
        return re.sub(r"[^a-z0-9]+", "_", (texte or "").lower())[:48].strip("_")

    @api.model
    def _detecter_competences(self):
        """Scanne les missions terminées des constructeurs (opencode, raphael)
        et crée une compétence par motif récurrent (>= SEUIL_REPETITION).

        La création de la compétence déclenche le hook existant
        (_detecter_competence) : le circuit brouillon naît tout seul. La
        détection ne décide jamais : un brouillon reste inactif tant que
        Patrick ne l'active pas."""
        if "atelier.mission" not in self.env or "equipe.membre" not in self.env:
            return 0
        Comp = self.env["equipe.competence"].sudo()
        Mission = self.env["atelier.mission"].sudo()
        raphael = self.env["equipe.membre"].sudo().search(
            [("name", "ilike", "raphaël")], limit=1)
        if not raphael:
            return 0
        missions = Mission.search(
            [("etat", "=", "terminee"),
             ("moteur", "in", list(self.MOTEURS_CONSTRUCTEURS))],
            order="create_date desc", limit=300)
        motifs = {}
        for m in missions:
            motif = self._motif_mission(m.name)
            if motif:
                motifs[motif] = motifs.get(motif, 0) + 1
        cree = 0
        for motif, n in motifs.items():
            if n < self.SEUIL_REPETITION:
                continue
            code = "detect_" + self._slug(motif)
            if Comp.search([("code", "=", code)], limit=1):
                continue
            try:
                Comp.create({
                    "name": "%s (détecté)" % motif[:60],
                    "code": code,
                    "membre_id": raphael.id,
                })
                cree += 1
            except Exception:  # noqa: BLE001
                continue
        if cree:
            _logger.info("compétences détectées sur le travail de Raphaël : %s", cree)
        return cree

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        if self._context.get("install_mode") or self._context.get("mesure_xp"):
            return recs
        if "circuit.modele" not in self.env:
            return recs
        try:
            Circuit = self.env["circuit.modele"].sudo()
            for c in recs:
                Circuit._detecter_competence(c)
        except Exception as exc:  # noqa: BLE001
            # La détection ne doit jamais empêcher une compétence de naître,
            # mais une détection qui échoue doit se voir dans les logs.
            _logger.warning("détection de compétence en échec : %s", exc)
        return recs
