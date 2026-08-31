# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
"""Petit moteur de circuits de l'édition Community.

L'édition complète porte le vrai moteur de circuits et sa gouvernance. Ici,
la brique Community propose des circuits simples : une liste d'étapes qui
deviennent de vraies tâches dans la Tour. C'est honnête et vérifiable — les
tâches créées apparaissent dans le dashboard, comme le reste."""

from odoo import api, fields, models


class WebMCPCircuit(models.Model):
    _name = "webmcp.circuit"
    _description = "Circuit exécutable de la Tour (Community)"
    _order = "name"

    name = fields.Char(string="Nom", required=True)
    description = fields.Text(string="Description")
    active = fields.Boolean(string="Actif", default=True)
    etape_ids = fields.One2many("webmcp.circuit.etape", "circuit_id",
                                string="Étapes", copy=True)
    nb_etapes = fields.Integer(string="Étapes", compute="_compute_nb_etapes")

    @api.depends("etape_ids")
    def _compute_nb_etapes(self):
        for circuit in self:
            circuit.nb_etapes = len(circuit.etape_ids)

    def executer(self):
        """Exécute le circuit : chaque étape crée une tâche réelle."""
        creees = []
        for etape in self.etape_ids:
            titre = etape.name
            if not titre:
                continue
            vals = {"name": titre}
            if etape.consigne:
                vals["description"] = "<p>%s</p>" % (
                    etape.consigne.replace("\n", "<br/>"))
            tache = self.env["project.task"].create(vals)
            creees.append({"nom": titre, "tache_id": tache.id})
        return creees


class WebMCPCircuitEtape(models.Model):
    _name = "webmcp.circuit.etape"
    _description = "Étape d'un circuit"
    _order = "sequence, id"

    circuit_id = fields.Many2one("webmcp.circuit", string="Circuit",
                                 ondelete="cascade", required=True)
    sequence = fields.Integer(string="Ordre", default=10)
    name = fields.Char(string="Tâche à créer", required=True)
    consigne = fields.Text(string="Consigne / description")