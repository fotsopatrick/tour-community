# -*- coding: utf-8 -*-
import json

from odoo import fields, http
from odoo.http import request


class TourCockpit(http.Controller):
    """Le cockpit : une page, un robinet de chiffres. Rien d'autre.

    Regle de l'etude 761 : source absente -> null, case vide,
    JAMAIS un chiffre invente.
    """

    # Le rideau (30/07) : cockpit masque par defaut pour tout le monde.
    # Seul un admin Reglages peut l'afficher ou le masquer.
    PARAM = "tour_cockpit.visible"

    def _visible(self):
        return request.env["ir.config_parameter"].sudo().get_param(self.PARAM, "0") == "1"

    # Le mode démo (01/08) : sur la base tour_test, le compte « demo » est
    # admin (group_erp_manager) mais pas group_system — les pages internes le
    # repoussaient. Le paramètre tour_cockpit.demo, posé UNIQUEMENT sur la
    # démo, ouvre ces pages au pilote de la démo. Jamais sur la prod : là,
    # group_system reste le seul passe.
    PARAM_DEMO = "tour_cockpit.demo"

    def _pilote(self):
        """Le droit de voir les pages internes du cockpit.

        group_system toujours ; sinon, mode démo + admin (le compte de la
        démo). Un invité (portal) ne passe jamais.
        """
        if request.env.user.has_group("base.group_system"):
            return True
        icp = request.env["ir.config_parameter"].sudo()
        if icp.get_param(self.PARAM_DEMO, "0") == "1" and request.env.user._is_admin():
            return True
        return False

    @http.route("/tour/cockpit", type="http", auth="user", website=False)
    def page(self, **kw):
        # Verrou de Patrick (30/07) : le cockpit est ferme a tout le monde
        # sauf les admins Reglages. Les autres retournent a l'accueil.
        if not request.env.user._is_admin():
            return request.redirect("/tour/dashboard")
        if not self._visible():
            return request.render("tour_cockpit.masque", {})
        return request.render("tour_cockpit.page", {"visites": self._visites()})

    def _visites(self):
        """Les visites de la vitrine publique, relues du service hôte (3214)."""
        import urllib.request
        try:
            with urllib.request.urlopen(
                    "http://172.17.0.1:3214/json", timeout=4) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return False

    @http.route("/tour/cockpit/agents", type="http", auth="user", website=False)
    def agents(self, **kw):
        """Le cockpit AGENTS — « Qui travaille, là, maintenant ? ».

        Patrick, 31/07 : « je préfère un dashboard conçu comme cockpit, là
        c'est pas joli mais les données sont super ». La première version de
        « Qui travaille ? » était une page brute ; ici les mêmes données sont
        rendues dans le langage du cockpit (radar, bandeaux, panneaux).

        SÉCURITÉ (payé le 31/07 au retest) : la page montre les consignes des
        missions en cours, c'est de l'interne. On verrouille sur
        base.group_system — le vrai « admin de la tour » — et PAS sur
        `_is_admin()` qui ouvre à group_erp_manager (le compte démo le
        possède, et il est public). Un invité ne peut pas voir ces données :
        elles ne sont PAS les siennes (règle de Patrick, 01/08 : un invité ne
        voit que ses propres données).
        """
        if not self._pilote():
            return request.redirect("/tour/dashboard")
        return request.render("tour_cockpit.page_agents", {})

    @http.route("/tour/cockpit/data-agents", type="http", auth="user",
                website=False)
    def data_agents(self, **kw):
        """Le robinet du cockpit agents : relaie le service hôte.

        Le service `etat-agents` (systemd, port 3211) lit des choses que le
        conteneur Odoo ne voit pas (processus, git, santé) et sert un JSON.
        La tour ne fait que RELAYER : source absente -> message d'erreur,
        jamais de chiffre inventé (règle de l'étude 761).

        Même verrou que la page : base.group_system, pas _is_admin() (voir
        plus haut — le compte démo a group_erp_manager).
        """
        if not self._pilote():
            return self._json({"error": "reserve au pilote"}, status=403)
        import urllib.request
        try:
            with urllib.request.urlopen(
                    "http://172.17.0.1:3211/json", timeout=6) as reponse:
                corps = reponse.read().decode("utf-8")
        except Exception:
            return self._json(
                {"error": "service etat-agents indisponible"}, status=503)
        return request.make_response(
            corps, headers=[("Content-Type", "application/json; charset=utf-8")])

    # -- Défense réseau -----------------------------------------------------
    # Le service hôte (systemd defense-service, port 3230) rend la CLI
    # defense-reseau.sh accessible au conteneur : état, scan, connexions,
    # verrouillage d'urgence, isolation du Raspberry Pi. La tour ne fait QUE
    # RELAYER : source absente -> message, jamais un chiffre inventé (règle 761).
    DEFENSE_SERVICE = "http://172.17.0.1:3230"

    def _defense_appeler(self, chemin, corps=None, timeout=40):
        """Appelle le service hôte de défense. Renvoie (données, erreur)."""
        import urllib.request
        try:
            if corps is None:
                requete = urllib.request.Request(self.DEFENSE_SERVICE + chemin)
            else:
                requete = urllib.request.Request(
                    self.DEFENSE_SERVICE + chemin,
                    data=json.dumps(corps).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST")
            with urllib.request.urlopen(requete, timeout=timeout) as reponse:
                return json.loads(reponse.read().decode("utf-8")), None
        except Exception as exc:  # noqa: BLE001
            return None, "service de défense indisponible (%s)" % exc

    def _defense_jeton(self):
        """Le jeton des actions sensibles, relu du service hôte (jamais vers
        le navigateur : le service n'écoute que sur le bridge docker)."""
        donnees, erreur = self._defense_appeler("/jeton", timeout=5)
        if erreur or not donnees:
            return ""
        return donnees.get("jeton", "")

    def _defense_lire_etat(self, sortie):
        """Transforme la sortie de `defense-reseau.sh etat` en l'objet que la
        page attend : verrou, pi, connexions (paires), texte brut."""
        # Parsing simple par sections (la sortie est du texte, on lit les
        # lignes qui suivent chaque en-tête).
        sections = {}
        cle = None
        for ligne in (sortie or "").splitlines():
            ligne = ligne.strip()
            if ligne.startswith("=== "):
                cle = ligne.strip("= ").strip()
                sections[cle] = []
            elif cle and ligne:
                sections[cle].append(ligne)
        verrou = " ".join(sections.get("VERROU DÉFENSE RÉSEAU", []) or ["?"])
        urgence = " ".join(sections.get("VERROU D'URGENCE", []) or ["?"])
        pi_texte = " ".join(sections.get("PI", []) or ["?"])
        if "ISOLÉ" in pi_texte:
            pi = "ISOLÉ"
        elif "relié" in pi_texte:
            pi = "RELIÉ"
        elif "non joignable" in pi_texte:
            pi = "hors ligne"
        else:
            pi = pi_texte
        connexions = [
            ["Verrou", verrou],
            ["Urgence", urgence],
            ["Pi", pi],
        ]
        return {"verrou": verrou, "pi": pi, "connexions": connexions,
                "texte": sortie or ""}

    @http.route("/tour/cockpit/defense", type="http", auth="user",
                website=False)
    def defense(self, **kw):
        """Le cockpit DÉFENSE réseau — « qui frappe, et que fait-on ? ».

        Le verrou d'urgence (couper 80/443, garder le SSH de Patrick, isoler
        le Raspberry Pi), la simulation qui prouve que la session survivrait,
        et la carte du réseau. Réservé au pilote comme les autres pages
        internes (jamais un invité).
        """
        if not self._pilote():
            return request.redirect("/tour/dashboard")
        return request.render("tour_cockpit.page_defense", {})

    @http.route("/tour/cockpit/data-defense", type="http", auth="user",
                website=False)
    def data_defense(self, **kw):
        """Le robinet de la défense : relaie le service hôte (3230).

        Actions : etat (défaut), simuler, scan, connexions.
        Source absente -> message d'erreur, jamais un chiffre inventé.
        """
        if not self._pilote():
            return self._json({"error": "reserve au pilote"}, status=403)
        action = kw.get("action", "etat")
        routes = {
            "etat": "/",
            "simuler": "/simuler",
            "scan": "/scan",
            "connexions": "/connexions",
        }
        if action not in routes:
            return self._json({"error": "action inconnue"}, status=404)
        donnees, erreur = self._defense_appeler(routes[action])
        if erreur:
            return self._json({"error": erreur}, status=503)
        if action == "etat":
            donnees_etat = self._defense_lire_etat(donnees.get("sortie"))
            # La même route sert deux consommateurs : renderEtat lit
            # verrou/pi/connexions/texte, get() après une action lit sortie.
            donnees_etat["sortie"] = donnees.get("sortie", "")
            return self._json(donnees_etat)
        return self._json({"sortie": donnees.get("sortie", "")})

    @http.route("/tour/cockpit/defense-action", type="http", auth="user",
                website=False)
    def defense_action(self, **kw):
        """Les actions sensibles : verrouiller, déverrouiller, isoler/relier
        le Raspberry Pi. Le jeton est relu du service hôte ici — jamais envoyé
        au navigateur."""
        if not self._pilote():
            return self._json({"error": "reserve au pilote"}, status=403)
        action = kw.get("action", "verrouiller")
        routes = {
            "verrouiller": "/verrouiller",
            "deverrouiller": "/deverrouiller",
            "isoler-pi": "/isoler-pi",
            "relier-pi": "/relier-pi",
        }
        if action not in routes:
            return self._json({"error": "action inconnue"}, status=404)
        jeton = self._defense_jeton()
        if not jeton:
            return self._json({"error": "jeton de défense introuvable"},
                              status=503)
        donnees, erreur = self._defense_appeler(
            routes[action], corps={"jeton": jeton}, timeout=60)
        if erreur:
            return self._json({"error": erreur}, status=503)
        return self._json({
            "ok": bool(donnees.get("ok")),
            "sortie": donnees.get("sortie", ""),
            "error": donnees.get("error"),
        })

    @http.route("/tour/cockpit/vps", type="http", auth="user", website=False)
    def vps(self, **kw):
        """Le cockpit VPS — « le serveur respire encore ? ».

        RAM, charge, disque et conteneurs, lus du service hôte et rendus dans
        le langage du cockpit. Réservé au pilote (group_system, ou le mode
        démo sur tour_test).
        """
        if not self._pilote():
            return request.redirect("/tour/dashboard")
        return request.render("tour_cockpit.page_vps", {})

    @http.route("/tour/cockpit/securite", type="http", auth="user",
                website=False)
    def securite(self, **kw):
        """Le cockpit SÉCURITÉ — nos circuits de sécurité et la porte.

        Les garde-fous (garde_fou.garde_fou), le tunnel de test (la porte :
        chaque test est une porte du circuit), et les circuits internes de
        sécurité. Même verrou que les autres pages internes : pilote
        (group_system), jamais un invité.
        """
        if not self._pilote():
            return request.redirect("/tour/dashboard")
        return request.render("tour_cockpit.page_securite", {})

    @http.route("/tour/cockpit/data-securite", type="http", auth="user",
                website=False)
    def data_securite(self, **kw):
        """Le robinet du cockpit sécurité : garde-fous + circuits de sécurité.
        Source absente -> champ absent, jamais un chiffre inventé."""
        if not self._pilote():
            return self._json({"error": "reserve au pilote"}, status=403)
        env = request.env
        garde_fous = []
        if "garde_fou.garde_fou" in env:
            for g in env["garde_fou.garde_fou"].sudo().search(
                    [], order="code"):
                garde_fous.append({
                    "code": g.code, "name": g.name, "zone": g.zone,
                    "etat": g.etat, "actif": g.actif,
                    "crainte": g.crainte or "",
                    "fonctionnement": g.fonctionnement or "",
                    "verification": g.verification or "",
                })
        gabarits = []
        if "circuit.modele" in env:
            for m in env["circuit.modele"].sudo().search(
                    [("active", "=", True)], order="name"):
                gabarits.append({
                    "name": m.name,
                    "type": m.type_operation,
                    "portes": [{
                        "nom": e.name,
                        "agent": (e.membre_id.name
                                  if e.role == "agent" and e.membre_id
                                  else ("Patrick" if e.role == "patron"
                                        else e.role)),
                    } for e in m.etape_ids.sorted("sequence")],
                })
        nb_actifs = len([g for g in garde_fous if g["actif"]])
        return self._json({
            "garde_fous": garde_fous,
            "gabarits": gabarits,
            "nb_garde_fous": len(garde_fous),
            "nb_actifs": nb_actifs,
            "nb_gabarits": len(gabarits),
        })

    @http.route("/tour/cockpit/traces", type="http", auth="user",
                website=False)
    def traces(self, **kw):
        """Le cockpit TRACES — « qu'est-ce qui s'est passé, dans quel ordre ? ».

        L'observabilité des livres (freeCodeCamp/LangGraph, ch.6) : un système
        multi-agents qui sort un mauvais résultat SANS erreur est plus dur à
        déboguer qu'un système qui plante. Ici on relit ce que les agents ont
        réellement fait : les missions (leur vie dans le temps, leurs étapes)
        et les passages de circuits (qui a franchi quelle porte, avec quel
        verdict). Rien n'est inventé : chaque ligne se lit dans la base.
        """
        if not self._pilote():
            return request.redirect("/tour/dashboard")
        return request.render("tour_cockpit.page_traces", {})

    @http.route("/tour/cockpit/data-traces", type="http", auth="user",
                website=False)
    def data_traces(self, **kw):
        """Le robinet du cockpit traces : les dernières missions et les
        derniers passages de circuits, lus de la base. Source absente ->
        champ absent, jamais un chiffre inventé."""
        if not self._pilote():
            return self._json({"error": "reserve au pilote"}, status=403)
        env = request.env

        missions = []
        if "atelier.mission" in env:
            for m in env["atelier.mission"].sudo().search(
                    [], order="id desc", limit=40):
                missions.append({
                    "id": m.id,
                    "name": m.name or "",
                    "moteur": m.moteur_utilise or m.moteur or "",
                    "etat": m.etat,
                    "duree": m.duree,
                    "deposee": m.create_date.isoformat() if m.create_date else "",
                    "envoyee_le": m.envoyee_le.isoformat() if m.envoyee_le else "",
                    "livree_le": m.livree_le.isoformat() if m.livree_le else "",
                    "avancement": m.avancement or "",
                    "retest": m.retest_declare,
                    "nb_etapes": len(m.etape_ids),
                    "suites": len(m.suite_ids),
                    "precedente": m.precedente_id.id or False,
                    "repropositions": m.repropositions,
                    "etapes": [{"nom": e.nom or "", "etat": e.etat}
                               for e in m.etape_ids.sorted("sequence")],
                    "qualite": self._qualite_reponse(
                        m.reponse, m.avancement, m.retest_declare),
                })

        passages = []
        if "circuit.passage" in env:
            for p in env["circuit.passage"].sudo().search(
                    [], order="id desc", limit=30):
                passages.append({
                    "instance": p.instance_id.name or "",
                    "modele": p.instance_id.modele_id.name or "",
                    "porte": p.etape_id.name or "",
                    "role": p.etape_id.role or "",
                    "etat": p.etat,
                    "avis": (p.avis or "")[:140],
                    "mission": p.mission_id.name or "",
                    "date": p.create_date.isoformat() if p.create_date else "",
                })

        en_attente = terminees = echecs = circuits_en_cours = 0
        if "atelier.mission" in env:
            Mission = env["atelier.mission"].sudo()
            en_attente = Mission.search_count([("etat", "=", "envoyee")])
            depuis = fields.Datetime.subtract(
                fields.Datetime.now(), days=7)
            terminees = Mission.search_count(
                [("etat", "=", "terminee"), ("create_date", ">=", depuis)])
            echecs = Mission.search_count(
                [("etat", "=", "echec"), ("create_date", ">=", depuis)])
        if "circuit.instance" in env:
            circuits_en_cours = env["circuit.instance"].sudo().search_count(
                [("etat", "=", "en_cours")])

        return self._json({
            "missions": missions,
            "passages": passages,
            "en_attente": en_attente,
            "terminees_7j": terminees,
            "echecs_7j": echecs,
            "circuits_en_cours": circuits_en_cours,
        })

    @http.route("/tour/cockpit/personnages", type="http", auth="user",
                website=False)
    def personnages(self, **kw):
        """Le selecteur de personnages (façon King of Fighters) : chaque agent
        de l'equipage avec ses competences en jauges. Patrick, 06/08 : voir les
        agents comme des personnages de jeu, et la spec de chacun."""
        if not self._pilote():
            return request.redirect("/tour/dashboard")
        return request.render("tour_cockpit.page_personnages", {})

    @http.route("/tour/cockpit/data-personnages", type="http", auth="user",
                website=False)
    def data_personnages(self, **kw):
        """Le robinet des personnages : les agents et leurs competences.
        Source absente -> champ absent, jamais invente."""
        if not self._pilote():
            return self._json({"error": "reserve au pilote"}, status=403)
        env = request.env
        agents = []
        if "equipe.membre" in env:
            for m in env["equipe.membre"].sudo().search([], order="id"):
                competences = []
                for c in m.competence_ids.sorted("sequence"):
                    competences.append({
                        "nom": c.name or "",
                        "valeur": c.valeur,
                        "etoiles": c.etoiles,
                        "confidentiel": c.confidentiel,
                    })
                fiche, nom_fiche = self._fiche_membre(m.name)
                agents.append({
                    "id": m.id,
                    "nom": m.name or "",
                    "poste": m.poste or "",
                    "moteur": m.moteur or "",
                    "niveau": m.niveau,
                    "xp": m.xp,
                    "nb_competences": len(competences),
                    "competences": competences,
                    "nom_fiche": nom_fiche,
                    "fiche": fiche,
                })
        return self._json({"agents": agents})

    _FICHES = None

    def _fiche_membre(self, nom):
        """La fiche de poste agents/<nom>.md (celle injectee dans les missions),
        lue depuis /mnt/atelier/agents-fiches.json (rassemble par l hote)."""
        import json as _json
        import unicodedata as _u
        import re as _re
        if self._FICHES is None:
            donnees = {}
            try:
                with open("/mnt/atelier/agents-fiches.json",
                          encoding="utf-8") as fh:
                    donnees = _json.load(fh)
            except Exception:  # noqa: BLE001 — fichier absent = pas de fiche
                donnees = {}

            def norme(s):
                s = _u.normalize("NFD", s).encode("ascii", "ignore").decode()
                return _re.sub(r"[^a-z0-9]", "", s.lower())

            fiches = donnees.get("fiches", {})
            candidats = {}
            for cle in fiches:
                candidats.setdefault(norme(cle), cle)
            for cle, f in fiches.items():
                premiere = (f.get("contenu") or "").splitlines()
                if not premiere:
                    continue
                for mot in premiere[0].replace("#", "").replace("—", " ").split():
                    if len(mot) >= 3:
                        candidats.setdefault(norme(mot), cle)
            explicite = {"Raph": "raphael", "Jor-El": "jorel",
                         "Mirline": "raphael"}
            self._FICHES = (explicite, candidats, fiches, norme)
        explicite, candidats, fiches, norme = self._FICHES
        nom_fiche = explicite.get(nom) or candidats.get(norme(nom))
        if not nom_fiche or nom_fiche not in fiches:
            return "", nom_fiche or ""
        return fiches[nom_fiche].get("contenu", ""), nom_fiche

    @http.route("/tour/cockpit/fiche-sauver", type="http", auth="user",
                website=False, methods=["POST"], csrf=False)
    def fiche_sauver(self, **kw):
        """Enregistre la fiche de poste d'un agent (reserve au pilote).
        Ecrit un ordre que le script hote applique (ecriture + commit)."""
        if not self._pilote():
            return self._json({"error": "reserve au pilote"}, status=403)
        try:
            membre_id = int(kw.get("agent_id", "") or 0)
        except Exception:
            membre_id = 0
        env = request.env
        m = env["equipe.membre"].sudo().browse(membre_id) if membre_id else None
        if not m or not m.exists():
            return self._json({"ok": False, "erreur": "agent inconnu"}, 404)
        _, nom_fiche = self._fiche_membre(m.name)
        if not nom_fiche:
            return self._json({"ok": False,
                               "erreur": "pas de fiche pour cet agent"}, 404)
        import os
        ordres = "/mnt/atelier/ordres-fiches"
        try:
            os.makedirs(ordres, exist_ok=True)
            with open(os.path.join(ordres, nom_fiche + ".txt"),
                      "w", encoding="utf-8") as fh:
                fh.write(kw.get("contenu", "") or "")
        except Exception as e:  # noqa: BLE001
            return self._json({"ok": False, "erreur": str(e)}, 500)
        return self._json({"ok": True, "nom_fiche": nom_fiche,
                           "message": "modification envoyee"})

    @http.route("/tour/cockpit/data-vps", type="http", auth="user",
                website=False)
    def data_vps(self, **kw):
        """Le robinet du cockpit VPS : relaie la section « vps » du service
        hôte (3211). Source absente -> erreur, jamais de chiffre inventé."""
        if not self._pilote():
            return self._json({"error": "reserve au pilote"}, status=403)
        import urllib.request
        try:
            with urllib.request.urlopen(
                    "http://172.17.0.1:3211/json", timeout=6) as reponse:
                corps = json.loads(reponse.read().decode("utf-8"))
        except Exception:
            return self._json(
                {"error": "service etat-agents indisponible"}, status=503)
        return self._json(corps.get("vps") or {}, 200)

    @http.route("/tour/cockpit/activer", type="http", auth="user",
                website=False, methods=["POST"])
    def activer(self, **kw):
        if not request.env.user._is_admin():
            return request.redirect("/tour/dashboard")
        request.env["ir.config_parameter"].sudo().set_param(self.PARAM, "1")
        return request.redirect("/tour/cockpit")

    @http.route("/tour/cockpit/masquer", type="http", auth="user",
                website=False, methods=["POST"])
    def masquer(self, **kw):
        if not request.env.user._is_admin():
            return request.redirect("/tour/dashboard")
        request.env["ir.config_parameter"].sudo().set_param(self.PARAM, "0")
        return request.redirect("/tour/dashboard")

    @http.route("/tour/cockpit/niveaux", type="http", auth="user",
                website=False)
    def niveaux(self, **kw):
        """Les niveaux détectés — le jeu de la tour ET l'équipe. Rien n'est
        inventé : chaque niveau se lit dans le travail réel déjà en base."""
        if not self._pilote():
            return request.redirect("/tour/dashboard")
        tours = []
        if "jeu.tour" in request.env:
            tours = request.env["jeu.tour"].sudo()._toutes_tours()
        membres = []
        if "equipe.membre" in request.env:
            for m in request.env["equipe.membre"].sudo().search(
                    [], order="xp desc"):
                membres.append({
                    "nom": m.name,
                    "niveau": m.niveau,
                    "titre": m.titre or "",
                    "xp": m.xp,
                    "avancement": m.avancement,
                })
        return request.render("tour_cockpit.page_niveaux", {
            "tours": tours,
            "membres": membres,
            "rejoue": kw.get("rejoue"),
        })

    @http.route("/tour/cockpit/rejouer-niveau", type="http", auth="user",
                website=False, methods=["POST"])
    def rejouer_niveau(self, **kw):
        """Rejouer la détection de niveau : on relit la base et on recalcule
        les niveaux (jeu de la tour + équipe). Le résultat se lit à l'écran."""
        if not self._pilote():
            return request.redirect("/tour/dashboard")
        if "jeu.tour" in request.env:
            request.env["jeu.tour"].sudo()._toutes_tours()
        if "equipe.membre" in request.env:
            membres = request.env["equipe.membre"].sudo().search([])
            try:
                membres.mapped("competence_ids")._mesurer()
            except Exception:  # noqa: BLE001 — la source peut manquer
                pass
            membres.invalidate_recordset(["xp", "niveau", "avancement"])
            _ = membres.mapped("niveau")  # force le recalcul
        return request.redirect("/tour/cockpit/niveaux?rejoue=1")

    @http.route("/tour/cockpit/data", type="http", auth="user", website=False)
    def data(self, **kw):
        if not request.env.user._is_admin() or not self._visible():
            return self._json({"error": "reserve au pilote"}, status=403)

        Task = request.env["project.task"]
        Project = request.env["project.project"]

        # --- etats : taches groupees par etape, rangees en 5 seaux fixes ---
        etats = {"a_faire": 0, "fait": 0, "en_cours": 0, "bloque": 0, "sans_etat": 0}
        try:
            for stage, count in Task._read_group([], ["stage_id"], ["__count"]):
                etats[self._seau(stage.name if stage else None)] += count
        except Exception:
            etats = None  # source cassee -> null, pas un chiffre invente

        # --- charge par projet ---
        par_projet = None
        try:
            rows = Task._read_group(
                [("project_id", "!=", False)], ["project_id"], ["__count"]
            )
            par_projet = sorted(
                [{"nom": p.display_name, "n": c} for p, c in rows],
                key=lambda r: -r["n"],
            )
        except Exception:
            pass

        # --- projets ---
        projets = None
        try:
            total = Project.search_count([])
            actifs = len(par_projet) if par_projet is not None else None
            projets = {"total": total, "actifs": actifs}
        except Exception:
            pass

        total_taches = sum(etats.values()) if etats else None

        # --- PREUVE SOCIALE (09/08, H3, Braignak/Merline) ---
        # Swamp affiche 194 millions d'evenements en vitrine ; nous, qui notons
        # tout, ne montrions presque rien. Ici les chiffres REELS, comptes en
        # base a chaque lecture. Source cassee -> null, jamais un chiffre
        # invente (regle de l'etude 761).
        preuve_sociale = {}
        comptages = [
            ("missions_terminees", "atelier.mission", [("etat", "=", "terminee")]),
            ("missions_echouees", "atelier.mission", [("etat", "=", "echec")]),
            ("fiches_reponses", "reponse.fiche", []),
            ("decisions_prises", "decision.fiche", []),
            ("etudes_braignak", "braignak.etude", []),
            ("gabarits_circuits", "circuit.modele", []),
            ("garde_fous", "garde_fou.garde_fou", []),
            ("membres_equipe", "equipe.membre", []),
        ]
        for cle, modele, domaine in comptages:
            try:
                preuve_sociale[cle] = request.env[modele].search_count(domaine)
            except Exception:
                preuve_sociale[cle] = None  # source cassee -> null

        return self._json(
            {
                "projets": projets,
                "etats": etats,
                "par_projet": par_projet,
                "total_taches": total_taches,
                "preuve_sociale": preuve_sociale,
            }
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _prose_utile(html):
        """Le texte de prose d'un compte rendu, sans balises ni decor."""
        import re
        from html import unescape
        if not html:
            return ""
        texte = unescape(re.sub(r"<[^>]+>", " ", html))
        lignes = []
        for ligne in texte.splitlines():
            l = ligne.strip().lstrip("-*#>• ").strip()
            if not l or re.fullmatch(r"[=\-_*·•\s]+", l):
                continue
            low = l.lower()
            if low.startswith(("=== ", "--- ", "***", "tours ", "jetons ",
                               "fichiers ", "appels d")):
                continue
            if len(l) < 12:
                continue
            lignes.append(l)
        return " ".join(lignes)

    @staticmethod
    def _qualite_reponse(reponse, avancement, retest_declare):
        """La jauge de qualité d'un compte rendu (l'évaluation des livres :
        freeCodeCamp ch.7, AI Agents in Action ch.10). Déterministe : chaque
        point se lit dans la réponse ou les champs, rien n'est inventé."""
        import re
        prose = TourCockpit._prose_utile(reponse).lower()
        points = [
            len(prose) >= 80,                       # 1. prose fournie
            bool(avancement and avancement != "non_consigne"),  # 2. avancement
            bool(retest_declare or re.search(
                r"\b(retest|régression|rejoué|rejoue|vérifié|prouvé|mesuré)\b",
                prose)),                            # 3. preuve
            bool(avancement == "pas_fait" or re.search(
                r"\b(pas fait|pas pu|impossible|blocage|volontairement|"
                r"n'a pas|échec|refusé)\b", prose))  # 4. honnêteté
        ]
        score = sum(points)
        if score == 4:
            classe = "complete"
        elif score == 3:
            classe = "solide"
        elif score == 2:
            classe = "partielle"
        else:
            classe = "pauvre"
        return {"score": score, "classe": classe,
                "criteres": ["prose", "avancement", "preuve", "honnetete"]}

    @staticmethod
    def _seau(nom):
        """Range un nom d'etape dans un des 5 seaux du cockpit."""
        if not nom:
            return "sans_etat"
        n = nom.lower()
        if "fait" in n or "done" in n or "termin" in n:
            return "fait"
        if "cours" in n or "progress" in n or "doing" in n:
            return "en_cours"
        if "bloqu" in n or "blocked" in n or "attente" in n:
            return "bloque"
        return "a_faire"

    @staticmethod
    def _json(payload, status=200):
        return request.make_response(
            json.dumps(payload, ensure_ascii=False),
            status=status,
            headers=[("Content-Type", "application/json; charset=utf-8")],
        )

    # ------------------------------------------------------------------ #
    # CE QUI SORT DE LA MACHINE (21/08/2026, demande de Patrick)
    #
    # « J'ai des doutes sur l'API DeepSeek et la confidentialité des données. »
    # Un doute ne se répond pas par une opinion : il se répond par la liste de
    # ce qui part, mesurée. Cette page lit deux sources, et rien d'autre :
    #   - les moteurs eux-mêmes (les adresses qu'ils appellent sont dans leur
    #     code, on ne les devine pas) ;
    #   - le journal des appels, qui compte ce qui est réellement parti.
    # Aucun texte de consigne n'est affiché ici : le journal n'en garde pas,
    # et cette page n'en fabriquera pas.
    # ------------------------------------------------------------------ #
    ATELIER = "/mnt/atelier"

    def _sorties_moteurs(self):
        """Qui appelle quoi. Lu dans le code des moteurs, jamais devine."""
        import os
        import re
        dossier = os.path.join(self.ATELIER, "moteurs")
        moteurs = []
        try:
            fichiers = sorted(os.listdir(dossier))
        except OSError:
            return moteurs
        for nom in fichiers:
            if not nom.endswith((".sh", ".py")) or ".avant" in nom or ".bak" in nom:
                continue
            chemin = os.path.join(dossier, nom)
            try:
                with open(chemin, "r", encoding="utf-8", errors="ignore") as f:
                    code = f.read()
            except OSError:
                continue
            hotes = set()
            for h in re.findall(r"https?://([A-Za-z0-9.-]+)", code):
                # Une vraie adresse a un nom ET une terminaison : « ... » ou
                # « . » sont des morceaux de commentaire, pas des serveurs.
                if not re.match(r"^[a-z0-9][a-z0-9-]*(\.[a-z0-9-]+)*\.[a-z]{2,}$", h, re.I):
                    continue
                if h.startswith("127.") or h in ("localhost", "0.0.0.0"):
                    continue
                hotes.add(h)
            interne = bool(re.search(r"127\.0\.0\.1|localhost|ollama", code))
            if not hotes and not interne:
                continue
            moteurs.append({
                "nom": nom.rsplit(".", 1)[0],
                "fichier": nom,
                "dehors": sorted(hotes),
                "chez_nous": interne,
            })
        return moteurs

    def _sorties_volumes(self):
        """Ce qui est REELLEMENT parti : compte par destination et par periode."""
        import json as _json
        import os
        import time
        chemin = os.path.join(self.ATELIER, "appels-api.jsonl")
        maintenant = int(time.time())
        bornes = {"jour": 86400, "semaine": 7 * 86400, "mois": 30 * 86400}
        par_moteur = {}
        # « Parti » et « refuse » ne se melangent pas : un envoi refuse a
        # quand meme quitte la machine, mais il n a rien ramene. Les compter
        # ensemble ferait croire a un travail qui n a pas eu lieu.
        total = {k: {"appels": 0, "entree": 0, "sortie": 0, "refuses": 0}
                 for k in bornes}
        dernier = 0
        try:
            with open(chemin, "r", encoding="utf-8", errors="ignore") as f:
                lignes = f.readlines()[-40000:]
        except OSError:
            lignes = []
        for ligne in lignes:
            try:
                ev = _json.loads(ligne)
            except Exception:  # noqa: BLE001
                continue
            quand = int(ev.get("horodatage") or 0)
            if not quand:
                continue
            dernier = max(dernier, quand)
            moteur = ev.get("moteur") or "?"
            modele = ev.get("modele") or ""
            cle = (moteur, modele)
            fiche = par_moteur.setdefault(cle, {
                "moteur": moteur, "modele": modele, "dernier": 0,
                "jour": 0, "semaine": 0, "mois": 0,
                "mots_mois": 0, "appels_mois": 0,
            })
            fiche["dernier"] = max(fiche["dernier"], quand)
            for periode, duree in bornes.items():
                if maintenant - quand <= duree:
                    fiche[periode] += 1
                    total[periode]["appels"] += 1
                    total[periode]["entree"] += int(ev.get("tokens_entree") or 0)
                    total[periode]["sortie"] += int(ev.get("tokens_sortie") or 0)
                    if ev.get("refuse"):
                        total[periode]["refuses"] += 1
                    if periode == "mois":
                        fiche["mots_mois"] += int(ev.get("tokens_entree") or 0)
                        fiche["appels_mois"] += 1
        lignes_v = sorted(par_moteur.values(), key=lambda x: -x["mots_mois"])
        return {"par_moteur": lignes_v, "total": total, "dernier": dernier}

    @http.route("/tour/cockpit/sorties", type="http", auth="user", website=False)
    def sorties(self, **kw):
        """Le cockpit SORTIES — « qu'est-ce qui quitte la machine, et pour aller ou ? »."""
        if not self._pilote():
            return request.redirect("/tour/dashboard")
        volumes = self._sorties_volumes()
        return request.render("tour_cockpit.page_sorties", {
            "moteurs": self._sorties_moteurs(),
            "volumes": volumes,
            "maintenant": fields.Datetime.now(),
        })
