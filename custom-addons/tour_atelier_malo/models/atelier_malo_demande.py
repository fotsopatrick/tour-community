# -*- coding: utf-8 -*-
# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
"""Une mission confiée à l'atelier Malo : le cerveau local (Ollama, Raspberry).

Le conteneur Odoo écrit la consigne dans un dossier pont partagé avec l'hôte ;
un relais hôte (deploy/pont-malo.sh) la dépose dans l'atelier-malo, qui
l'exécute avec le moteur ollama (aucune clé, qwen2.5:1.5b tourne sur le Pi).
Le relais dépose la réponse dans le même pont, et ce module la relève.
"""
import logging
import os
import time

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

PONT = "/mnt/atelier/pont-malo"


class AtelierMaloDemande(models.Model):
    _name = "atelier.malo.demande"
    _description = "Une mission confiée à l'atelier Malo"
    _order = "create_date desc"

    name = fields.Char("Titre", required=True)
    consigne = fields.Text("Consigne", required=True)
    jeton = fields.Char("Jeton du pont", readonly=True)
    etat = fields.Selection([
        ("attente", "En attente"),
        ("en_cours", "En cours"),
        ("fait", "Terminée"),
        ("echec", "Échec"),
    ], default="attente", required=True)
    reponse = fields.Text("Réponse du cerveau local")
    demandeur = fields.Char("Demandeur",
                            default=lambda self: self.env.user.name)

    # ------------------------------------------------------------------
    def action_envoyer(self):
        """Écrit la consigne dans le pont ; le relais hôte la prend."""
        self.ensure_one()
        if self.jeton:
            return self.jeton
        jeton = "malo-%s-%d" % (time.strftime("%Y%m%d-%H%M%S"), self.id)
        dossier = os.path.join(PONT, "demandes")
        try:
            os.makedirs(dossier, exist_ok=True)
            chemin = os.path.join(dossier, jeton + ".md")
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(self.consigne)
        except OSError as e:
            _logger.warning("Atelier Malo : pont injoignable (%s)", e)
            raise
        self.write({"jeton": jeton})
        _logger.info("Atelier Malo : demande %s posée dans le pont", jeton)
        return jeton

    def _relever(self):
        """Relève les réponses déposées par le relais hôte."""
        dossier = os.path.join(PONT, "reponses")
        if not os.path.isdir(dossier):
            return False
        pris = 0
        for fichier in os.listdir(dossier):
            if not fichier.endswith(".md"):
                continue
            jeton = fichier[:-3]
            demande = self.search([("jeton", "=", jeton)], limit=1)
            if not demande or demande.etat == "fait":
                continue
            try:
                with open(os.path.join(dossier, fichier),
                          "r", encoding="utf-8") as f:
                    reponse = f.read()
            except OSError:
                continue
            demande.write({"etat": "fait", "reponse": reponse})
            pris += 1
        if pris:
            _logger.info("Atelier Malo : %d réponse(s) relevée(s)", pris)
        return bool(pris)

    @api.model
    def _cron_relever(self):
        return self._relever()
