# -*- coding: utf-8 -*-
"""Le registre des appels API faits avec la clé DeepSeek.

C'est la partie VISIBLE du garde-fou. La partie qui refuse et consigne vit
sur l'hôte (compter_appel.py) ; ici on relève le journal et on l'affiche —
« ce qui consomme encore des tokens ».
"""
import json
import logging
from datetime import datetime, timezone

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

JOURNAL = "/mnt/atelier/appels-api.jsonl"
PARAM_DERNIER = "api.appel.dernier_ingere"

# Tarifs DeepSeek, mêmes que le copilote : euros par million de jetons.
PE, PS = 0.25, 1.0


class AppelApi(models.Model):
    _name = "api.appel"
    _description = "Appel API DeepSeek"
    _order = "horodatage desc"

    horodatage = fields.Datetime("Quand", readonly=True, index=True)
    date = fields.Date("Jour", readonly=True, index=True)
    agent = fields.Char("Agent", readonly=True, index=True)
    mission = fields.Char("Mission", readonly=True)
    mission_nom = fields.Char(
        "Nom de la mission", readonly=True,
        help="Le nom de la mission résolu au relevé : il survit à la "
             "suppression de la mission et garde la trace du circuit.")
    moteur = fields.Char("Moteur", readonly=True)
    modele = fields.Char("Modèle", readonly=True)
    prompt = fields.Text(
        "Demande",
        readonly=True,
        help="Ce qui a déclenché l'appel : la consigne/la question posée "
             "(tronquée au garde-fou). Pour savoir QUELLE demande a coûté.")
    tokens_entree = fields.Integer("Jetons entrée", readonly=True)
    tokens_sortie = fields.Integer("Jetons sortie", readonly=True)
    cout_estime = fields.Float(
        "Coût estimé (€)", compute="_compute_cout", digits=(12, 6))
    refuse = fields.Boolean(
        "Refusé (budget)", readonly=True,
        help="Vrai quand le garde-fou a refusé l'appel : le budget du jour "
             "était épuisé, la mission s'est arrêtée.")

    @api.depends("tokens_entree", "tokens_sortie")
    def _compute_cout(self):
        for r in self:
            r.cout_estime = ((r.tokens_entree or 0) / 1e6) * PE + \
                ((r.tokens_sortie or 0) / 1e6) * PS

    @api.model
    def _relever(self):
        """Relève le journal de l'hôte et crée les enregistrements manquants.

        Idempotent : on ne reprend que ce qui est postérieur au dernier
        horodatage déjà ingéré. La lecture ne casse jamais si le fichier
        manque ou si une ligne est corrompue.
        """
        import os
        if not os.path.exists(JOURNAL):
            return 0
        icp = self.env["ir.config_parameter"].sudo()
        dernier = int(icp.get_param(PARAM_DERNIER, "0") or 0)
        nouvelles = []
        try:
            with open(JOURNAL, encoding="utf-8") as f:
                for ligne in f:
                    try:
                        d = json.loads(ligne)
                    except ValueError:
                        continue
                    h = int(d.get("horodatage") or 0)
                    if h <= dernier:
                        continue
                    nouvelles.append(d)
        except OSError:
            return 0
        if not nouvelles:
            return 0
        max_h = max(int(d.get("horodatage") or 0) for d in nouvelles)
        for d in nouvelles:
            if self.sudo().search_count([
                    ("horodatage", "=", datetime.fromtimestamp(
                        int(d.get("horodatage") or 0),
                        timezone.utc).replace(tzinfo=None)),
                    ("agent", "=", d.get("agent", "")),
                    ("mission", "=", d.get("mission", ""))]):
                continue
            nom_mission = ""
            mid = (d.get("mission") or "").strip()
            if mid.isdigit():
                m_mission = self.env["atelier.mission"].sudo().browse(
                    int(mid))
                if m_mission.exists():
                    nom_mission = m_mission.name or ""
            try:
                self.sudo().create({
                    "horodatage": datetime.fromtimestamp(
                        int(d.get("horodatage") or 0),
                        timezone.utc).replace(tzinfo=None),
                    "date": d.get("date") or None,
                    "agent": (d.get("agent") or "")[:80],
                    "mission": (d.get("mission") or "")[:64],
                    "mission_nom": (nom_mission or "")[:120],
                    "moteur": (d.get("moteur") or "")[:40],
                    "modele": (d.get("modele") or "")[:60],
                    "prompt": (d.get("prompt") or "")[:400],
                    "tokens_entree": int(d.get("tokens_entree") or 0),
                    "tokens_sortie": int(d.get("tokens_sortie") or 0),
                    "refuse": bool(d.get("refuse")),
                })
            except Exception as exc:  # noqa: BLE001
                _logger.warning("api.appel : ligne ignorée (%s) : %s", exc, ligne)
        icp.set_param(PARAM_DERNIER, str(max_h))
        return len(nouvelles)
