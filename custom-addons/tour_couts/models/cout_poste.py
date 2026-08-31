# -*- coding: utf-8 -*-
"""Ce que coûte chaque partie du logiciel.

Patrick, le 29/07 : « que nous coûte l'automatisation en ressource ? ça
signifie quoi en argent ? on peut sûrement déployer quelque chose qui nous dit
ce que coûte chaque partie du logiciel ».

La question est juste, et elle n'avait aucune réponse : on savait dépenser sans
savoir où. Ce module tient une ligne par dépense, la ramène toujours à un coût
MENSUEL (sinon on compare des choux et des carottes), et la rattache aux projets
qu'elle sert.

**Trois règles, et la première est la plus importante.**

1. **Un montant est MESURÉ ou DÉCLARÉ, jamais deviné.** Une ligne mesurée est
   recalculée par la tour à partir de ses propres traces (les jetons consommés,
   par exemple). Une ligne déclarée vient d'une facture que quelqu'un a lue. Un
   chiffre qui ne serait ni l'un ni l'autre serait pire que pas de chiffre : on
   prendrait des décisions dessus.
2. **Un coût commun se partage, il ne se duplique pas.** Le serveur sert huit
   projets : compter 9 € sur chacun en ferait 72 € qui n'existent pas.
3. **Ce qui ne coûte rien doit apparaître à zéro.** L'automatisation des
   courriels ne coûte rien de plus que le serveur déjà payé — et c'est une
   information, pas un vide. Une ligne absente se lit « on ne sait pas » ; une
   ligne à zéro se lit « on a regardé ».
"""
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

CATEGORIES = [
    ("serveur", "Serveur et hébergement"),
    ("modele", "Modèles d'IA (jetons)"),
    ("abonnement", "Abonnements logiciels"),
    ("domaine", "Domaines et courriel"),
    ("stockage", "Stockage et sauvegardes"),
    ("service", "Services extérieurs"),
    ("humain", "Temps humain"),
    ("autre", "Autre"),
]

PERIODICITES = [
    ("mensuel", "Par mois"),
    ("annuel", "Par an"),
    ("usage", "À l'usage"),
    ("unique", "Une seule fois"),
]


class CoutPoste(models.Model):
    _name = "cout.poste"
    _description = "Poste de coût"
    _order = "categorie, name"

    name = fields.Char("Ce que c'est", required=True)
    categorie = fields.Selection(CATEGORIES, "Catégorie", required=True,
                                 default="autre", index=True)
    fournisseur = fields.Char("Chez qui")
    montant = fields.Float("Montant (€)", digits=(12, 4))
    periodicite = fields.Selection(PERIODICITES, "Rythme", required=True,
                                   default="mensuel")
    montant_mensuel = fields.Float(
        "Par mois (€)", compute="_compute_mensuel", store=True, digits=(12, 4),
        help="Tout est ramené au mois : sinon on compare un abonnement annuel "
             "à une facture d'API et on ne conclut rien.")
    mesure = fields.Boolean(
        "Mesuré par la tour", default=False,
        help="Coché : le montant est recalculé à partir des traces de la tour. "
             "Décoché : quelqu'un l'a lu sur une facture.")
    a_confirmer = fields.Boolean(
        "Montant à confirmer", default=False,
        help="Le chiffre est approximatif ou inconnu. Une ligne à confirmer "
             "ne doit jamais servir à décider.")
    app_ids = fields.Many2many(
        "app.suivi", string="Pour quels projets",
        help="Laisser vide si la dépense sert TOUT : elle sera alors partagée "
             "entre les projets actifs, pas comptée sur chacun.")
    commun = fields.Boolean("Dépense commune", compute="_compute_commun",
                            store=True)
    note = fields.Text("Détail")
    date_mesure = fields.Datetime("Dernière mesure", readonly=True)
    active = fields.Boolean("Actif", default=True)

    @api.depends("montant", "periodicite")
    def _compute_mensuel(self):
        for r in self:
            if r.periodicite == "annuel":
                r.montant_mensuel = (r.montant or 0.0) / 12.0
            elif r.periodicite == "unique":
                # Une dépense unique n'est pas un coût mensuel. La compter
                # comme tel gonflerait le total tous les mois, indéfiniment.
                r.montant_mensuel = 0.0
            else:
                r.montant_mensuel = r.montant or 0.0

    @api.depends("app_ids")
    def _compute_commun(self):
        for r in self:
            r.commun = not r.app_ids

    # ------------------------------------------------------------------
    @api.model
    def _cron_mesurer(self):
        """Recalcule les lignes que la tour sait mesurer elle-même."""
        return self._mesurer() and self._mesurer_atelier()

    @api.model
    def _mesurer(self):
        """Les jetons consommés deviennent des euros.

        C'est la seule dépense que la tour connaît de l'intérieur : chaque
        appel au modèle laisse sa trace dans copilote.usage, avec son coût
        estimé. On somme les trente derniers jours — pas le mois calendaire :
        un premier du mois afficherait presque zéro et donnerait l'illusion
        d'avoir arrêté de dépenser.
        """
        poste = self.sudo().search([("mesure", "=", True),
                                    ("categorie", "=", "modele")], limit=1)
        if not poste:
            return False
        if "copilote.usage" not in self.env:
            return False
        self.env.cr.execute("""
            SELECT coalesce(sum(cout_estime), 0), coalesce(sum(tokens_entree), 0),
                   coalesce(sum(tokens_sortie), 0), count(*)
            FROM copilote_usage WHERE jour > current_date - interval '30 days'
        """)
        cout, entree, sortie, appels = self.env.cr.fetchone()
        poste.write({
            "montant": cout,
            "periodicite": "mensuel",
            "a_confirmer": False,
            "date_mesure": fields.Datetime.now(),
            "note": _(
                "Mesuré sur 30 jours glissants : %(a)s appels, %(e)s jetons "
                "en entrée, %(s)s en sortie. Ce sont les appels facturés à la "
                "clé d'API (Chloe). Ce qui passe par l'abonnement du serveur "
                "— l'atelier, Clark, Lois, Braignak — ne coûte rien de plus "
                "que l'abonnement lui-même et n'est pas compté ici.",
                a=appels, e=entree, s=sortie),
        })
        _logger.info("Coûts : poste des modèles mesuré à %.4f EUR", cout or 0)
        return True

    @api.model
    def _mesurer_atelier(self):
        """Le travail des agents sur l'abonnement, mesuré en USAGE.

        Le poste « L'abonnement qui fait tourner les agents » n'a pas de
        montant mesurable par la tour (le prix vit dans la facture que Patrick
        déclare) — mais son USAGE, lui, est mesurable : combien de missions
        les moteurs `claude`/`braignak`/`lois`/`discussion` ont-ils menées sur
        les 30 derniers jours ? Sans ce chiffre, la ligne d'abonnement est un
        trou : on sait ce qu'elle coûte « à confirmer », on ne sait pas ce
        qu'elle produit. Le dénombrement devient la note de la ligne, datée.
        """
        poste = self.sudo().search(
            [("name", "ilike", "%abonnement qui fait tourner les agents%")],
            limit=1)
        if not poste or "atelier.mission" not in self.env:
            return False
        self.env.cr.execute("""
            SELECT moteur, count(*), min(create_date)::date, max(create_date)::date
            FROM atelier_mission
            WHERE etat = 'terminee' AND create_date > current_date - interval '30 days'
            GROUP BY moteur ORDER BY count(*) DESC
        """)
        lignes = self.env.cr.fetchall()
        if not lignes:
            return False
        detail = "; ".join(
            "%s : %s missions (du %s au %s)" % (m or "?", n, d1, d2)
            for m, n, d1, d2 in lignes)
        total = sum(n for _m, n, _d1, _d2 in lignes)
        poste.write({
            "date_mesure": fields.Datetime.now(),
            "note": _(
                "30 jours glissants : %(total)s missions des agents ont tourné "
                "sur l'abonnement. %(detail)s. Le montant mensuel reste à "
                "confirmer par Patrick sur sa facture.", total=total,
                detail=detail),
        })
        _logger.info("Coûts : usage de l'abonnement atelier mesuré (%s missions)", total)
        return True

    def action_mesurer(self):
        self._mesurer()
        return True
