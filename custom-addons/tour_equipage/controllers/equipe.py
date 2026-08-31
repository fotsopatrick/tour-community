# -*- coding: utf-8 -*-
import json
import os
import re

from odoo import http
from odoo.http import request

_I18N_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "i18n")


def _charger_trad(lang):
    """Charge le cache de traduction (equipe-<lang>.json) indexé par la chaîne
    FR. Le fichier est généré hors-ligne (gen-equipe-i18n.py) — pas d'appel
    API au rendu. Retourne un dict, vide si absent."""
    if lang not in ("en", "ja"):
        return {}
    chemin = os.path.join(_I18N_DIR, "equipe-%s.json" % lang)
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return {}


# Les NOMS DE FAMILLE des membres sont des marques (séries Smallville/DC).
# Le garde-fou les retire des fiches : on garde les prénoms, jamais les noms.
# (09/08, Patrick — « passe tous les noms complets au garde-fou ».)
MARQUES = ["Sullivan", "Kent", "Stone", "Olsen", "Hamilton", "Ross",
           "Queen", "Lane", "White", "Mercer"]


def _sans_marques(texte):
    if not texte:
        return texte
    for marque in MARQUES:
        texte = re.sub(r"\b%s\b" % marque, "", texte)
    texte = re.sub(r"\s{2,}", " ", texte).strip()
    return texte


class PageEquipage(http.Controller):

    def _trad_ctx(self, lang):
        """Le contexte de langue : dictionnaire des textes d'interface (L) et
        la fonction trad() qui traduit une chaîne FR (elle rend l'original si
        la traduction manque)."""
        cache = _charger_trad(lang)
        L = {
            "fr": {
                "titre": "L'équipe", "intro": "L'équipe de la tour. Chacun "
                        "a un poste, et personne n'est interchangeable.",
                "note_titre": "L'expérience ci-dessous ne se saisit pas, elle "
                              "se gagne.",
                "note_corps": "Chaque point vient d'un enregistrement réel de "
                              "la tour : une mission rendue, un constat de "
                              "sécurité retenu, une régression attrapée, un "
                              "guide écrit. Aucun de ces chiffres n'est "
                              "modifiable.",
                "points": "points", "palier": "palier suivant à",
                "dernier": "dernier palier atteint", "eteint": "éteint",
                "total": "Total de l'équipe :", "compteurs": "Les compteurs "
                            "sont relus à chaque ouverture de cette page.",
                "accueil": "Accueil", "vitrine": "la vitrine", "niv": "Niv.",
                "confidentiel": "confidentiel",
            },
            "en": {
                "titre": "The team", "intro": "The team of the tower. Each "
                         "person has a role, and no one is interchangeable.",
                "note_titre": "The experience below is not entered by hand — "
                              "it is earned.",
                "note_corps": "Every point comes from a real record in the "
                              "tower: a mission delivered, a security finding "
                              "kept, a regression caught, a guide written. "
                              "None of these numbers can be edited.",
                "points": "points", "palier": "next level at",
                "dernier": "last level reached", "eteint": "off",
                "total": "Team total:", "compteurs": "Counters are re-read "
                            "every time this page is opened.",
                "accueil": "Home", "vitrine": "the showcase", "niv": "Lv.",
                "confidentiel": "confidential",
            },
            "ja": {
                "titre": "仲間", "intro": "管制塔の仲間たち。それぞれに役割があり、"
                         "誰一人として代わりがききません。",
                "note_titre": "以下の経験値は手で入力するものではなく、"
                              "積み上げていくものです。",
                "note_corps": "すべてのポイントは管制塔の実際の記録から来ています："
                              "完了したミッション、採用されたセキュリティ指摘、"
                              "捉えたリグレッション、書かれたガイド。"
                              "これらの数字は誰も変更できません。",
                "points": "ポイント", "palier": "次の階級まで",
                "dernier": "最終階級到達", "eteint": "停止中",
                "total": "チーム合計：", "compteurs": "カウンターはこのページを"
                            "開くたびに読み直されます。",
                "accueil": "ホーム", "vitrine": "ショーケース", "niv": "階級",
                "confidentiel": "機密",
            },
        }[lang if lang in ("en", "ja") else "fr"]
        return {
            "lang": lang if lang in ("en", "ja") else "fr",
            "L": L,
            "trad": lambda texte: (cache.get(texte) if cache else None)
                    or texte or "",
        }

    def _vue_membre(self, m, trad):
        """Le membre traduit pour l'affichage. Le perimetre est du HTML : on
        traduit son texte nu et on le remet dans un <p>."""
        perimetre = re.sub(r"<[^>]+>", " ", m.perimetre or "").strip()
        perimetre = re.sub(r"\s+", " ", perimetre)
        perimetre = trad(perimetre)
        return {
            "id": m.id,
            "name": m.name,
            "embleme": m.embleme,
            "poste": _sans_marques(trad(m.poste or "")),
            "niveau": m.niveau,
            "titre": _sans_marques(trad(m.titre or "")),
            "titre_jp": m.titre_jp,
            "avancement": m.avancement,
            "xp": m.xp,
            "xp_palier": m.xp_palier,
            "active": m.active,
            "perimetre": _sans_marques(perimetre),
            "origine": _sans_marques(trad(m.origine or "")),
            "refus": _sans_marques(m.refus),
            "competences": [{
                "name": trad(c.name),
                "valeur": c.valeur,
                "etoiles": c.etoiles,
                "confidentiel": c.confidentiel,
            } for c in m.competence_ids],
        }

    def _membres_vus(self, membres, lang):
        ctx = self._trad_ctx(lang)
        trie = membres.sorted(lambda m: (-m.xp, m.sequence))
        vus = [self._vue_membre(m, ctx["trad"]) for m in trie]
        return vus, ctx

    @http.route("/tour/equipe", type="http", auth="user", website=False)
    def equipe(self, **kw):
        # La page montre l'équipe, ses XP et ses rôles : des données du
        # propriétaire, pas celles d'un invité (règle de Patrick, 01/08).
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        lang = (kw.get("lang") or "fr")[:2]
        membres = request.env["equipe.membre"].sudo().search([])
        # On mesure à l'affichage plutôt qu'au seul passage du cron : une page
        # qui montre des chiffres d'hier fait douter de tous les autres.
        # Le coût est de quelques `search_count`, pas d'un calcul.
        membres.mapped("competence_ids")._mesurer()
        nom = request.env["ir.config_parameter"].sudo().get_param(
            "tour_equipage.nom", "Dōryō")
        sens = request.env["ir.config_parameter"].sudo().get_param(
            "tour_equipage.sens",
            "Dōryō (同僚) : les collègues, l'équipe de travail")
        vus, ctx = self._membres_vus(membres, lang)
        return request.render("tour_equipage.page_equipage", {
            "membres": vus,
            "nom_equipage": nom,
            "sens_nom": sens,
            "total_xp": sum(membres.mapped("xp")),
            "L": ctx["L"],
            "lingua": ctx["lang"],
        })

    @http.route("/tour/equipe-public", type="http", auth="public",
                website=False)
    def equipe_publique(self, **kw):
        """La page d'équipe VUE DE LA VITRINE : même design, données filtrées
        par le template public (pas de refus, pas de liens internes). Le rendu
        passe au scan des garde-fous (termes interdits + liens privés) avant
        toute publication — voir deploy/verifier-posts-publics.sh."""
        lang = (kw.get("lang") or "fr")[:2]
        membres = request.env["equipe.membre"].sudo().search([])
        membres.mapped("competence_ids")._mesurer()
        nom = request.env["ir.config_parameter"].sudo().get_param(
            "tour_equipage.nom", "Dōryō")
        vus, ctx = self._membres_vus(membres, lang)
        return request.render("tour_equipage.page_equipage_public", {
            "membres": vus,
            "nom_equipage": nom,
            "total_xp": sum(membres.mapped("xp")),
            "L": ctx["L"],
            "lingua": ctx["lang"],
        })

    @http.route("/tour/equipe/<int:membre_id>", type="http", auth="user", website=False)
    def fiche(self, membre_id, **kw):
        """Le tableau de bord d'UN agent : son travail, ce qui l'attend.

        Même principe que l'accueil de Patrick : on ne liste pas tout ce qui
        existe, on montre ce qui a bougé et ce qui attend quelqu'un. Un tableau
        de bord exhaustif est une archive, pas un tableau de bord.
        """
        m = request.env["equipe.membre"].sudo().browse(membre_id)
        if not m.exists():
             return request.not_found()
        m.competence_ids._mesurer()
        # --- LA CARTE DE CET AGENT (06/08, Patrick) : les circuits où il a
        # une porte, et les instances en cours qui l'attendent. Il ne voit
        # pas les 100+ gabarits : seulement les siens.
        circuits_agent = []
        attente_agent = []
        if "circuit.modele" in request.env:
            Etape = request.env["circuit.etape"].sudo()
            Instance = request.env["circuit.instance"].sudo()
            portes = Etape.search(
                [("membre_id", "=", m.id), ("role", "=", "agent")])
            modeles = portes.mapped("modele_id").filtered(lambda g: g.active)
            for g in modeles:
                circuits_agent.append({
                    "id": g.id,
                    "name": g.name,
                    "type_operation": g.type_operation,
                    "nb_etapes": len(g.etape_ids),
                    "portes": [{
                        "nom": e.name,
                        "agent": (e.membre_id.name
                                  if e.role == "agent" and e.membre_id
                                  else "Patrick"),
                        "role": e.role,
                    } for e in g.etape_ids.sorted("sequence")],
                })
            instances = Instance.search(
                [("etat", "=", "en_cours")], order="create_date desc")
            for inst in instances:
                etapes = inst.modele_id.etape_ids.sorted(
                    lambda e: (e.sequence, e.id))
                if inst.etape_courante <= len(etapes):
                    porte = etapes[inst.etape_courante - 1]
                    if porte.membre_id.id == m.id and porte.role == "agent":
                        attente_agent.append({
                            "id": inst.id,
                            "name": inst.name,
                            "porte": porte.name,
                            "modele": inst.modele_id.name,
                        })
        return request.render("tour_equipage.page_agent", {
            "m": m,
            "travaux": m._travaux(),
            "evolution": m._evolution(),
            "conso": m._consommation(),
            "attente": m._attente(),
            "circuits_agent": circuits_agent,
            "attente_agent": attente_agent,
            # La spec modifiable (poste, périmètre, refus, consignes, exemples)
            "spec": self._specs_vue(m),
            # Sa fiche de poste (agents/<nom>.md) — la connaissance injectée
            # dans ses missions. Rien n'est servi si elle n'existe pas.
            "connaissance_agent": self._fiche_agent(m),
            # L'origine du nom est une clé de lecture pour le propriétaire,
            # pas une information de service : elle ne sort qu'ici.
            "est_admin": request.env.user.has_group("base.group_system"),
        })

    @http.route("/tour/agents", type="http", auth="user", website=False)
    def qui_travaille(self, **kw):
        """Ancienne adresse de « Qui travaille ? » — le cockpit agents la remplace.

        Patrick, 31/07 : « je préfère un dashboard conçu comme cockpit ».
        La page vit désormais sur /tour/cockpit/agents (tour_cockpit), au même
        look que le cockpit. Cette route garde l'ancienne URL vivante pour ne
        casser aucun lien, et redirige vers la nouvelle.
        """
        return request.redirect("/tour/cockpit/agents", code=301)

    @http.route("/tour/equipe/<int:membre_id>/basculer", type="http",
                auth="user", website=False, methods=["POST"])
    def basculer(self, membre_id, **kw):
        """Éteindre / rallumer un agent — ADMIN SEULEMENT.

        Le bouton de la fiche agent envoie un POST ici. Le contrôle d'accès
        se fait sur le VRAI utilisateur de la requête (request.env.user) :
        la méthode modèle est appelée en sudo() pour écrire, mais l'autorisation
        n'est pas déléguée à l'objet — c'est la requête qui décide.
        """
        if not request.env.user.has_group("base.group_system"):
            return request.forbidden()
        m = request.env["equipe.membre"].sudo().browse(membre_id)
        if not m.exists():
            return request.not_found()
        m.action_basculer_activite()
        return request.redirect("/tour/equipe/%s" % m.id)

    # -- GALERIE DES SPECS DES AGENTS (05/08, Patrick) ----------------------
    # Une webapp au style de la tour (moteur 2D maison) : tu choisis l'agent
    # dans une grille de cartes-avatars, tu l'ouvres, tu vois ET tu modifies
    # tous ses points (poste, périmètre, refus, consignes, exemples).
    # ADMIN SURTOUT : voir/modifier les specs des agents = toucher au cerveau.
    # Même pattern de droit que « basculer » : on vérifie le vrai user.
    def _specs_vue(self, m):
        """La « spec » d'un agent, telle qu'on la montre et l'édite."""
        return {
            "id": m.id,
            "name": m.name,
            "embleme": m.embleme or "🛠️",
            "poste": _sans_marques(m.poste or ""),
            "origine": _sans_marques(m.origine or ""),
            "perimetre": _sans_marques(m.perimetre or ""),
            "refus": _sans_marques(m.refus or ""),
            "consignes": _sans_marques(m.consignes or ""),
            "exemples": _sans_marques(m.exemples or ""),
            "moteur": m.moteur or "",
            "active": m.active,
            "eteint": not m.active,
            "niveau": m.niveau,
            "xp": m.xp,
            "titre": _sans_marques(m.titre or ""),
        }

    _FICHES_AGENTS = None

    def _fiche_agent(self, m):
        """La connaissance d'un agent = sa fiche de poste agents/<nom>.md,
        celle-là même qui est injectée en tête de chaque mission (atelier.sh).

        Les fiches vivent sur l'host (~/tour/agents) que le conteneur ne voit
        pas : un script hôte (deploy/agents-fiches.sh) les rassemble dans
        /mnt/atelier/agents-fiches.json, monté dans le conteneur. On résout
        ici le nom du membre vers une fiche par normalisation (minuscules,
        sans accents ni tirets), avec une table pour les cas qui ne mappent
        pas tout seuls (Raph -> raphael, Jor-El -> jorel, Mirline = Raph)."""
        if self._FICHES_AGENTS is None:
            import json as _json
            import unicodedata as _u
            import re as _re
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
            self._FICHES_AGENTS = (explicite, candidats, fiches, norme)
        explicite, candidats, fiches, norme = self._FICHES_AGENTS
        if m.name in explicite:
            nom_fiche = explicite[m.name]
        else:
            nom_fiche = candidats.get(norme(m.name))
        if not nom_fiche or nom_fiche not in fiches:
            return ""
        return fiches[nom_fiche].get("contenu", "")

    @http.route("/tour/specs", type="http", auth="user", website=False)
    def specs_galerie(self, **kw):
        """La galerie : chaque agent est une carte/avatar (moteur 2D maison).
        Tu choisis celui que tu veux voir/modifier. Ordre : priorité = XP."""
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        membres = request.env["equipe.membre"].sudo().search([])
        membres.mapped("competence_ids")._mesurer()
        trie = membres.sorted(lambda m: (-m.xp, m.sequence))
        cartes = [self._specs_vue(m) for m in trie]
        return request.render("tour_equipage.page_specs_agents", {
            "agents": cartes,
            "agents_json": json.dumps(cartes, ensure_ascii=False),
            "total": len(cartes),
        })

    @http.route("/tour/specs/<int:membre_id>", type="http", auth="user",
                website=False)
    def specs_detail(self, membre_id, **kw):
        """La fiche éditable d'UN agent : on voit sa spec et on peut la
        modifier (POST vers /tour/specs/<id>/sauver)."""
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        m = request.env["equipe.membre"].sudo().browse(membre_id)
        if not m.exists():
            return request.not_found()
        return request.render("tour_equipage.page_specs_detail", {
            "a": self._specs_vue(m),
        })

    @http.route("/tour/specs/<int:membre_id>/sauver", type="http",
                auth="user", website=False, methods=["POST"])
    def specs_sauver(self, membre_id, **kw):
        """Enregistre les specs modifiées d'un agent — ADMIN SEULEMENT."""
        if not request.env.user.has_group("base.group_system"):
            return request.forbidden()
        m = request.env["equipe.membre"].sudo().browse(membre_id)
        if not m.exists():
            return request.not_found()
        vals = {}
        for champ in ("poste", "perimetre", "refus", "consignes", "exemples"):
            if champ in kw and kw[champ] is not None:
                vals[champ] = kw[champ]
        if not vals:
            return request.redirect("/tour/specs/%s" % m.id)
        m.write(vals)
        return request.redirect("/tour/specs/%s" % m.id)
