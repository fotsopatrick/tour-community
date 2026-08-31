# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
"""Un passage : un visiteur, un jour, un site, une case.

Pourquoi ranger ça dans la base alors que le journal existe déjà ? Parce que
le cahier du portier (Caddy note chaque page demandée) est jeté au bout de
quelques jours : il ne garde que les cinq derniers. Ici, chaque analyse
dépose le résumé dans la base — et l'historique reste, pour toujours, même
quand le cahier d'origine a disparu.

Le vocabulaire est celui de la compétence « intrusions » : mêmes cases,
mêmes noms. Un seul langage pour Patrick, pas deux.

Règle de l'étude 761 : source absente -> on le dit, JAMAIS un chiffre inventé.
"""
import json
import logging
import urllib.request

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Le lecteur de journal tourne sur la machine hôte, pas dans le conteneur
# Odoo : lui seul peut lire les fichiers de Caddy (ils appartiennent à root).
SERVICE_DEFAUT = "http://172.17.0.1:3240"

CASES = [
    ("humain", "Visiteur humain"),
    ("moteur", "Robot moteur de recherche"),
    ("ia", "Robot IA"),
    ("seo", "Robot SEO"),
    ("social", "Robot réseau social"),
    ("veille", "Robot de surveillance"),
    ("maison", "Notre propre robot"),
    ("outil", "Robot outil"),
    ("autre", "Robot autre"),
    ("sans_nom", "Sans nom"),
    ("fouilleur", "Fouilleur"),
    ("scanner", "Scanner d'attaque"),
    ("inconnu", "Inconnu"),
]


class TourRobotPassage(models.Model):
    _name = "tour.robot.passage"
    _description = "Passage d'un visiteur sur un site de la tour"
    _order = "jour desc, requetes desc, robot"

    jour = fields.Date("Jour", required=True, index=True)
    robot = fields.Char("Qui", required=True, index=True)
    categorie = fields.Selection(CASES, string="Case", index=True,
                                 default="inconnu", required=True)
    site = fields.Char("Site visité", required=True, index=True)

    requetes = fields.Integer("Pages demandées", default=0)
    nb_pages = fields.Integer("Adresses différentes", default=0)
    octets = fields.Integer("Octets envoyés", default=0)
    premiere = fields.Datetime("Première demande")
    derniere = fields.Datetime("Dernière demande")
    pointe_minute = fields.Integer("Pointe (demandes en 1 minute)", default=0)

    pages = fields.Text("Adresses demandées (JSON)")
    statuts = fields.Text("Réponses données (JSON)")
    ips = fields.Text("Échantillon d'adresses IP (JSON)")
    nb_ips = fields.Integer("Adresses IP différentes", default=0)
    agent = fields.Text("Carte de visite")
    robots_txt = fields.Boolean("A lu robots.txt", default=False)

    fouille = fields.Integer("Demandes de fouille", default=0)
    fouille_200 = fields.Integer("Fouilles reçues en 200", default=0)
    pages_fouille = fields.Text("Adresses de fouille (JSON)")
    pages_200 = fields.Text("Fouilles répondues en 200 (JSON)")
    techniques = fields.Text("Techniques d'attaque vues (JSON)")

    _sql_constraints = [
        ("passage_unique", "unique(jour, robot, site, categorie)",
         "Un seul passage par visiteur, par jour, par site et par case."),
    ]

    # -- le réglage ---------------------------------------------------------

    @api.model
    def _service(self):
        return self.env["ir.config_parameter"].sudo().get_param(
            "tour_robots.service", SERVICE_DEFAUT).rstrip("/")

    @api.model
    def _attention(self, categorie, fouille=0, fouille_200=0,
                   meme_poids=False, techniques=None):
        """Une ligne du tableau mérite-t-elle qu'on la regarde ?

        Rend '', 'moyenne' ou 'haute' :
        - des techniques d'attaque reconnues      -> haute ;
        - un fouilleur/scanner qui a reçu des réponses « oui » de poids
          différents (une fuite possible)         -> haute ;
        - un fouilleur/scanner, le reste          -> moyenne (surveiller) ;
        - tout le reste                           -> rien.
        """
        if techniques:
            return "haute"
        if categorie in ("fouilleur", "scanner"):
            if fouille_200 and not meme_poids:
                return "haute"
            return "moyenne"
        return ""

    @api.model
    def _a_obtenu(self, categorie, fouille_200=0, meme_poids=False):
        """Le fouilleur a-t-il obtenu quelque chose de sensible ?

        Rend 'oui', 'non' ou '' (pas un fouilleur) :
        - 'oui' : le site a répondu « oui » avec des poids DIFFÉRENTS — une
          vraie page, peut-être un vrai fichier, est sortie. Ce qui ne
          devrait pas.
        - 'non' : refus (404) ou réponse toujours de même poids (la page
          passe-partout renvoyée à chaque fois) — rien de sensible n'est
          sorti.
        """
        if categorie not in ("fouilleur", "scanner"):
            return ""
        if fouille_200 and not meme_poids:
            return "oui"
        return "non"

    # -- l'analyse ----------------------------------------------------------

    @api.model
    def _lire_service(self, jours):
        """Demande le résumé au lecteur de journal. Rend (données, erreur)."""
        url = "%s/json?jours=%d" % (self._service(), int(jours))
        try:
            with urllib.request.urlopen(url, timeout=300) as reponse:
                brut = reponse.read().decode("utf-8")
        except Exception as err:  # noqa: BLE001
            _logger.warning("tour_robots : lecteur injoignable (%s)", err)
            return None, ("Le lecteur de journal ne répond pas (%s). "
                          "Rien n'a été changé dans le tableau."
                          % str(err)[:120])
        try:
            donnees = json.loads(brut)
        except ValueError:
            return None, "Le lecteur de journal a répondu quelque chose d'illisible."
        if donnees.get("erreur"):
            return None, "Le lecteur de journal a signalé : %s" % donnees["erreur"]
        return donnees, None

    @api.model
    def analyser(self, jours=3):
        """Relit le cahier du portier et met la base à jour."""
        donnees, erreur = self._lire_service(jours)
        if erreur:
            return {"ok": False, "message": erreur}

        passages = donnees.get("passages") or []
        anciens = {}
        if passages:
            jours_vus = sorted({p["jour"] for p in passages})
            for rec in self.search([("jour", ">=", jours_vus[0]),
                                    ("jour", "<=", jours_vus[-1])]):
                anciens[(str(rec.jour), rec.robot, rec.site,
                         rec.categorie)] = rec

        def js(valeur):
            return json.dumps(valeur or [], ensure_ascii=False)

        crees = majs = 0
        for p in passages:
            valeurs = {
                "jour": p["jour"],
                "robot": p["robot"],
                "categorie": p.get("case") or "inconnu",
                "site": p["site"],
                "requetes": p.get("requetes") or 0,
                "nb_pages": p.get("nb_pages") or 0,
                "octets": p.get("octets") or 0,
                "premiere": p.get("premiere_utc") or False,
                "derniere": p.get("derniere_utc") or False,
                "pointe_minute": p.get("pointe_minute") or 0,
                "pages": js(p.get("pages")),
                "statuts": js(p.get("statuts")),
                "ips": js(p.get("ips")),
                "nb_ips": p.get("nb_ips") or 0,
                "agent": p.get("agent") or "",
                "robots_txt": bool(p.get("robots_txt")),
                "fouille": p.get("fouille") or 0,
                "fouille_200": p.get("fouille_200") or 0,
                "pages_fouille": js(p.get("pages_fouille")),
                "pages_200": js(p.get("pages_200")),
                "techniques": js(p.get("techniques")),
            }
            cle = (p["jour"], p["robot"], p["site"], valeurs["categorie"])
            ancien = anciens.get(cle)
            if ancien:
                ancien.write(valeurs)
                majs += 1
            else:
                self.create(valeurs)
                crees += 1

        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("tour_robots.derniere_analyse",
                      fields.Datetime.to_string(fields.Datetime.now()))
        icp.set_param("tour_robots.dernier_compte", str(len(passages)))

        return {
            "ok": True,
            "crees": crees,
            "majs": majs,
            "passages": len(passages),
            "message": (
                "Analyse faite sur %d jour(s) : %d nouvelle(s) ligne(s), "
                "%d mise(s) à jour, %d ligne(s) trouvée(s) en tout."
                % (jours, crees, majs, len(passages))),
        }

    @api.model
    def _cron_analyser(self):
        """La tâche automatique : toutes les 4 heures.

        On relit 3 jours et pas seulement 4 heures : si le serveur a été
        éteint, ou si une analyse a échoué, le trou se rebouche tout seul au
        passage suivant.
        """
        resultat = self.analyser(jours=3)
        if not resultat.get("ok"):
            _logger.warning("tour_robots : %s", resultat.get("message"))
        return resultat
