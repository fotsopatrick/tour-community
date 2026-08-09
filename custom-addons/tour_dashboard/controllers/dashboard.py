# -*- coding: utf-8 -*-
"""La page d'accueil de la tour.

Ordre imposé par le propriétaire : d'abord ce qu'il y a à faire, ensuite les
actus. Et la première question à laquelle la page doit répondre sans qu'on
clique : « qu'est-ce qui m'attend, moi ? »
"""
import json
import logging
import re
import time
import urllib.parse
import urllib.request

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)
try:
    from odoo.addons.tour_i18n.models.traduction import contexte_langue
except Exception:
    def contexte_langue(user):
        return {"lang": "fr", "_t": lambda m: m, "trad": {}}

PROJET_JOURNAL = "ODOO"

# LE MODE AUTO (01/08). Patrick autorise Raph à décider seul — et veut un
# bouton d'arrêt dans SON menu Actions, réservé à LUI. Le mode vit dans un
# paramètre : tour.mode_auto = "1" (auto) / "0" (arrêté). Seul le propriétaire
# (les deux courriels de Patrick) peut l'activer ou l'arrêter — pas un autre
# admin, pas la démo.
PARAM_MODE_AUTO = "tour.mode_auto"


def _owner_ids():
    """Les identifiants du propriétaire : config (hors git), pas en dur."""
    val = (request.env["ir.config_parameter"].sudo().get_param(
        "tour_owner.identifiants", "") or "")
    return {x.strip().lower() for x in val.split(",") if x.strip()}



def _acces_invite(url, secours):
    """Cet utilisateur peut-il ouvrir `url` ?

    La reponse vient de tour.actions.config : le drapeau « Invites ? » ET la
    case de l'environnement. Meme regle que celle qui decide d'afficher le
    lien dans le menu Actions. Si le module de config n'est pas installe, on
    rend `secours` — le garde d'origine.
    """
    env = request.env
    if "tour.actions.config" in env:
        return env["tour.actions.config"].sudo().autorise(url)
    return secours()

class TourDashboard(http.Controller):

    @http.route("/demo-etat", type="http", auth="public", website=False)
    def demo_etat(self, **kw):
        """Statut des comptes démo, en direct (pour la vitrine publique).

        Public : la page demo-acces de la vitrine l'interroge pour afficher
        « libre / occupé ». Un compte est occupé si quelqu'un s'y est connecté
        dans les 10 dernières minutes (log_date).
        """
        Users = request.env["res.users"].sudo()
        maintenant = fields.Datetime.now()
        comptes = []
        for i in range(1, 6):
            u = Users.search(
                [("login", "=", "demo%d@demo.local" % i)], limit=1)
            occupe = False
            derniere = ""
            if u and "log_ids" in u._fields:
                dernier_log = u.log_ids[:1]
                if dernier_log and dernier_log.create_date:
                    derniere = dernier_log.create_date.strftime("%H:%M")
                    occupe = (maintenant - dernier_log.create_date
                              ).total_seconds() < 600
            comptes.append({
                "login": "demo%d@demo.local" % i,
                "occupe": occupe,
                "derniere": derniere,
            })
        corps = json.dumps({"comptes": comptes}).encode("utf-8")
        return request.make_response(
            corps, headers=[("Content-Type", "application/json; charset=utf-8")])

    # ------------------------------------------------------------------
    # Twitch — « EN DIRECT » pour la vitrine (08/08, Merline).
    #
    # La vitrine est statique : elle ne peut pas interroger Twitch elle-même
    # (il faudrait y mettre le secret, et le secret sortirait). Elle appelle
    # donc CETTE route publique, qui lit le Coffre, parle à Twitch à sa
    # place, et répond « live ou pas ». Le token d'application et le résultat
    # sont mis en cache (paramètres) pour ne pas marteler l'API à chaque
    # affichage d'une page.
    # ------------------------------------------------------------------
    TWITCH_CHAINE = "codenominomi"

    def _twitch_etat(self, **kw):
        """Live ou pas sur Twitch. Ne lève jamais : la vitrine doit rester
        muette (pas de badge) plutôt que de planter si Twitch est injoignable."""
        Param = request.env["ir.config_parameter"].sudo()
        maintenant = time.time()
        # Cache court (90 s) : une page de la vitrine qui appelle dix fois
        # dans la minute ne doit pas faire dix appels à Twitch.
        cache = Param.get_param("tour.twitch_live_cache", "")
        if cache:
            try:
                d = json.loads(cache)
                if d.get("_jusque", 0) > maintenant:
                    return d
            except (ValueError, TypeError):
                pass
        Vault = request.env["vault.secret"].sudo()
        try:
            client_id = Vault.search(
                [("name", "=", "Twitch — Client ID (app Tour de controle)")],
                limit=1)._valeur_claire("indicateur LIVE de la vitrine")
            client_secret = Vault.search(
                [("name", "=", "Twitch — Client Secret (app Tour de controle)")],
                limit=1)._valeur_claire("indicateur LIVE de la vitrine")
        except Exception:  # noqa: BLE001
            _logger.warning("Twitch LIVE : secrets illisibles", exc_info=True)
            return {"live": False}
        if not client_id or not client_secret:
            return {"live": False}
        # Token d'application, caché ~23 h (les app tokens Twitch durent
        # plusieurs jours ; on le reprend bien avant son expiration).
        token = Param.get_param("tour.twitch_token", "")
        token_jusque = float(Param.get_param(
            "tour.twitch_token_jusque", "0") or 0)
        if not token or token_jusque < maintenant + 300:
            try:
                corps = urllib.parse.urlencode({
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "client_credentials",
                }).encode("utf-8")
                req = urllib.request.Request(
                    "https://id.twitch.tv/oauth2/token", data=corps,
                    headers={"Content-Type":
                             "application/x-www-form-urlencoded"})
                with urllib.request.urlopen(req, timeout=15) as rep:
                    data = json.loads(rep.read().decode("utf-8"))
                token = data.get("access_token", "")
                expires = int(data.get("expires_in", 86400))
                Param.set_param("tour.twitch_token", token)
                Param.set_param("tour.twitch_token_jusque",
                                str(int(maintenant + expires)))
            except Exception:  # noqa: BLE001
                _logger.warning("Twitch LIVE : token impossible", exc_info=True)
                return {"live": False}
        if not token:
            return {"live": False}
        # La question qui nous intéresse : la chaîne diffuse-t-elle, là,
        # maintenant ?
        try:
            url = ("https://api.twitch.tv/helix/streams?user_login="
                   + urllib.parse.quote(self.TWITCH_CHAINE))
            req = urllib.request.Request(
                url, headers={"Client-ID": client_id,
                              "Authorization": "Bearer " + token})
            with urllib.request.urlopen(req, timeout=15) as rep:
                data = json.loads(rep.read().decode("utf-8"))
            flux = data.get("data") or []
            if not flux:
                etat = {"live": False}
            else:
                s = flux[0]
                etat = {
                    "live": True,
                    "titre": (s.get("title") or "")[:200],
                    "jeu": (s.get("game_name") or "")[:120],
                    "spectateurs": s.get("viewer_count") or 0,
                    "depuis": s.get("started_at") or "",
                }
            etat["_jusque"] = maintenant + 90
            Param.set_param("tour.twitch_live_cache",
                            json.dumps(etat))
            return etat
        except Exception:  # noqa: BLE001
            _logger.warning("Twitch LIVE : lecture du flux impossible",
                            exc_info=True)
            return {"live": False}

    @http.route("/tour/twitch-live", type="http", auth="public", website=False)
    def twitch_live(self, **kw):
        """Statut Twitch en direct, pour la vitrine publique.

        Public : le pied de page de la vitrine l'interroge pour afficher
        « EN DIRECT » quand Patrick diffuse. Ne renvoie JAMAIS de secret :
        seulement live/titre/jeu/spectateurs.
        """
        etat = self._twitch_etat(**kw)
        corps = json.dumps(etat).encode("utf-8")
        return request.make_response(
            corps, headers=[("Content-Type", "application/json; charset=utf-8"),
                            ("Cache-Control", "no-cache"),
                            ("Access-Control-Allow-Origin", "*")])

    def _dispo(self):
        """Disponibilité. Chemin paramétrable (tour_dashboard.dispo_path) ;
        par défaut vide — en édition Community, pas de fichier, donc False."""
        chemin = request.env["ir.config_parameter"].sudo().get_param(
            "tour_dashboard.dispo_path", "")
        if not chemin:
            return False
        try:
            with open(chemin, encoding="utf-8") as f:
                ligne = f.readline().strip()
            morceaux = ligne.split("\t")
            if len(morceaux) >= 2:
                return {"quand": morceaux[0], "etat": morceaux[1],
                        "raison": morceaux[2] if len(morceaux) > 2 else ""}
        except OSError:
            pass
        return False

    @http.route("/tour/dashboard", type="http", auth="user", website=False)
    def dashboard(self, **kw):
        # La toute premiere visite passe par la page de bienvenue. Une seule
        # fois : le champ est pose des l affichage, donc un rechargement ne la
        # ramene pas. Une page d accueil qui revient a chaque connexion devient
        # un obstacle qu on apprend a fermer sans lire.
        user = request.env.user
        if "bienvenue_vue" in user._fields and not user.bienvenue_vue:
            return request.redirect("/tour/bienvenue")
        env = request.env
        user = env.user
        est_admin = user.has_group("base.group_system")

        # Configuration du menu Actions (module tour_actions) : chargée une
        # seule fois pour l'env courant, réutilisée par le rendu qui suit.
        _actions_config = (env["tour.actions.config"].sudo().reglages()
                           if "tour.actions.config" in env else None)
        _actions_urls = set(r["url"] for r in (_actions_config or [])
                            if r["visible"] and r["url"])
        # Les adresses que CET utilisateur a le droit d'ouvrir. Calculees en
        # une fois : interroger le modele quarante fois pour rendre une page
        # coute quarante recherches.
        _urls_permises = (env["tour.actions.config"].sudo().urls_autorisees(
            env.user) if _actions_config is not None else set())

        # FAILLE FERMEE (30/07) : le journal (projet ODOO) est le tableau
        # de bord de PATRICK. Sans ce garde, tout interne (invite) voyait
        # son accueil ET ses taches. Un non-admin passe desormais par le
        # bloc `else` (listes vides) et ne voit que SON propre travail
        # (missions/debats deja bornes plus bas). Ils ont leur propre accueil.
        projet = env["project.project"].search(
            [("name", "ilike", PROJET_JOURNAL)], limit=1) if est_admin else env["project.project"]

        taches = env["project.task"]
        if projet:
            base = [("project_id", "=", projet.id)]
            fait = env.ref("tour_dashboard.stage_fait", raise_if_not_found=False)
            pas_fait = base + ([("stage_id", "!=", fait.id)] if fait else [])

            # CE QUI T ATTEND AUJOURD HUI, pas tout ce qui traine.
            #
            # Patrick, le 28/07 : << on enleve ce qui m attend de l accueil ?
            # c est pas mieux que tout en vrac ? >>. Il avait raison sur le
            # vrac, pas sur la suppression : le planning dit QUAND, l accueil
            # dit MAINTENANT. Supprimer le second obligerait a ouvrir un ecran
            # pour savoir s il y a le feu.
            #
            # On ne garde donc que trois choses : ce qui est en priorite haute,
            # ce qui a une echeance aujourd hui ou passee, et ce qui bloque
            # quelqu un d autre. Le reste vit dans le planning, un lien plus
            # bas y mene. Une liste de vingt lignes ne se lit pas : elle se
            # survole, donc elle ne sert plus a rien.
            import datetime
            aujourd_hui = fields.Date.context_today(taches)
            a_moi = pas_fait + [("qui", "in", ("proprietaire", "partage"))]
            urgentes = taches.search(
                a_moi + ["|", ("priority", "=", "1"),
                         ("date_deadline", "<=", aujourd_hui)],
                order="date_deadline asc, priority desc, id desc", limit=6)
            m_attend = urgentes
            m_attend_total = taches.search_count(a_moi)
            en_cours = taches.search(
                pas_fait + [("qui", "=", "claude")], order="id desc", limit=12)
            non_classees = taches.search_count(pas_fait + [("qui", "=", False)])
            recemment = taches.search(
                base + ([("stage_id", "=", fait.id)] if fait else []),
                order="write_date desc", limit=8)
            reste = taches.search_count(pas_fait)
        else:
            m_attend = en_cours = recemment = taches
            non_classees = reste = m_attend_total = 0

        # FAIT RECEMMENT, TOUTES SOURCES ET SIGNE (29/07). Patrick : « pas
        # du tout mis a jour automatiquement, et aucune distinction de qui
        # a accompli ». La liste ne vivait que des consignations manuelles
        # du journal — le travail des agents (missions, debats) n'y entrait
        # jamais tout seul. On FUSIONNE les trois sources par date, chacune
        # signee. Zero nouvel enregistrement : on lit ce qui existe.
        fait_recemment = []
        for t in recemment:
            fait_recemment.append({
                "quand": t.write_date,
                "qui": dict(t._fields["qui"].selection).get(t.qui) or "Claude",
                "titre": t.name,
                "href": "/odoo/project/%s/tasks/%s" % (t.project_id.id, t.id),
            })
        # Un invite ne voit dans ce fil QUE son propre travail — la lecon
        # du 29/07 (les 447 taches d'Imane), appliquee AVANT d'etre mordu.
        borne = [] if est_admin else [("create_uid", "=", user.id)]
        if "atelier.mission" in env:
            Avis = env["debat.avis"].sudo() if "debat.avis" in env else None
            for m in env["atelier.mission"].sudo().search(
                    [("etat", "=", "terminee")] + borne,
                    order="write_date desc", limit=8):
                agent = m.AGENTS.get((m.moteur or "").strip(), "L'atelier")
                if Avis is not None:
                    avis = Avis.search([("mission_id", "=", m.id)], limit=1)
                    if avis:
                        agent = avis.membre_id.name
                fait_recemment.append({
                    "quand": m.write_date, "qui": agent, "titre": m.name,
                    "href": "/web#id=%s&model=atelier.mission&view_type=form"
                            % m.id,
                })
        if "debat.sujet" in env:
            for d in env["debat.sujet"].sudo().search(
                    [("etat", "=", "rendu")] + borne,
                    order="write_date desc", limit=4):
                fait_recemment.append({
                    "quand": d.write_date, "qui": "Le débat",
                    "titre": "Avis rendus : %s" % d.name,
                    "href": "/web#id=%s&model=debat.sujet&view_type=form"
                            % d.id,
                })
        # DATE + HEURE, dans le fuseau de l utilisateur (Patrick, 30/07 :
        # << je ne vois pas l heure ni le jour >>). write_date est en UTC ;
        # context_timestamp le ramene a l heure locale. Sans ca, un
        # horodatage ment de deux heures l ete.
        for f in fait_recemment:
            q = f.get("quand")
            if q:
                loc = fields.Datetime.context_timestamp(request.env.user, q)
                f["quand_txt"] = loc.strftime("%d/%m à %Hh%M")
            else:
                f["quand_txt"] = ""
        fait_recemment.sort(key=lambda x: x["quand"] or "", reverse=True)
        fait_recemment = fait_recemment[:8]

        # Les activités du jour (rappels récurrents compris) : c'est le
        # deuxième « ça m'attend », et il ne vit pas dans le journal.
        # Un invité (portal) n'a pas les droits internes sur mail.activity :
        # sans .sudo() la recherche levait une Forbidden à la première visite
        # d'un compte d'invitation — erreur bloquante sur l'accueil.
        activites = env["mail.activity"].sudo().search(
            [("user_id", "=", user.id),
             ("date_deadline", "<=", fields.Date.context_today(env.user))],
            order="date_deadline", limit=10)

        # La langue des actus est un choix PAR UTILISATEUR (dropdown à côté
        # du titre). « toutes » = pas de filtre — le comportement d'avant.
        actus_langue = getattr(user, "actus_langue", None) or "toutes"
        dom_actus = [] if actus_langue == "toutes" else \
            [("langue", "=", actus_langue)]
        articles = env["actus.article"].search(
            dom_actus, order="date_pub desc", limit=6)

        # Les compteurs sont cliquables : chacun ouvre la liste filtrée
        # correspondante plutôt que d'être un chiffre mort.
        def lien(xmlid):
            act = env.ref("tour_dashboard.%s" % xmlid, raise_if_not_found=False)
            return "/odoo/action-%s" % act.id if act else "#"

        # Le registre des faits de l'équipe (module équipe, s'il est là) :
        # la porte « voir tout » du bloc Fait récemment.
        act_exploit = env.ref("tour_equipage.action_exploit",
                              raise_if_not_found=False)
        lien_exploits = "/odoo/action-%s" % act_exploit.id if act_exploit else ""

        # QUI ATTEND QUI.
        #
        # La question que Patrick a posee le 27/07 : « est-ce que je bloque
        # quelque chose ? ». Il n'y avait aucun moyen d'y repondre sans me
        # demander — or c'est exactement le genre d'information qu'on ne
        # devrait jamais avoir a demander a quelqu'un.
        #
        # Les briques existaient depuis toujours : Odoo porte depend_on_ids
        # (bloquee par) et dependent_ids (bloque), et le champ « qui » dit a
        # qui revient la tache. Personne ne les avait croisees.
        #
        # On compte deux choses, et deux seulement — un tableau de bord qui
        # repond a trois questions n'en repond a aucune :
        #   - ce que JE bloque : mes taches dont d'autres dependent
        #   - ce qui ME bloque : mes taches en attente de quelqu'un d'autre
        ouvertes = [("stage_id.fold", "=", False)]
        je_bloque = en_cours_bloquees = 0
        try:
            miennes = taches.search(
                ouvertes + [("qui", "in", ("proprietaire", "partage"))])
            je_bloque = len(miennes.filtered(
                lambda t: any(not d.stage_id.fold for d in t.dependent_ids)))
            siennes = taches.search(ouvertes + [("qui", "=", "claude")])
            en_cours_bloquees = len(siennes.filtered(
                lambda t: any(not d.stage_id.fold for d in t.depend_on_ids)))
        except Exception:  # noqa: BLE001 — l'accueil ne doit jamais tomber
            pass

        # Le planning de la semaine : un lien, pas une liste. L'accueil dit
        # deja ce qui attend AUJOURD'HUI ; y deverser la semaine entiere
        # noierait le jour present, qui est le seul sur lequel on peut agir.
        etiquette = env["project.tags"].sudo().search(
            [("name", "like", "semaine-")], order="id desc", limit=1)
        lien_semaine = ""
        if etiquette:
            act = env.ref("tour_dashboard.action_taches_restantes",
                          raise_if_not_found=False)
            if act:
                lien_semaine = "/odoo/action-%s" % act.id

        # Les offres d'essai : reservees a l'admin, et affichees seulement
        # quand elles existent. On ne fait pas chercher un lien qu'on utilise
        # a chaque test — le chercher a chaque fois, c'est finir par ne plus
        # tester.
        essais = env["abonnement.offre"].sudo().search(
            [("publie", "=", True), ("lien_paiement", "!=", False),
             ("name", "ilike", "ESSAI")]) if est_admin and "abonnement.offre" in env else False

        # Le cap. Affiche en haut, discretement : la ligne d'arrivee doit
        # etre sous les yeux SANS occuper la place de ce qu'il y a a faire.
        # Un objectif qui prend tout l'ecran devient un decor qu'on ne lit
        # plus au bout de trois jours.
        cap = env["tour.cap"].sudo().courant()

        # Qui est là, maintenant. Odoo le sait déjà (bus.presence, alimenté
        # par le canal temps réel) — on ne mesure rien de neuf, on affiche ce
        # qui existait sans être visible nulle part.
        #
        # « en ligne » seulement, pas « absent » : un onglet ouvert depuis ce
        # matin sur une autre machine n'est pas quelqu'un qui travaille, et le
        # compter donnerait un chiffre flatteur et faux.
        connectes = 0
        if "bus.presence" in env:
            connectes = env["bus.presence"].sudo().search_count(
                [("status", "=", "online")])

        # Missions traitées aujourd'hui (08/08, Patrick) : le compteur se
        # synchronise avec l'atelier — « livrée » veut dire que la mission a
        # été relevée et terminée (ou échouée) par l'atelier, pas seulement
        # créée. `livree_le` est posé par la relève au moment où l'atelier
        # rend son compte rendu.
        missions_traitees = 0
        if "atelier.mission" in env:
            aujourdhui = fields.Datetime.subtract(
                fields.Datetime.now(), days=0)
            missions_traitees = env["atelier.mission"].sudo().search_count(
                [("livree_le", ">=", aujourdhui.replace(hour=0, minute=0, second=0))])

        # La cagnotte : on LIT le dernier relevé, on n'appelle jamais Stripe
        # ici. Un appel réseau au chargement d'une page la rend lente quand le
        # fournisseur rame et blanche quand il tombe — pour un chiffre qu'on
        # regarde en passant. Le relevé tourne de son côté toutes les 4 h.
        cagnotte = env["stripe.releve"].sudo().dernier() if est_admin else False
        cagnotte_date = ""
        if cagnotte:
            cagnotte_date = fields.Datetime.context_timestamp(
                cagnotte, cagnotte.create_date).strftime("%d/%m à %Hh%M")

        # Sans en-tete de cache, le navigateur decide seul — et un
        # telephone garde volontiers une page consultee il y a une heure.
        # Patrick a suivi le travail depuis dehors le 27/07 et n'a rien vu
        # bouger : tout etait pourtant en base. Une page qui montre << ce
        # qui t'attend AUJOURD'HUI >> ne doit jamais etre servie depuis un
        # cache : c'est la seule page ou l'ancienneté est un mensonge.
        # Les décisions en attente — la deuxième porte. Compté ici et pas
        # dans le gabarit : si le module n'est pas installé, la page vit
        # sans lui, elle ne casse pas.
        nb_decisions = 0
        if "decision.fiche" in request.env:
            try:
                nb_decisions = request.env["decision.fiche"].nb_en_attente()
            except Exception:  # noqa: BLE001
                nb_decisions = 0

        # Les PRÉ-DÉCISIONS DU CLONE (31/07, Patrick : « combien de décisions
        # mon clone a pris, pré-décision quoi »). On compte les propositions
        # (<li>) des fiches « Décisions du clone » en attente : chaque ligne
        # est une pré-décision que Patrick doit valider ou corriger.
        nb_predecisions_clone = 0
        if "decision.fiche" in request.env:
            try:
                Fiches = request.env["decision.fiche"].sudo()
                fiches = Fiches.search(
                    [("etat", "=", "attente"),
                     ("origine", "=", "Clone de Patrick")])
                nb_predecisions_clone = sum(
                    (f.resume or "").count("<li>") for f in fiches)
            except Exception:  # noqa: BLE001
                nb_predecisions_clone = 0

        # Le compteur copilote (tâche 430) : chacun voit ce qu'il a consommé
        # et ce qui lui reste, sans le demander à personne. Quota nul = pas
        # de limite, donc rien à afficher. Même règle que les décisions :
        # si le module n'est pas là, la page vit sans lui.
        copilote = None
        if "copilote.usage" in request.env:
            try:
                Usage = request.env["copilote.usage"].sudo()
                quota = Usage._quota_du_jour(user)
                # En sudo et pas via le champ res.users : le champ est
                # réservé admin pour que personne ne lise le compteur
                # d'un autre — ici chacun ne compte que ses lignes.
                consomme = Usage.search_count([
                    ("user_id", "=", user.id),
                    ("jour", "=", fields.Date.context_today(Usage)),
                ])
                # quota <= 0 = pas de limite : on montre quand même le
                # compte (un chiffre compté informe), sans « /0 » trompeur.
                copilote = {
                    "consomme": consomme,
                    "quota": quota if quota > 0 else None,
                    "restant": max(0, quota - consomme) if quota > 0 else None,
                }
            except Exception:  # noqa: BLE001
                copilote = None

        ctx_lang = contexte_langue(request.env.user)
        # Les decisions : module Odoo sur la prod, webapp sur la demo.
        _base = (request.env.cr.dbname or "tour").lower()
        _lien_decisions = "/decisions/" if _base == "tour_test" else "/odoo/action-688"
        reponse = request.render("tour_dashboard.page_accueil", {
            **ctx_lang,
            "lien_decisions": _lien_decisions,
            "nb_decisions": nb_decisions,
            "nb_predecisions_clone": nb_predecisions_clone,
            "copilote": copilote,
            "cap": cap,
            "je_bloque": je_bloque,
            "lien_bloque": lien("action_taches_bloquantes"),
            "en_cours_bloquees": en_cours_bloquees,
            "essais": essais,
            "lien_semaine": lien_semaine,
            "semaine": etiquette.name if etiquette else "",
            "connectes": connectes,
            "missions_traitees": missions_traitees,
            "cagnotte": cagnotte,
            "cagnotte_date": cagnotte_date,
            "lien_reste": lien("action_taches_restantes"),
            "lien_attend": lien("action_taches_moi"),
            "lien_claude": lien("action_taches_claude"),
            "lien_non_classees": lien("action_taches_non_classees"),
            "user": user,
            "est_admin": est_admin,
            "est_owner": user.login.lower() in _owner_ids(),
            # Configuration du menu Actions (module tour_actions, s'il est
            # installé) : la liste des items visibles pour l'environnement
            # courant (prod/démo), selon les cases cochées. Si le module est
            # absent, actions_config vaut None et le template conserve les
            # conditions d'origine ; actions_urls est l'ensemble des adresses.
            "actions_config": _actions_config,
            # Helper QWeb : `_actif('<url>')` renvoie True si le module
            # tour_actions est absent (== menu d'origine), ou si cette
            # adresse est cochée pour l'environnement courant.
            "_actif": (lambda u: u in _actions_urls)
            if _actions_config is not None else (lambda u: True),
            # `_peut('<url>')` — la SEULE question que pose le menu pour un
            # item ouvrable aux invites : « cette personne a-t-elle le droit
            # d'ouvrir cette adresse ? ». La reponse vient de
            # tour.actions.config.autorise(), la meme que celle qu'appliquent
            # les controleurs des pages concernees. Deux appels, une regle :
            # c'est ce qui empeche l'affichage et la protection de diverger.
            # Si le module de config est absent, on retombe sur le role seul —
            # jamais sur « tout le monde passe ».
            "_peut": (lambda u: u in _urls_permises)
            if _actions_config is not None
            else (lambda u: est_admin or user.login.lower() in _owner_ids()),
            "mode_auto": (request.env["ir.config_parameter"].sudo()
                          .get_param(PARAM_MODE_AUTO, "0") == "1"),
            "degre_pilotage": env["tour.capacite"].sudo()._degre()
            if "tour.capacite" in env else False,
            "dispo": self._dispo(),
            "m_attend": m_attend,
            "m_attend_total": m_attend_total,
            "en_cours": en_cours,
            "recemment": recemment,
            "fait_recemment": fait_recemment,
            "non_classees": non_classees,
            "reste": reste,
            "activites": activites,
            "articles": articles,
            "actus_langue": actus_langue,
            "projet": projet,
            "lien_exploits": lien_exploits,
            "moteur_force": (request.env["ir.config_parameter"].sudo()
                             .get_param("atelier.moteur_force") or ""),
        })
        reponse.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        reponse.headers["Pragma"] = "no-cache"
        return reponse

    @http.route("/tour/attention", type="http", auth="user", website=False)
    def attention(self, **kw):
        """CE QUI DEMANDE ATTENTION — une seule page.

        Les briques existaient (signaux, décisions, missions en échec), mais
        chacune vivait dans son coin : rien ne disait à Patrick « regarde,
        là, maintenant ». Cette page rassemble tout ce qui attend un regard :
        les signaux d'alerte (sentinelle, agents), les décisions qui dorment,
        les missions qui ont échoué. Réservée au propriétaire.
        """
        if not _acces_invite("/tour/attention", lambda: request.env.user.login.lower() in _owner_ids()):
            return request.redirect("/tour/dashboard")
        env = request.env
        # tour.signal est un modèle ABSTRAIT : il envoie un courriel, il ne
        # stocke rien. La page ne lit donc que ce qui est réellement en base.
        decisions = []
        if "decision.fiche" in env:
            decisions = env["decision.fiche"].sudo().search(
                [("etat", "=", "attente")], order="create_date asc", limit=20)
        echecs = []
        if "atelier.mission" in env:
            echecs = env["atelier.mission"].sudo().search(
                [("etat", "=", "echec"),
                 ("create_date", ">=", fields.Datetime.subtract(
                     fields.Datetime.now(), days=7))],
                order="create_date desc", limit=20)
        circuits = []
        if "circuit.instance" in env:
            circuits = env["circuit.instance"].sudo().search(
                [("etat", "in", ("brouillon", "en_cours"))],
                order="create_date desc", limit=20)
        return request.render("tour_dashboard.page_attention", {
            "decisions": decisions,
            "echecs": echecs,
            "circuits": circuits,
        })

    @http.route("/tour/resume", type="http", auth="user", website=False)
    def resume(self, **kw):
        """Le résumé de la journée (compétence « résumé des travaux » de Raph).
        Réservé au propriétaire. Rassemble ce qui a bougé le jour choisi (par
        défaut aujourd'hui) : missions, tâches, décisions, guides, circuits,
        appels, solde."""
        if not _acces_invite("/tour/resume", lambda: request.env.user.login.lower() in _owner_ids()):
            return request.redirect("/tour/dashboard")
        env = request.env
        # Le jour choisi ?date=YYYY-MM-DD (défaut : aujourd'hui).
        try:
            jour = fields.Date.to_date(kw.get("date") or "") if kw.get("date") else None
        except ValueError:
            jour = None
        if jour is None:
            jour = fields.Date.context_today(request.env.user)
        fin = jour + __import__("datetime").timedelta(days=1)
        Mission = env["atelier.mission"].sudo()
        Guide = env["tour.guide"].sudo() if "tour.guide" in env else None
        Decision = env["decision.fiche"].sudo() if "decision.fiche" in env else None
        Circuit = env["circuit.modele"].sudo() if "circuit.modele" in env else None
        solde = env["deepseek.solde"].sudo()._comparatif() \
            if "deepseek.solde" in env else False
        resume = {
            "missions_terminees": Mission.search_count(
                [("create_date", ">=", jour), ("etat", "=", "terminee")]) if Mission else 0,
            "missions_echec": Mission.search_count(
                [("create_date", ">=", jour), ("etat", "=", "echec")]) if Mission else 0,
            "missions_en_cours": Mission.search_count(
                [("create_date", ">=", jour), ("etat", "=", "en_cours")]) if Mission else 0,
            "guides": Guide.search_count([("create_date", ">=", jour)]) if Guide else 0,
            "decisions_attente": Decision.search_count(
                [("create_date", ">=", jour)]) if Decision else 0,
            "circuits": Circuit.search_count([("create_date", ">=", jour)]) if Circuit else 0,
            "solde": solde,
        }
        # Appels copilote + coût du jour
        resume["appels"] = {"nb": 0, "cout": 0.0}
        if "copilote.usage" in env:
            rows = env["copilote.usage"].sudo().search(
                [("create_date", ">=", jour)])
            resume["appels"] = {"nb": len(rows),
                                "cout": round(sum(rows.mapped("cout_estime") or [0]), 2)}
        resume["degre"] = env["tour.capacite"].sudo()._degre() \
            if "tour.capacite" in env else False
        # Les TÂCHES du jour (projet) : créées, terminées, en cours.
        resume["taches"] = {"creees": 0, "faites": 0, "en_cours": 0, "liste": []}
        if "project.task" in env:
            Task = env["project.task"].sudo()
            taches = Task.search([("create_date", ">=", jour)],
                                 order="create_date desc", limit=8)
            resume["taches"]["creees"] = len(taches)
            resume["taches"]["faites"] = len(taches.filtered(
                lambda t: (t.state or "").lower() in ("1_done", "done", "fait", "terminee")))
            resume["taches"]["en_cours"] = len(taches.filtered(
                lambda t: "cours" in (t.state or "").lower()
                          or "progress" in (t.state or "").lower()))
            resume["taches"]["liste"] = [
                {"nom": t.name, "etat": t.state or ""} for t in taches]
        # Le trafic de la vitrine (le fruit des publications).
        resume["visites"] = False
        try:
            import json as _json, urllib.request as _ur
            with _ur.urlopen("http://172.17.0.1:3214/json", timeout=4) as _r:
                resume["visites"] = _json.loads(_r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            resume["visites"] = False
        # Les études de Braignak récentes + leurs conclusions.
        resume["etudes"] = []
        if "braignak.etude" in env:
            for e in env["braignak.etude"].sudo().search(
                    [("create_date", ">=", jour)], order="create_date desc",
                    limit=8):
                resume["etudes"].append({
                    "nom": e.name, "etat": e.etat,
                    "verdict": e.verdict or "",
                    "resume": (e.resume or "")[:200],
                })
        return request.render("tour_dashboard.page_resume", {
            "resume": resume,
            "jour": fields.Date.context_today(request.env.user),
            "releve_le": fields.Datetime.context_timestamp(
                request.env.user, fields.Datetime.now()).strftime("%H:%M:%S"),
        })


    @http.route("/tour/business-plan", type="http", auth="user", website=False)
    def business_plan(self, **kw):
        """Le business plan de la tour (prod) — réservé au propriétaire."""
        if request.env.user.login.lower() not in _owner_ids():
            return request.redirect("/tour/dashboard")
        env = request.env
        plan = ""
        if "tour.guide" in env:
            g = env["tour.guide"].sudo().search(
                [("name", "=", "Business plan de la Tour de contrôle")], limit=1)
            if g:
                plan = g.contenu or ""
        etude = env["braignak.etude"].sudo().search(
            [("name", "ilike", "potentiel d'une startup")], limit=1) if "braignak.etude" in env else False
        return request.render("tour_dashboard.page_business_plan", {
            "plan": plan, "etude": etude})


    @http.route("/tour/assembleur", type="http", auth="user", website=False)
    def assembleur(self, **kw):
        """Le dépôt PRIVÉ « tour-en-assembleur » (tâche 1071) — réservé au
        propriétaire. L'accès vit dans le Coffre (vault.secret) ; ici on montre
        le README, le journal git et les fichiers. Jamais public."""
        if request.env.user.login.lower() not in _owner_ids():
            return request.redirect("/tour/dashboard")
        import os
        import subprocess
        # Le dépôt PRIVÉ est monté dans le conteneur (docker-compose) en
        # lecture seule, car le conteneur n'a pas accès au /home de l'hôte.
        # git n'existe pas dans le conteneur : la version est dans VERSION.txt
        # (généré sur l'hôte), le reste se lit en direct.
        REPO = "/srv/tour-en-assembleur"
        readme = fichiers = version = "introuvable"
        if os.path.isdir(REPO):
            try:
                readme = open(os.path.join(REPO, "README.md"),
                              encoding="utf-8").read()
            except Exception:  # noqa: BLE001
                readme = ""
            try:
                version = open(os.path.join(REPO, "VERSION.txt"),
                               encoding="utf-8").read()
            except Exception:  # noqa: BLE001
                version = ""
            try:
                fichiers = subprocess.run(
                    ["ls", "-la", REPO],
                    capture_output=True, text=True, timeout=10).stdout
            except Exception:  # noqa: BLE001
                fichiers = ""
        return request.render("tour_dashboard.page_assembleur", {
            "chemin": REPO,
            "readme": readme,
            "version": version,
            "fichiers": fichiers,
        })


    @http.route("/tour/poser-a-braignak", type="http", auth="user",
                website=False, methods=["GET", "POST"])
    def poser_a_braignak(self, **kw):
        """POSER À BRAIGNAK — accessible à TOUS les utilisateurs.

        Une question qu'on vous a posée, même hors de votre domaine :
        Braignak y répond, pour que vous puissiez répondre sans connaître
        le sujet. La question part en mission, la réponse arrive dans Réponses."""
        env = request.env
        mission = False
        question = (kw.get("question") or "").strip()
        if request.httprequest.method == "POST" and question:
            if "atelier.mission" in env and "equipe.membre" in env:
                b = env["equipe.membre"].sudo().search(
                    [("name", "=", "Braignak")], limit=1)
                if b and b.moteur:
                    m = env["atelier.mission"].sudo().create({
                        "name": "Question de %s — %s" % (env.user.name, question[:40]),
                        "moteur": b.moteur, "etat": "brouillon",
                        "consigne": ("Tu es Braignak, l'observateur. %s te pose une question "
                            "(il ne connait pas le domaine) : %s. Reponds clairement, avec ta "
                            "methode, 15 lignes max — pour qu'il puisse repondre lui-meme." % (
                                env.user.name, question))})
                    m.action_envoyer()
                    mission = m
        return request.render("tour_dashboard.page_braignak", {
            "mission": mission, "question": question})


    @http.route("/tour/education", type="http", auth="user", website=False)
    def education(self, **kw):
        """L'ÉDUCATION — accessible à TOUS les utilisateurs.

        Des guides simples (pour un enfant de 6 ans) sur le monde : voitures,
        fusées, propulsion. Chacun apprend, sans honte de ne pas savoir."""
        env = request.env
        guides = []
        if "tour.guide" in env:
            guides = env["tour.guide"].sudo().search(
                [("categorie", "=", "education"), ("interne", "=", False)],
                order="id desc", limit=20)
        return request.render("tour_dashboard.page_education", {"guides": guides})


    @http.route("/tour/jeu", type="http", auth="user", website=False,
                methods=["GET", "POST"])
    def jeu(self, **kw):
        """LE JEU DES TOURS — une webapp qui communique avec la tour.

        Une réponse (reponse_fiche) devient un défi : le relever crée une
        tâche réelle dans le projet « Jeu des tours », et la réussir fait
        évoluer la tour qui a posé la question. Les scores viennent de la
        base — rien d'inventé."""
        env = request.env
        Projet = env["project.project"].sudo()
        jeu = Projet.search([("name", "=", "Jeu des tours")], limit=1)
        defi = None
        releve = False
        if request.httprequest.method == "POST":
            did = kw.get("defi_id")
            if did and jeu and "project.task" in env:
                try:
                    env["project.task"].sudo().create({
                        "name": "Défi croisé — %s" % (kw.get("defi_nom") or "défi")[:90],
                        "project_id": jeu.id,
                        "user_ids": [(6, 0, [env.user.id])] if "user_ids" in env["project.task"]._fields else None})
                    releve = True
                except Exception:  # noqa: BLE001
                    pass
        # un défi au hasard (une réponse d'une autre source)
        if "reponse.fiche" in env:
            reponses = env["reponse.fiche"].sudo().search([], order="id desc", limit=200)
            if reponses:
                import random
                defi = reponses[random.randrange(len(reponses))]
        # le scoreboard (défis par état)
        score = {"total": 0, "faits": 0}
        if jeu and "project.task" in env:
            taches = env["project.task"].sudo().search([("project_id", "=", jeu.id)])
            score["total"] = len(taches)
            score["faits"] = len(taches.filtered(
                lambda t: (t.state or "").lower() in ("1_done", "done", "fait")))
        return request.render("tour_dashboard.page_jeu", {
            "defi": defi, "releve": releve, "score": score})

    @http.route("/tour/moteur", type="http", auth="user", website=False,
                methods=["POST"], csrf=True)
    def basculer_moteur(self, mode=None, **kw):
        """Le bouton de secours : forcer tous les agents sur un moteur.

        POURQUOI UN BOUTON ET PAS SEULEMENT LE REPLI AUTOMATIQUE.
        Le repli (clé d'API, puis DeepSeek) ne se déclenche qu'APRÈS un échec :
        chaque mission paie un aller-retour perdu avant de basculer. Quand on
        SAIT que le forfait est vide, on ne veut pas payer cet échec trente
        fois. Ce bouton force le moteur dès le départ, pour toute la file.

        POURQUOI EN POST. Un lien qui change l'état du serveur se déclenche
        tout seul : un navigateur qui pré-charge, un aperçu de lien dans une
        messagerie, un antivirus qui suit les URL. La bascule doit venir d'un
        geste, pas d'une visite.

        Réservé à l'administrateur : c'est un réglage qui engage la dépense de
        toute la maison, pas une préférence personnelle.
        """
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        icp = request.env["ir.config_parameter"].sudo()
        # On n'accepte que des moteurs connus : une valeur libre venue du
        # formulaire finirait dans une commande du serveur.
        #   - « deepseek-agent » = le forgeron. DeepSeek avec des outils : il
        #     ÉCRIT et modifie les fichiers (prouvé le 30/07, 50 essais / 50).
        #   - « opencode » = le moteur sans clé (gratuit), modèles opencode.
        #   - « deepseek » = l'ancien filet. Il répond, il ne construit pas.
        #   - « ollama » = le cerveau local (Malo, le Raspberry) — le filet
        #     qui ne coûte rien, ajouté le 09/08 (Décision #2290).
        valeur = mode if mode in ("deepseek-agent", "deepseek", "opencode",
                                  "ollama") else ""
        icp.set_param("atelier.moteur_force", valeur)
        if valeur == "opencode":
            message = ("Toutes les missions partent maintenant sur opencode, "
                       "le moteur sans clé (modèles gratuits) : rien ne coûte "
                       "de tokens. À basculer quand DeepSeek doit économiser "
                       "son solde.")
            ton = "fait"
        elif valeur == "ollama":
            message = ("Toutes les missions partent maintenant sur Malo (Ollama, "
                       "le Raspberry) : le cerveau local, sans clé ni solde. "
                       "Petit modèle : bon pour analyser, trier, résumer — pas "
                       "pour construire une application. Si le Raspberry est "
                       "éteint, les missions échouent : rebascule d'un clic.")
            ton = "attention"
        elif valeur == "deepseek-agent":
            message = ("Toutes les missions partent maintenant sur DeepSeek-"
                       "agent (le forgeron) : il écrit et modifie les fichiers, "
                       "au prix du solde DeepSeek.")
            ton = "attention"
        elif valeur == "deepseek":
            message = ("Toutes les missions partent sur DeepSeek (répond, ne "
                       "construit pas).")
            ton = "attention"
        else:
            message = ("Les missions repartent sur leur moteur d'origine, avec "
                       "le repli automatique en cas de limite.")
            ton = "fait"
        request.env["tour.signal"].sudo()._signaler(
            "Atelier",
            "Moteur forcé sur « %s »" % valeur if valeur
            else "Retour au moteur normal",
            "<p>%s</p>" % message,
            lien="/tour/dashboard", ton=ton)
        return request.redirect("/tour/dashboard")

    @http.route("/tour/tests", type="http", auth="user", website=False)
    def tests(self, **kw):
        """La page de test : tout ce qui se vérifie, en un endroit, daté.

        Réservée aux administrateurs : elle décrit la mécanique interne
        (épreuves, écarts, cibles), pas le service rendu. Chaque bloc est
        gardé par « in env » — la page vit dans tour_dashboard mais les
        contrôles vivent dans trois modules qui peuvent manquer (une
        instance cliente n'a pas forcément tout).
        """
        env = request.env
        if not env.user.has_group("base.group_system"):
            return request.redirect("/")
        epreuves = env["agent.epreuve"].sudo().search(
            [("active", "=", True)]) if "agent.epreuve" in env else []
        nb_total = len(epreuves)
        nb_ok = len([e for e in epreuves if e.dernier_etat == "ok"])
        ecarts = env["coherence.ecart"].sudo().search(
            [("etat", "=", "ouvert")]) if "coherence.ecart" in env else []
        cibles = env["recette.cible"].sudo().search(
            [("actif", "=", True)]) if "recette.cible" in env else []
        campagnes = env["project.task"].sudo().search(
            [("name", "ilike", "Test complet")],
            order="create_date desc", limit=5)
        return request.render("tour_dashboard.page_tests", {
            "epreuves": epreuves, "nb_total": nb_total, "nb_ok": nb_ok,
            "ecarts": ecarts, "cibles": cibles, "campagnes": campagnes,
        })

    @http.route("/tour/journal", type="http", auth="user", website=False)
    def journal(self, **kw):
        """Le journal de travail de la session — réservé au propriétaire.

        Dans l'édition complète, il lit le journal du serveur. Dans l'édition
        Community, ce bloc est vide (voir plus bas).
        """
        if request.env.user.login.lower() not in _owner_ids():
            return request.redirect("/tour/dashboard")
        # Édition Community : pas de journal serveur accessible ici. Le
        # bloc reste réservé au propriétaire (vide par construction).
        corps = ("<p>Le journal de session n'est pas disponible dans "
                 "l'édition Community.</p>")
        return request.make_response(
            _page_journal(corps),
            headers=[("Content-Type", "text/html; charset=utf-8")])


def _esc(t):
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(t):
    t = _esc(t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    return t


def _md_html(brut):
    """Un Markdown minimal : titres, tableaux,
    listes, code, gras. Volontairement simple — un journal lu est un journal
    fidèle, pas un site."""
    import re
    lignes = brut.replace("\r\n", "\n").split("\n")
    out = []
    i = 0
    en_pre = False
    en_liste = None  # 'ul' ou 'ol'
    while i < len(lignes):
        l = lignes[i]
        # Bloc de code
        if l.strip().startswith("```"):
            if not en_pre:
                out.append("<pre>")
                en_pre = True
            else:
                out.append("</pre>")
                en_pre = False
            i += 1
            continue
        if en_pre:
            out.append(_esc(l))
            i += 1
            continue
        # Tableau
        if l.startswith("|") and i + 1 < len(lignes) and set(
                lignes[i + 1].replace("|", "").replace(":", "").replace("-", "").strip()) == set() \
                and "-" in lignes[i + 1]:
            en_tete = [c.strip() for c in l.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lignes) and lignes[i].startswith("|"):
                rows.append([c.strip() for c in lignes[i].strip("|").split("|")])
                i += 1
            out.append("<table><tr>" + "".join(
                "<th>%s</th>" % _inline(c) for c in en_tete) + "</tr>")
            for r in rows:
                out.append("<tr>" + "".join(
                    "<td>%s</td>" % _inline(c) for c in r) + "</tr>")
            out.append("</table>")
            continue
        # Titres
        m = re.match(r"^(#{1,4})\s+(.*)$", l)
        if m:
            if en_liste:
                out.append("</%s>" % en_liste)
                en_liste = None
            n = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (n + 1, _inline(m.group(2)), n + 1))
            i += 1
            continue
        # Liste
        m = re.match(r"^\s*[-*]\s+(.*)$", l)
        if m:
            if en_liste != "ul":
                if en_liste:
                    out.append("</ul>")
                out.append("<ul>")
                en_liste = "ul"
            out.append("<li>%s</li>" % _inline(m.group(1)))
            i += 1
            continue
        m = re.match(r"^\s*\d+\.\s+(.*)$", l)
        if m:
            if en_liste != "ol":
                if en_liste:
                    out.append("</ol>")
                out.append("<ol>")
                en_liste = "ol"
            out.append("<li>%s</li>" % _inline(m.group(1)))
            i += 1
            continue
        # Séparateur
        if re.match(r"^\s*(---+|\*\*\*+)\s*$", l):
            if en_liste:
                out.append("</%s>" % en_liste)
                en_liste = None
            out.append("<hr/>")
            i += 1
            continue
        # Paragraphe / ligne normale
        if en_liste and not l.strip():
            out.append("</%s>" % en_liste)
            en_liste = None
        elif l.strip():
            out.append("<p>%s</p>" % _inline(l))
        i += 1
    if en_pre:
        out.append("</pre>")
    if en_liste:
        out.append("</%s>" % en_liste)
    return "".join(out)


def _page_journal(corps):
    return """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Journal de travail — Tour de contrôle</title>
<meta name="robots" content="noindex,nofollow"/>
<style>
 :root{--fond:#0a0f1a;--surface:#111a2b;--surface2:#1c2740;--bord:#243149;
       --texte:#e8eef7;--doux:#93a3bb;--accent:#4f8ef7;--r:12px}
 @media (prefers-color-scheme: light){:root{--fond:#f7f9fc;--surface:#fff;
       --surface2:#eef2f8;--bord:#dde4ee;--texte:#0f172a;--doux:#5b6b83}}
 *{box-sizing:border-box}
 body{margin:0;background:var(--fond);color:var(--texte);line-height:1.6;
      font-family:ui-sans-serif,system-ui,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
 a{color:var(--accent);text-decoration:none}
 .wrap{max-width:54rem;margin:0 auto;padding:1.4rem 1.15rem 4rem}
 header{padding-bottom:1rem;border-bottom:1px solid var(--bord);
        margin-bottom:1.2rem;display:flex;gap:1rem;align-items:baseline}
 header h1{font-size:1.15rem;margin:0}
 header a{font-size:.85rem;color:var(--doux)}
 h2{font-size:1.05rem;margin:1.6rem 0 .5rem;color:var(--accent)}
 h3{font-size:.95rem;margin:1.3rem 0 .4rem}
 h4{font-size:.85rem;margin:1.2rem 0 .3rem;color:var(--doux)}
 p{margin:.5rem 0}
 ul,ol{margin:.4rem 0;padding-left:1.25rem}
 li{margin:.25rem 0}
 code{background:var(--surface2);border:1px solid var(--bord);
      border-radius:4px;padding:.05rem .3rem;font-size:.85em}
 pre{background:var(--surface);border:1px solid var(--bord);border-radius:var(--r);
     padding:.8rem;overflow-x:auto;font-size:.82rem;line-height:1.5}
 table{border-collapse:collapse;width:100%%;margin:.6rem 0;font-size:.88rem}
 td,th{border:1px solid var(--bord);padding:.4rem .6rem;text-align:left;vertical-align:top}
 th{background:var(--surface2)}
 hr{border:none;border-top:1px solid var(--bord);margin:1.2rem 0}
 .pied{color:var(--doux);font-size:.8rem;margin-top:2rem}
</style></head><body><div class="wrap">
 <header><h1>Journal de travail</h1>
 <a href="/tour/dashboard">← l'accueil</a></header>
 %(corps)s
 <div class="pied">Réservé au propriétaire — indisponible dans l'édition Community.</div>
 </div></body></html>""" % {"corps": corps}
