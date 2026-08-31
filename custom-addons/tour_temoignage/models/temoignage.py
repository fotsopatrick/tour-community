# -*- coding: utf-8 -*-
"""Témoignages : ce que chacun a vécu, raconté par lui-même.

L'idée est de Patrick (28/07, écrite depuis son téléphone, couché) : le
témoignage de l'agent sur la vitrine dit vrai parce qu'il est né du travail.
Alors on donne l'outil à TOUTE l'équipe : « qu'ils alimentent eux-mêmes leur
témoignage s'ils ont des choses à témoigner — vu qu'ils montent en compétence
et s'entraînent, on aura de vrais témoignages rapidement et sans mentir ».

Le garde-fou est dans la mécanique, pas dans la confiance :

- Une entrée naît d'une MISSION RÉELLE : l'agent termine son compte rendu par
  une section « === TEMOIGNAGE === » quand il a vraiment quelque chose à
  dire. La relève l'extrait — personne n'écrit le témoignage d'un autre.
- La section est FACULTATIVE. Un témoignage obligatoire devient du
  remplissage, et le remplissage est un mensonge poli.
- Chaque entrée garde le lien vers sa mission : le lecteur peut toujours
  remonter à ce qui s'est réellement passé.
- Rien ne part sur la vitrine tout seul : publier reste une décision de
  Patrick (même circuit d'approbation que le reste du public).
"""
import re

from odoo import api, fields, models

MARQUE = "=== TEMOIGNAGE ==="


class TemoignageEntree(models.Model):
    _name = "temoignage.entree"
    _description = "Une entrée de témoignage"
    _order = "quand desc"

    agent = fields.Char("Qui témoigne", required=True, index=True)
    texte = fields.Text("Ce qu'il a vécu", required=True)
    quand = fields.Datetime("Quand", required=True,
                            default=fields.Datetime.now)
    mission_id = fields.Many2one("atelier.mission", "Née de la mission",
                                 ondelete="set null")
    publie = fields.Boolean(
        "Retenu pour la vitrine", default=False,
        help="Coché par le propriétaire : l'entrée pourra nourrir la page "
             "publique — via l'approbation habituelle, jamais toute seule.")

    def _lancer_circuit(self):
        """01/08 : chaque témoignage part dans le CIRCUIT « Témoignage d'un
        agent » — Lois relit (c'est vrai ?) puis Patrick publie. L'agent met
        donc à jour son témoignage tout seul, mais rien ne sort sans le
        regard de la relecture et la validation du propriétaire."""
        if "circuit.instance" not in self.env:
            return False
        Gabarit = self.env["circuit.modele"].sudo().search(
            [("name", "=", "Témoignage d'un agent")], limit=1)
        if not Gabarit:
            return False
        try:
            inst = self.env["circuit.instance"].sudo().create({
                "modele_id": Gabarit.id,
                "name": "Témoignage de %s" % self.agent,
                "sujet": "%s — %s" % (self.agent, self.texte or ""),
                "etat": "brouillon",
            })
            inst.action_lancer()
            return True
        except Exception:  # noqa: BLE001
            return False

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for r in recs:
            r._lancer_circuit()
        return recs


class AtelierMissionTemoignage(models.Model):
    """La relève extrait la section TEMOIGNAGE du compte rendu."""
    _inherit = "atelier.mission"

    def write(self, vals):
        candidats = []
        if vals.get("etat") == "terminee" and vals.get("reponse"):
            candidats = [m.id for m in self if m.etat == "envoyee"]
        res = super().write(vals)
        if candidats and "temoignage.entree" in self.env:
            for m in self.browse(candidats):
                texte = self._temoignage_extraire(m.reponse or "")
                if not texte:
                    continue
                agent = m.AGENTS.get((m.moteur or "").strip(), "L atelier")
                if "debat.avis" in self.env:
                    avis = self.env["debat.avis"].sudo().search(
                        [("mission_id", "=", m.id)], limit=1)
                    if avis:
                        agent = avis.membre_id.name
                self.env["temoignage.entree"].sudo().create({
                    "agent": agent, "texte": texte, "mission_id": m.id})
        return res

    @staticmethod
    def _temoignage_extraire(reponse):
        i = reponse.find(MARQUE)
        if i < 0:
            return ""
        texte = reponse[i + len(MARQUE):]
        # La section s'arrête au prochain séparateur de section.
        j = re.search(r"\n(?:===|---|## )", texte)
        if j:
            texte = texte[:j.start()]
        return texte.strip()[:2000]
