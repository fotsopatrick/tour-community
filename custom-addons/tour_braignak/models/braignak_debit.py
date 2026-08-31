# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
"""Le plafond du chat public de Braignak, compté DANS LA BASE.

Avant (06/08) : le compteur vivait dans un dictionnaire du processus. Odoo
tourne avec `workers = 4` : chaque worker avait donc son propre plafond, et
la limite réelle valait QUATRE FOIS celle annoncée — 20 messages par heure
et par IP au lieu de 5, 800 par jour au lieu de 200. Sur une route publique
qui dépense des jetons DeepSeek, un plafond faux coûte de l'argent.

Un compteur partagé se compte là où tous les workers regardent : la base.
"""
from datetime import timedelta

from odoo import api, fields, models

MAX_PAR_IP = 5       # messages / heure / IP
FENETRE = 3600       # secondes
MAX_PAR_JOUR = 200   # plafond quotidien global (budget)
GARDE_JOURS = 2      # au-delà, les traces ne servent plus à rien


class BraignakDebit(models.Model):
    _name = "braignak.debit"
    _description = "Braignak — passages du chat public (pour le plafond)"
    _order = "id desc"
    # Pas de log de modification : ce sont des lignes jetables, pas des faits
    # de gestion. Elles n'ont rien à faire dans le fil de discussion.
    _log_access = True

    ip = fields.Char("Adresse", index=True, required=True)

    @api.model
    def _autorise(self, ip):
        """Vrai si ce passage est permis, et alors il est compté.

        Le comptage et l'écriture sont dans la même transaction : deux workers
        qui arrivent ensemble ne peuvent pas passer tous les deux au-dessus du
        plafond sans que l'un des deux le voie.
        """
        ip = (ip or "?")[:64]
        maintenant = fields.Datetime.now()

        # Ménage : les lignes vieilles ne servent plus qu'à grossir la table.
        vieilles = self.search(
            [("create_date", "<", maintenant - timedelta(days=GARDE_JOURS))])
        if vieilles:
            vieilles.unlink()

        depuis = maintenant - timedelta(seconds=FENETRE)
        if self.search_count([("ip", "=", ip),
                              ("create_date", ">=", depuis)]) >= MAX_PAR_IP:
            return False

        debut_jour = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
        if self.search_count([("create_date", ">=", debut_jour)]) >= MAX_PAR_JOUR:
            return False

        self.create({"ip": ip})
        return True

    @api.model
    def _etat(self, ip=None):
        """Ce que le plafond voit en ce moment. Sert au banc d'essai.

        Un garde qui ne sait pas dire où il en est ne se teste pas : on ne
        peut que le croire.
        """
        maintenant = fields.Datetime.now()
        debut_jour = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
        etat = {
            "aujourdhui": self.search_count([("create_date", ">=", debut_jour)]),
            "plafond_jour": MAX_PAR_JOUR,
            "plafond_ip": MAX_PAR_IP,
        }
        if ip:
            depuis = maintenant - timedelta(seconds=FENETRE)
            etat["cette_ip"] = self.search_count(
                [("ip", "=", ip), ("create_date", ">=", depuis)])
        return etat
