# -*- coding: utf-8 -*-
"""Tess — ce que ça coûte, ce que ça rapporte, et la date où ça coince.

Trois métiers demandés par Patrick — analyste produit, contrôle de gestion,
business analyst — parce qu'ils répondent à la même question sous trois angles :
**est-ce que ça tient ?**

Deux règles de construction, et elles comptent plus que les chiffres :

**Zéro intelligence artificielle.** Ce sont des comptages et des divisions. Un
chiffre de gestion doit rendre le même résultat deux fois de suite, sinon on ne
peut pas le comparer d'un mois à l'autre — et un indicateur qu'on ne peut pas
comparer ne sert à rien. C'est la même règle que Victor.

**Elle alerte sur la PENTE, pas sur le niveau.** « 12 instances » ne dit rien.
« 12 instances, +4 cette semaine, plafond dans 9 semaines » dit tout. Un seuil
fixe prévient toujours trop tard : quand on l'atteint, il est déjà trop tard
pour commander un serveur.

**Ce qu'elle ne fait pas : décider.** Elle donne le chiffre et l'échéance.
Couper une dépense ou monter un prix, c'est une décision — et une décision se
prend par quelqu'un qui en assume les conséquences.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Les constantes de coût. Écrites ici, en clair, plutôt que devinées : le jour
# où le VPS change de prix, on change UNE ligne et tous les relevés suivants
# sont justes. Les anciens gardent le chiffre de leur époque, ce qui est
# exactement ce qu'on veut d'un historique.
COUT_VPS_MOIS = 15.0        # EUR — VPS OVH
MO_PAR_INSTANCE = 350.0     # Mo occupés par une instance client
PLAFOND_INSTANCES = 50      # au-delà, le cron d'Odoo scanne trop de bases
FRAIS_STRIPE_FIXE = 0.25    # EUR par transaction
FRAIS_STRIPE_PCT = 0.015    # 1,5 %


class TessReleve(models.Model):
    """Un relevé = une photo datée. On ne modifie jamais un relevé passé.

    C'est ce qui permet de calculer une pente : deux photos et une soustraction.
    Corriger rétroactivement un chiffre de gestion, c'est perdre la seule chose
    qui avait de la valeur — la comparaison.
    """

    _name = "tess.releve"
    _description = "Relevé de Tess : coûts, usage, marge"
    _order = "date desc, id desc"
    _rec_name = "date"

    date = fields.Date("Date", required=True, default=fields.Date.context_today, index=True)

    # --- Ce qui sort (contrôle de gestion) ---
    cout_serveur = fields.Float("Serveur (EUR/mois)", readonly=True)
    cout_ia = fields.Float("Intelligence artificielle (EUR/mois)", readonly=True)
    cout_paiement = fields.Float("Frais de paiement (EUR/mois)", readonly=True)
    cout_total = fields.Float("Total des dépenses", compute="_calculer", store=True)

    # --- Ce qui rentre (business analyst) ---
    recette = fields.Float("Recettes (EUR/mois)", readonly=True)
    marge = fields.Float("Marge", compute="_calculer", store=True)

    # --- Ce qui est utilisé (analyste produit) ---
    nb_instances = fields.Integer("Instances actives", readonly=True)
    nb_contrats = fields.Integer("Contrats actifs", readonly=True)
    nb_utilisateurs = fields.Integer("Utilisateurs", readonly=True)
    disque_mo = fields.Float("Disque occupé (Mo)", readonly=True)

    # --- La pente et l'échéance ---
    instances_semaine = fields.Float("Nouvelles instances / semaine", readonly=True)
    semaines_avant_plafond = fields.Integer(
        "Semaines avant le plafond", readonly=True,
        help="Au rythme actuel. 0 = plafond déjà atteint, -1 = aucune croissance.")
    alerte = fields.Char("Ce qui coince", readonly=True)

    @api.depends("cout_serveur", "cout_ia", "cout_paiement", "recette")
    def _calculer(self):
        for r in self:
            r.cout_total = (r.cout_serveur or 0) + (r.cout_ia or 0) + (r.cout_paiement or 0)
            r.marge = (r.recette or 0) - r.cout_total

    # ------------------------------------------------------------------
    @api.model
    def _cron_relever(self):
        """Une photo par jour. Ne lève jamais : un cron qui plante s'éteint."""
        try:
            return self._relever()
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Tess : relevé impossible (%s)", exc)
            return False

    @api.model
    def _relever(self):
        vals = {"date": fields.Date.context_today(self)}
        vals.update(self._mesurer_usage())
        vals.update(self._mesurer_couts(vals))
        vals.update(self._mesurer_pente(vals))
        releve = self.create(vals)
        releve._prevenir_si_besoin()
        return releve

    def _compter(self, modele, domaine):
        """Compte sans jamais faire tomber le relevé entier.

        Chaque source dans son propre point de reprise : un module absent chez
        un client ne doit pas priver Tess de tous ses autres chiffres.
        """
        if modele not in self.env:
            return 0
        try:
            with self.env.cr.savepoint():
                return self.env[modele].sudo().search_count(domaine)
        except Exception:
            return 0

    @api.model
    def _mesurer_usage(self):
        contrats = self._compter("abonnement.contrat", [("etat", "=", "actif")])
        instances = self._compter("abonnement.contrat",
                                  [("instance_etat", "=", "montee")])
        users = self._compter("res.users", [("active", "=", True), ("share", "=", False)])
        return {
            "nb_contrats": contrats,
            "nb_instances": instances,
            "nb_utilisateurs": users,
            "disque_mo": instances * MO_PAR_INSTANCE,
        }

    @api.model
    def _mesurer_couts(self, deja):
        """Ce qui sort réellement. Aucun chiffre inventé : quand une source
        n'existe pas, la ligne vaut zéro et ça se voit."""
        # L'IA : seule Chloe consomme une clé d'API. On lit sa consommation si
        # le module la tient, sinon zéro — mieux qu'une estimation flatteuse.
        cout_ia = 0.0
        if "copilote.usage" in self.env:
            try:
                with self.env.cr.savepoint():
                    Usage = self.env["copilote.usage"].sudo()
                    champ = next((c for c in ("cout", "cout_eur", "montant")
                                  if c in Usage._fields), None)
                    if champ:
                        debut = fields.Date.subtract(fields.Date.context_today(self), days=30)
                        lignes = Usage.search([("create_date", ">=", debut)])
                        cout_ia = sum(lignes.mapped(champ) or [0.0])
            except Exception:
                cout_ia = 0.0

        # Les frais de paiement : par transaction encaissée sur 30 jours.
        cout_paiement, recette = 0.0, 0.0
        if "abonnement.contrat" in self.env:
            try:
                with self.env.cr.savepoint():
                    C = self.env["abonnement.contrat"].sudo()
                    actifs = C.search([("etat", "=", "actif")])
                    for c in actifs:
                        prix = getattr(c.offre_id, "prix", 0.0) or 0.0
                        recette += prix
                        cout_paiement += FRAIS_STRIPE_FIXE + prix * FRAIS_STRIPE_PCT
            except Exception:
                pass
        return {"cout_serveur": COUT_VPS_MOIS, "cout_ia": cout_ia,
                "cout_paiement": cout_paiement, "recette": recette}

    @api.model
    def _mesurer_pente(self, deja):
        """La pente, et la date où ça coince. C'est la partie qui sert."""
        precedent = self.search([], order="date desc", limit=1)
        instances = deja.get("nb_instances", 0)
        pente = 0.0
        if precedent and precedent.date:
            jours = (fields.Date.context_today(self) - precedent.date).days or 1
            pente = (instances - precedent.nb_instances) * 7.0 / jours

        reste = PLAFOND_INSTANCES - instances
        if reste <= 0:
            semaines = 0
        elif pente <= 0:
            semaines = -1          # pas de croissance : aucune échéance
        else:
            semaines = int(reste / pente)

        alerte = ""
        if semaines == 0:
            alerte = "Plafond d'instances atteint (%s)" % PLAFOND_INSTANCES
        elif 0 < semaines <= 8:
            alerte = "Plafond d'instances dans ~%s semaines" % semaines
        return {"instances_semaine": pente, "semaines_avant_plafond": semaines,
                "alerte": alerte}

    def _prevenir_si_besoin(self):
        """Elle ne parle que quand il y a quelque chose à décider.

        Une alerte qui arrive tous les jours n'est plus une alerte : on apprend
        à l'ignorer, et on ignore ensuite celle qui comptait.
        """
        self.ensure_one()
        raisons = []
        if self.alerte:
            raisons.append(self.alerte)
        if self.recette and self.marge < 0:
            raisons.append("La marge est négative : %.2f EUR" % self.marge)
        if not raisons or "tour.signal" not in self.env:
            return
        corps = (
            "<p>%s</p>"
            "<ul><li>Instances : <b>%s</b> (%+.1f par semaine)</li>"
            "<li>Dépenses : <b>%.2f EUR/mois</b> — serveur %.2f, IA %.2f, "
            "paiements %.2f</li>"
            "<li>Recettes : <b>%.2f EUR/mois</b> — marge <b>%.2f</b></li></ul>"
            "<p><i>Je donne le chiffre et l'échéance. La décision est à toi.</i></p>"
        ) % ("</p><p>".join(raisons), self.nb_instances, self.instances_semaine,
             self.cout_total, self.cout_serveur, self.cout_ia, self.cout_paiement,
             self.recette, self.marge)
        self.env["tour.signal"]._signaler(
            agent="Tess", titre="Les chiffres demandent une décision",
            corps_html=corps, ton="attention")
