# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
"""La page « Qui vient sur nos sites » du cockpit.

Une question simple, une réponse simple : qui est venu, quel jour, sur quel
site, et qu'est-ce qu'il a demandé.

Les heures sont TOUJOURS rendues à l'heure de Paris — jamais l'heure brute
lue dans la base (règle de Patrick, 20/08).
"""
import json
import math
from datetime import datetime, timedelta

import pytz

from odoo import fields, http
from odoo.http import request

PARIS = pytz.timezone("Europe/Paris")

# (nom montré, marque dans la pastille, couleur, une phrase d'explication)
#
# PAS D'EMOJI (corrigé le 22/08 après contrôle dans un vrai navigateur) :
# le poste de Patrick n'a aucune police d'emoji installée — chaque emoji s'y
# affichait en carré vide. Une pastille de couleur, elle, marche partout.
CASES = {
    "humain": ("Visiteur humain", "", "c2",
               "une vraie personne, avec un vrai navigateur"),
    "moteur": ("Robot moteur de recherche", "", "c1",
               "Google, Bing… ils rangent le site dans les moteurs. Utile."),
    "ia": ("Robot IA", "", "c3",
           "ils aspirent le texte pour entraîner des modèles. Légal, "
           "mais on peut le refuser."),
    "seo": ("Robot SEO", "", "c4",
            "des sociétés de référencement. Légal, mais gourmand."),
    "social": ("Robot réseau social", "", "c1",
               "il vient chercher l'image d'un lien partagé"),
    "veille": ("Robot de surveillance", "", "c2",
               "il vérifie juste que le site répond"),
    "maison": ("Notre propre robot", "", "c2",
               "c'est nous — nos propres programmes"),
    "outil": ("Robot outil", "", "neutre",
              "curl, python, wget… souvent nos propres scripts. À vérifier."),
    "autre": ("Robot autre", "?", "neutre",
              "il se déclare robot, mais on ne le connaît pas"),
    "sans_nom": ("Sans nom", "?", "neutre",
                 "il ne dit pas qui il est. Suspect."),
    "fouilleur": ("Fouilleur", "!", "crit",
                  "il demande des adresses qui n'existent pas chez nous. "
                  "Il essaie les portes une par une. PAS légal."),
    "scanner": ("Scanner d'attaque", "!", "crit",
                "un outil d'attaque connu, qui se présente sous son nom. "
                "PAS légal."),
    "inconnu": ("Inconnu", "?", "neutre",
                "ni robot déclaré, ni navigateur"),
}

# Ce qu'une réponse du site veut dire, en français.
REPONSES = {
    "200": "page donnée", "201": "créé", "204": "rien à renvoyer",
    "301": "renvoyé ailleurs", "302": "renvoyé ailleurs",
    "303": "renvoyé ailleurs", "307": "renvoyé ailleurs",
    "308": "renvoyé ailleurs", "304": "déjà à jour chez lui",
    "400": "demande mal formée", "401": "il faut se connecter",
    "403": "refusé", "404": "ça n'existe pas", "405": "méthode refusée",
    "429": "trop de demandes, freiné",
    "500": "panne chez nous", "502": "panne chez nous",
    "503": "site indisponible", "504": "trop lent chez nous",
}

PAR_PAGE = 25


class TourRobots(http.Controller):

    # -- le droit d'entrer --------------------------------------------------
    # Même verrou que les pages internes du cockpit : ces données disent où
    # sont les trous du site. C'est de l'interne.
    def _pilote(self):
        if request.env.user.has_group("base.group_system"):
            return True
        icp = request.env["ir.config_parameter"].sudo()
        if icp.get_param("tour_cockpit.demo", "0") == "1" and \
                request.env.user._is_admin():
            return True
        return False

    # -- petits outils d'affichage -----------------------------------------
    @staticmethod
    def _a_paris(valeur):
        """Une date-heure de la base (heure de Greenwich) -> heure de Paris."""
        if not valeur:
            return None
        if isinstance(valeur, str):
            valeur = fields.Datetime.from_string(valeur)
        return pytz.utc.localize(valeur).astimezone(PARIS)

    @classmethod
    def _heure(cls, valeur):
        local = cls._a_paris(valeur)
        return local.strftime("%H:%M") if local else "—"

    @staticmethod
    def _jour_fr(valeur):
        if not valeur:
            return "—"
        if isinstance(valeur, str):
            valeur = fields.Date.from_string(valeur)
        return valeur.strftime("%d/%m/%Y")

    @staticmethod
    def _charger(texte):
        try:
            valeur = json.loads(texte or "[]")
            return valeur if isinstance(valeur, list) else []
        except (ValueError, TypeError):
            return []

    @staticmethod
    def _taille(octets):
        o = float(octets or 0)
        if o < 1024:
            return "%d o" % o
        for unite in ("Ko", "Mo", "Go"):
            o /= 1024
            if o < 1024 or unite == "Go":
                return "%.1f %s" % (o, unite)
        return "%d o" % (octets or 0)

    def _pages_200(self, texte):
        """Les fouilles auxquelles le site a répondu « oui », avec le poids.

        Le poids est là pour une raison précise : plusieurs de nos sites sont
        faits d'une seule page et répondent « oui » à n'importe quelle adresse
        inconnue, en renvoyant leur page d'accueil. Si TOUS les poids sont
        identiques, le fouilleur a reçu la page d'accueil — il n'a rien obtenu.
        """
        sortie = []
        poids = set()
        for cle, nb in self._charger(texte):
            adresse, _, taille = str(cle).rpartition("|")
            try:
                taille = int(taille)
            except ValueError:
                taille = 0
            poids.add(taille)
            sortie.append({"adresse": adresse or str(cle), "nb": nb,
                           "poids": self._taille(taille)})
        return sortie, (len(poids) == 1 and len(sortie) > 1)

    # -- la page ------------------------------------------------------------
    @http.route("/tour/cockpit/robots", type="http", auth="user",
                website=False)
    def page(self, page="1", categorie="", site="", robot="", fouille="",
             a_obtenu="", **kw):
        if not self._pilote():
            return request.redirect("/tour/dashboard")

        Passage = request.env["tour.robot.passage"]

        domaine = []
        if categorie and categorie in CASES:
            domaine.append(("categorie", "=", categorie))
        if site:
            domaine.append(("site", "=", site))
        if robot:
            domaine.append(("robot", "=", robot))
        if fouille == "1":
            domaine.append(("fouille", ">", 0))

        records = Passage.search(domaine)
        if a_obtenu in ("oui", "non"):
            records = self._filtrer_a_obtenu(records, a_obtenu)

        total = len(records)
        pages_total = max(1, int(math.ceil(total / float(PAR_PAGE))))
        try:
            numero = max(1, min(int(page), pages_total))
        except (TypeError, ValueError):
            numero = 1

        lignes = []
        debut = (numero - 1) * PAR_PAGE
        for r in records[debut:debut + PAR_PAGE]:
            nom_cas, marque, couleur, phrase = CASES.get(
                r.categorie or "inconnu", CASES["inconnu"])
            pages_200, meme_poids = self._pages_200(r.pages_200)
            techniques = self._charger(r.techniques)
            lignes.append({
                "jour": self._jour_fr(r.jour),
                "robot": r.robot,
                "categorie": r.categorie,
                "case_nom": nom_cas,
                "case_phrase": phrase,
                "marque": marque,
                "couleur": couleur,
                "site": r.site,
                "requetes": r.requetes,
                "nb_pages": r.nb_pages,
                "taille": self._taille(r.octets),
                "de": self._heure(r.premiere),
                "a": self._heure(r.derniere),
                "nb_ips": r.nb_ips,
                "ips": self._charger(r.ips),
                "pages": self._charger(r.pages),
                "pages_fouille": self._charger(r.pages_fouille),
                "pages_200": pages_200,
                "meme_poids": meme_poids,
                "techniques": techniques,
                "attention": Passage._attention(
                    r.categorie, r.fouille, r.fouille_200, meme_poids,
                    techniques),
                "a_obtenu": Passage._a_obtenu(
                    r.categorie, r.fouille_200, meme_poids),
                "statuts": [{"code": str(c), "nb": n,
                             "sens": REPONSES.get(str(c), "")}
                            for c, n in self._charger(r.statuts)],
                "agent": r.agent or "",
                "robots_txt": r.robots_txt,
                "fouille": r.fouille,
                "fouille_200": r.fouille_200,
                "pointe": r.pointe_minute,
            })

        resume = self._resume(Passage)
        cases_vues = []
        for cle, nb in self._compter(Passage, "categorie"):
            nom_cas, marque, coul, _p = CASES.get(cle or "inconnu",
                                               CASES["inconnu"])
            cases_vues.append({"cle": cle or "inconnu", "nom": nom_cas,
                               "marque": marque, "couleur": coul, "nb": nb})
        sites_vus = [{"cle": s, "nb": nb}
                     for s, nb in self._compter(Passage, "site")][:18]

        message = request.session.pop("robots_message", None)
        message_ok = request.session.pop("robots_message_ok", True)

        return request.render("tour_robots.page_robots", {
            "lignes": lignes,
            "resume": resume,
            "cases_vues": cases_vues,
            "sites_vus": sites_vus,
            "filtre_categorie": categorie,
            "filtre_site": site,
            "filtre_robot": robot,
            "filtre_fouille": fouille == "1",
            "filtre_a_obtenu": a_obtenu,
            "lien_a_obtenu": self._lien_tri_a_obtenu(categorie, site, robot,
                                                     fouille, a_obtenu),
            "un_filtre": bool(categorie or site or robot or fouille == "1"
                              or a_obtenu in ("oui", "non")),
            "page": numero,
            "pages_total": pages_total,
            "total": total,
            "message": message,
            "message_ok": message_ok,
            "base_url": self._url_filtres(categorie, site, robot, fouille,
                                          a_obtenu),
        })

    def _filtrer_a_obtenu(self, records, valeur):
        """Ne garde que les passages dont « a obtenu » vaut `valeur`.

        Le champ est calculé (fouille_200 + poids des réponses), pas stocké :
        le filtre se fait en Python, pas en SQL. Une valeur vide (ou autre
        que oui/non) rend tout tel quel.
        """
        if valeur not in ("oui", "non"):
            return records
        gardes = []
        Passage = records.env["tour.robot.passage"]
        for r in records:
            _pages_200, meme_poids = self._pages_200(r.pages_200)
            if Passage._a_obtenu(r.categorie, r.fouille_200,
                                 meme_poids) == valeur:
                gardes.append(r.id)
        return records.browse(gardes)

    def _lien_tri_a_obtenu(self, categorie, site, robot, fouille, a_obtenu):
        """L'URL du prochain état du tri : rien -> oui -> non -> rien."""
        prochain = {"": "oui", "oui": "non", "non": ""}[a_obtenu]
        morceaux = self._url_filtres(categorie, site, robot, fouille)
        if prochain:
            morceaux = (morceaux + "&" if morceaux else "") \
                + "a_obtenu=%s" % prochain
        return "/tour/cockpit/robots?" + morceaux

    def _resume(self, Passage):
        """Les grands chiffres. Aucune source -> None, jamais un chiffre inventé."""
        icp = request.env["ir.config_parameter"].sudo()
        derniere = icp.get_param("tour_robots.derniere_analyse")
        derniere_paris = self._a_paris(derniere) if derniere else None
        quand = (derniere_paris.strftime("%d/%m/%Y à %Hh%M")
                 if derniere_paris else None)

        if not Passage.search_count([]):
            return {"vide": True, "derniere": quand, "prochaine": None}

        aujourdhui = datetime.now(PARIS).date()
        hier = aujourdhui - timedelta(days=1)

        def somme(domaine, champ="requetes"):
            g = Passage._read_group(domaine, [], ["%s:sum" % champ])
            return int((g[0][0] if g and g[0][0] else 0))

        def visiteurs(jour):
            """Les visiteurs humains d'un jour : on additionne les sites."""
            return somme([("jour", "=", jour), ("categorie", "=", "humain")],
                         "nb_ips")

        mauvais = [("categorie", "in", ("fouilleur", "scanner"))]
        premier = Passage.search([], order="jour asc", limit=1)

        return {
            "vide": False,
            "passages": Passage.search_count([]),
            "requetes": somme([]),
            "robots": len(Passage._read_group(
                [("categorie", "!=", "humain")], ["robot"], [])),
            "premier_jour": self._jour_fr(premier.jour) if premier else "—",
            "humains_jour": visiteurs(aujourdhui),
            "humains_hier": visiteurs(hier),
            "pages_jour": somme([("jour", "=", aujourdhui)]),
            "pages_hier": somme([("jour", "=", hier)]),
            "fouille_total": somme([], "fouille"),
            "fouille_jour": somme([("jour", "=", aujourdhui)], "fouille"),
            "mauvais_jour": somme([("jour", "=", aujourdhui)] + mauvais),
            "derniere": quand,
            "prochaine": (derniere_paris + timedelta(hours=4)).strftime(
                "%d/%m à %Hh%M") if derniere_paris else None,
        }

    @staticmethod
    def _compter(Passage, champ):
        """Par valeur du champ : combien de pages demandées, du plus gros au
        plus petit. Sert à proposer des filtres qui existent vraiment."""
        sortie = []
        for valeur, requetes in Passage._read_group([], [champ],
                                                    ["requetes:sum"]):
            if isinstance(valeur, (list, tuple)):
                valeur = valeur[0]
            sortie.append((valeur, int(requetes or 0)))
        sortie.sort(key=lambda kv: -kv[1])
        return sortie

    @staticmethod
    def _url_filtres(categorie, site, robot, fouille, a_obtenu=""):
        from urllib.parse import quote
        morceaux = []
        if categorie:
            morceaux.append("categorie=%s" % quote(categorie))
        if site:
            morceaux.append("site=%s" % quote(site))
        if robot:
            morceaux.append("robot=%s" % quote(robot))
        if fouille == "1":
            morceaux.append("fouille=1")
        if a_obtenu in ("oui", "non"):
            morceaux.append("a_obtenu=%s" % a_obtenu)
        return "&".join(morceaux)

    # -- le bouton ----------------------------------------------------------
    @http.route("/tour/cockpit/robots/analyser", type="http", auth="user",
                methods=["POST"], website=False, csrf=True)
    def analyser(self, jours="3", retour="", **kw):
        if not self._pilote():
            return request.redirect("/tour/dashboard")
        try:
            nb = max(1, min(int(jours), 60))
        except (TypeError, ValueError):
            nb = 3
        resultat = request.env["tour.robot.passage"].analyser(jours=nb)
        request.session["robots_message"] = resultat.get("message")
        request.session["robots_message_ok"] = bool(resultat.get("ok"))
        suite = "?%s" % retour if retour else ""
        return request.redirect("/tour/cockpit/robots%s" % suite)
