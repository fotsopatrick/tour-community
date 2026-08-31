# -*- coding: utf-8 -*-
"""Faire disparaître ce qu'on ne vend pas, et couper ce qui téléphone dehors.

Demandé par Patrick le 28/07 : « les modules d'Odoo qui demandent un abonnement,
peux-tu les lister comme modules à reproduire et les retirer de ce qui
s'affiche ? »

Oui, et il y a **deux familles**, qu'il ne faut surtout pas confondre — la
seconde est bien plus gênante que la première.

**1. Les vingt-et-une publicités.** Odoo Community affiche dans Applications
les modules de l'édition payante, avec un bouton « Mettre à niveau ». Ils ne
sont pas installés, ils ne font rien : ce sont des annonces. Sur une tour
débrandée, c'est un trou franc — un client y découvre qu'il existe un produit
au-dessus, et lequel. Tout le travail de débranding tombe sur cet écran-là.

**2. Les sept modules installés qui appellent les serveurs d'Odoo.** Ceux-là
ne sont pas des annonces : ils tournent. `partner_autocomplete` envoie des
données de contact chez Odoo pour les compléter, toutes les heures. Sur une
instance cliente, ce sont **les contacts du client** qui partent. `sms` et
`snailmail` facturent à l'unité. Personne n'a rien demandé, et rien ne le dit.

Ce qu'on fait, et ce qu'on ne fait pas
--------------------------------------
On MASQUE la première famille (`to_buy = False`) : réversible d'un clic, et
aucun code d'Odoo ne s'exécute différemment pour autant.

On DÉSACTIVE les tâches planifiées de la seconde, on ne désinstalle pas. Une
désinstallation entraîne ses dépendants — `sms` est requis par des modules de
vente — et un module retiré emporte parfois des données au passage. Couper la
tâche suffit : plus aucun appel ne part, et tout se rallume en cochant une case.

C'est une `<function>` rejouée à chaque mise à jour du module, et pas un script
lancé une fois : `to_buy` est repositionné par Odoo à chaque mise à jour de la
liste des applications. Un nettoyage fait une seule fois se défait tout seul,
sans que personne le remarque.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Les tâches planifiées qui sortent de la machine. Repérées par le nom XML
# plutôt que par leur libellé : un libellé est traduit, donc introuvable dès
# que la base n'est pas en anglais.
CRONS_SORTANTS = [
    # Complète les fiches contact en interrogeant les serveurs d'Odoo. C'est
    # celui qui pose un vrai problème : il fait sortir des données clients.
    "partner_autocomplete.ir_cron_partner_autocomplete",
    # Vérifie les numéros de TVA via le service payant d'Odoo (VIES passe par
    # IAP). Le contrôle de TVA local, lui, continue de fonctionner.
    "base_vat_autocomplete.ir_cron_vat_autocomplete",
    # File d'envoi de SMS : facturés à l'unité, crédits achetés chez Odoo.
    "sms.ir_cron_sms_scheduler_action",
    # Courrier postal payant.
    "snailmail.snailmail_print",
]


class MasquerEntreprise(models.AbstractModel):
    _name = "tour.masquer.entreprise"
    _description = "Retire les modules payants de l'affichage"

    @api.model
    def appliquer(self):
        """Masque les publicités, coupe les appels sortants. Rejouable."""
        self._masquer_publicites()
        self._couper_sortants()
        return True

    @api.model
    def _masquer_publicites(self):
        Module = self.env["ir.module.module"].sudo()
        # `to_buy` marque les modules de l'édition payante. On ne touche pas à
        # l'état d'installation : ils ne sont pas installés, et ils ne le
        # seront pas — on les retire de la vitrine, c'est tout.
        vitrines = Module.search([("to_buy", "=", True)])
        if not vitrines:
            return
        noms = vitrines.mapped("name")
        vitrines.write({"to_buy": False})
        _logger.info(
            "Debranding : %s module(s) de l'edition payante retire(s) de "
            "l'affichage : %s", len(noms), ", ".join(sorted(noms)))

    @api.model
    def _couper_sortants(self):
        coupes = []
        for xmlid in CRONS_SORTANTS:
            # `ref` avec `raise_if_not_found=False` : tous ces modules ne sont
            # pas forcement installes sur toutes les instances, et l'absence
            # de l'un ne doit pas faire echouer le chargement du theme.
            cron = self.env.ref(xmlid, raise_if_not_found=False)
            if cron and cron.active:
                cron.sudo().write({"active": False})
                coupes.append(xmlid)
        if coupes:
            _logger.info(
                "Debranding : %s tache(s) planifiee(s) qui appelaient les "
                "serveurs d'Odoo ont ete coupees : %s",
                len(coupes), ", ".join(coupes))
