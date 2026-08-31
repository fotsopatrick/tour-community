# -*- coding: utf-8 -*-
"""L'inventaire des modules de la tour.

Le problème, constaté le 31/07 : quarante-neuf modules maison, et personne
n'avait la liste de référence. Chaque session redécouvrait ce qui existe en
lisant le dossier. Cette liste vit dans la tour, se recale seule sur la
réalité, et chaque module porte son état et son responsable.

**Règle d'honnêteté** : l'état d'installation et la version viennent de la
BASE (ir_module_module) et du manifeste — jamais d'une saisie. Ce qui est
saisi à la main, c'est le RESPONSABLE et le statut produit, et ça ne
s'écrase jamais lors d'une synchronisation.
"""
import ast
import logging
import os

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class TourModule(models.Model):
    _name = "tour.module"
    _description = "Module de la tour — inventaire"
    _order = "name"

    name = fields.Char("Module technique", required=True, index=True)
    nom_affichage = fields.Char("Nom affiché")
    installe = fields.Boolean("Installé", default=False)
    version = fields.Char("Version")
    description = fields.Text("Ce qu'il fait")
    agent_id = fields.Many2one("equipe.membre", "Agent responsable")
    statut = fields.Selection(
        [("operationnel", "Opérationnel"),
         ("partiel", "Partiel / à compléter"),
         ("a_faire", "En chantier / à faire"),
         ("archive", "Archivé")],
        string="État produit", default="operationnel")
    notes = fields.Text("Notes")

    _sql_constraints = [("name_unique", "unique(name)",
                         "Ce module est déjà dans l'inventaire.")]

    @api.model
    def _chemins_addons(self):
        """Les dossiers addons de CETTE instance (le montage, pas l'image)."""
        chemins = []
        try:
            from odoo.tools.config import config
            for chemin in config["addons_path"].split(","):
                if "extra-addons" in chemin or "custom-addons" in chemin:
                    chemins.append(chemin.strip())
        except Exception:  # noqa: BLE001
            pass
        return chemins

    def _lire_manifeste(self, dossier):
        """Le nom affiché, la description et la version depuis le manifeste."""
        chemin = os.path.join(dossier, "__manifest__.py")
        if not os.path.isfile(chemin):
            return {}, ""
        try:
            with open(chemin, "r", encoding="utf-8") as f:
                data = ast.literal_eval(f.read())
            return data, chemin
        except Exception:  # noqa: BLE001
            return {}, chemin

    @api.model
    def _synchroniser(self, commit=False):
        """Recale l'inventaire sur la réalité de l'installation.

        Les modules INSTALLÉS sont lus dans ir_module_module (la vérité de
        la base). Les modules PRÉSENTS dans custom-addons mais non installés
        apparaissent aussi, marqués non installés : un module qu'on a écrit
        mais pas posé doit se voir — c'est exactement ce qu'on veut retrouver.
        """
        Modules = self.env["ir.module.module"].sudo()
        en_base = {m.name: m for m in Modules.search([])}
        vus = {}
        for chemin in self._chemins_addons():
            if not os.path.isdir(chemin):
                continue
            for nom in sorted(os.listdir(chemin)):
                dossier = os.path.join(chemin, nom)
                if not os.path.isdir(dossier):
                    continue
                data, _f = self._lire_manifeste(dossier)
                if not data:
                    continue
                m = en_base.get(nom)
                vus[nom] = {
                    "nom_affichage": (data.get("name") or nom)[:120],
                    "installe": bool(m),
                    "version": m and m.latest_version or
                               (data.get("version") or "")[:40],
                    "description": (data.get("description") or "")[:2000],
                }
        if not vus:
            return 0
        existants = {r.name: r for r in self.search([])}
        nb = 0
        for nom, vals in vus.items():
            rec = existants.get(nom)
            if rec:
                rec.write({"installe": vals["installe"],
                           "version": vals["version"],
                           "nom_affichage": vals["nom_affichage"] or rec.nom_affichage,
                           "description": vals["description"] or rec.description})
            else:
                self.create(dict(vals, name=nom))
            nb += 1
        if commit:
            self.env.cr.commit()
        _logger.info("Inventaire : %s modules synchronisés", nb)
        return nb

    @api.model
    def _cron_synchroniser(self):
        """La nuit, l'inventaire se recale tout seul sur la réalité."""
        return self._synchroniser(commit=True)

    def action_synchroniser(self):
        self._synchroniser(commit=True)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Inventaire recalé"),
                "message": _("L'inventaire des modules est à jour."),
                "type": "success",
            },
        }
