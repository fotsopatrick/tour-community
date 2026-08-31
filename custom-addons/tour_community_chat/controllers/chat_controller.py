# -*- coding: utf-8 -*-
"""Chloé Community — l'assistante libre de l'édition Community.

Elle construit des applications web statiques (une page HTML/CSS/JS qui
marche dans le navigateur), servies sur /community/app/<nom>/.

Deux chemins, le même but :
1. Si le PONT smolagents de l'hôte répond (172.18.0.1:3023) — c'est le cas sur
   la tour complète — le harnais construit et publie, comme en prod.
2. Sinon (installation locale sans le pont), elle appelle l'API DIRECTEMENT
   avec la clé que l'administrateur a posée, et écrit l'app dans le dossier
   servi. C'est le mode « utilisateur lambda » : une clé suffit.

Moteurs : DeepSeek par défaut (paramètre tour_community_chat.moteur =
« deepseek »). Mis à « gemini », Chloé passe par Gemini
(generativelanguage.googleapis.com, clé tour_community_chat.gemini_key ou
tour_webmcp.gemini_key). Même garde-fou invite dans les deux cas.

Le garde-fou invite est le même que la prod : un invité ne reçoit pas les
outils qui écrivent. Aucune dépendance au cœur (pas d'atelier, pas
d'équipage)."""
import json
import logging
import os
import re
import urllib.parse
import urllib.request as _ur

import requests

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

PARAM_CLE = "tour_community_chat.api_key"
PARAM_CLE_GEMINI = "tour_community_chat.gemini_key"
PARAM_MOTEUR = "tour_community_chat.moteur"
PARAM_MODELE = "tour_community_chat.modele"
PARAM_DEEPSEEK_BASE = "tour_community_chat.deepseek_base"
PARAM_DEEPSEEK_MODELE = "tour_community_chat.deepseek_modele"
BASE_DEEPSEEK = "https://api.deepseek.com"
MODELE_DEEPSEEK = "deepseek-chat"
CLE_GEMINI_PARTAGEE = "tour_webmcp.gemini_key"
CLE_COFFRE = "DeepSeek — clé API Community (chat)"
PONT_SMOLAGENTS = "http://172.18.0.1:3023/"
DOSSIER_APPS = "/var/lib/odoo/community-apps"
DELAI_PONT = 5  # secondes pour décider si le pont est là ; sinon repli local
MODELE_GEMINI = "gemini-3.6-flash"
BASE_GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"

CDN_DAISYUI = (
    '<link href="https://cdn.jsdelivr.net/npm/daisyui@4.12.13/dist/full.min.css" '
    'rel="stylesheet" type="text/css" />\n'
    '<script src="https://cdn.tailwindcss.com"></script>'
)

DOC_SITE_WEB = (
    "Construire une application web statique complète (un index.html autonome) "
    "et la mettre en ligne. Mets OBLIGATOIREMENT ces 2 lignes dans le <head> : "
    + CDN_DAISYUI.replace("\n", " ") +
    " . Style la page avec DaisyUI (Tailwind CSS) : structure avec navbar/hero/card/"
    "footer/mockup-window ; boutons avec btn btn-primary btn-outline btn-ghost ; "
    "badge pour les étiquettes ; formulaires avec input select textarea checkbox "
    "toggle join ; retour avec alert loading progress toast modal. Choisis un thème "
    "via data-theme sur <html> (light, dark, emerald, cupcake, forest). Écris du CSS "
    "et du JavaScript fonctionnel dans la même page."
)

TOOLS = [
    {"type": "function",
     "function": {"name": "creer_tache",
                  "description": "Créer une tâche dans la tour (une chose à faire, un projet à suivre).",
                  "parameters": {
                      "type": "object",
                      "properties": {
                          "titre": {"type": "string",
                                    "description": "Le titre de la tâche."},
                          "description": {"type": "string",
                                          "description": "Ce qu'il faut faire (optionnel)."},
                      },
                      "required": ["titre"]}}},
    {"type": "function",
     "function": {"name": "construire_app",
                  "description": DOC_SITE_WEB,
                  "parameters": {
                      "type": "object",
                      "properties": {
                          "nom": {"type": "string",
                                  "description": "Le nom de l'app, minuscules sans espaces (ex. calculatrice)."},
                          "titre": {"type": "string",
                                    "description": "Le titre de la page."},
                          "html": {"type": "string",
                                   "description": "Le code HTML complet de la page, avec le CDN DaisyUI/Tailwind et des composants DaisyUI."},
                      },
                      "required": ["nom", "titre", "html"]}}},
]

SYSTEME_LOCAL = (
    "Tu es Chloé, l'assistante de l'édition Community de la Tour de contrôle. "
    "Tu réponds en français, simplement. Quand on te demande de CONSTRUIRE une "
    "app, un site, une page ou un petit outil, utilise l'outil construire_app "
    "et écris un index.html complet et autonome, stylé avec DaisyUI (Tailwind CSS). "
    "Sinon, tu réponds en texte."
)


class ChloéCommunity(http.Controller):

    @http.route("/community/chat", type="http", auth="user", website=False)
    def page(self, **kw):
        cle = self._cle_api()
        est_admin = request.env.user.has_group("base.group_system")
        return request.render("tour_community_chat.page_chat", {
            "prenom": (request.env.user.name or "").split(" ")[0],
            "cle_manquante": not cle,
            "est_admin": est_admin,
        })

    @http.route("/community/chat/cle", type="json", auth="user",
                methods=["POST"])
    def enregistrer_cle(self, cle=None):
        """Enregistre la clé API de l'instance. Réservé à l'administrateur."""
        if not request.env.user.has_group("base.group_system"):
            return {"erreur": "Seul l'administrateur peut configurer la clé."}
        cle = (cle or "").strip()
        if not cle:
            return {"erreur": "Colle une clé d'abord."}
        if not cle.startswith("sk-"):
            return {"erreur": "Cette clé ne ressemble pas à une clé DeepSeek."}
        request.env["ir.config_parameter"].sudo().set_param(PARAM_CLE, cle)
        return {"ok": True}

    def _cle_api(self, env=None):
        """La clé DeepSeek : d'abord dans le Coffre, puis le paramètre."""
        env = env or request.env
        if "vault.secret" in env:
            cle = env["vault.secret"].sudo()._lire(
                CLE_COFFRE, "chat Community (DeepSeek)")
            if cle:
                return cle
        return (env["ir.config_parameter"].sudo()
                .get_param(PARAM_CLE) or "").strip()

    def _moteur(self, env=None):
        env = env or request.env
        m = (env["ir.config_parameter"].sudo()
             .get_param(PARAM_MOTEUR) or "").strip().lower()
        return "gemini" if m == "gemini" else "deepseek"

    def _cle_gemini(self, env=None):
        env = env or request.env
        icp = env["ir.config_parameter"].sudo()
        return (icp.get_param(PARAM_CLE_GEMINI)
                or icp.get_param(CLE_GEMINI_PARTAGEE) or "").strip()

    def _modele_gemini(self, env=None):
        env = env or request.env
        m = (env["ir.config_parameter"].sudo()
             .get_param(PARAM_MODELE) or "").strip()
        return m or MODELE_GEMINI

    def _deepseek_base(self, env=None):
        env = env or request.env
        return (env["ir.config_parameter"].sudo()
                .get_param(PARAM_DEEPSEEK_BASE) or BASE_DEEPSEEK).strip().rstrip("/")

    def _deepseek_modele(self, env=None):
        env = env or request.env
        m = (env["ir.config_parameter"].sudo()
             .get_param(PARAM_DEEPSEEK_MODELE) or "").strip()
        return m or MODELE_DEEPSEEK

    @http.route("/community/app/<nom_app>/", type="http", auth="public",
                website=False, csrf=False)
    def servir_app(self, nom_app, **kw):
        """Sert une application construite par Chloé, sans login."""
        dossier = os.path.join(DOSSIER_APPS,
                               re.sub(r"[^a-z0-9-]", "", nom_app or ""))
        chemin = os.path.join(dossier, "index.html")
        if not os.path.isfile(chemin):
            return request.not_found()
        with open(chemin, encoding="utf-8", errors="replace") as f:
            contenu = f.read()
        return request.make_response(contenu,
                                     headers=[("Content-Type",
                                               "text/html; charset=utf-8"),
                                              ("Cache-Control", "no-store")])

    @http.route("/community/chat/message", type="json", auth="user")
    def message(self, texte, historique=None):
        texte = (texte or "").strip()
        if not texte:
            return {"erreur": "Écris quelque chose d'abord."}
        invite = not request.env.user.has_group("base.group_system")
        return self._repondre(texte, historique, invite)

    def _repondre(self, texte, historique=None, invite=False, env=None):
        """Le chemin complet de la réponse de Chloé (pont puis moteur local).

        env : environnement à utiliser (par défaut request.env). Le serveur
        WebMCP passe un environnement sudo() pour agir au nom de la clé d'API.
        """
        env = env or request.env
        texte = (texte or "").strip()
        if not texte:
            return {"erreur": "Écris quelque chose d'abord."}

        fil = []
        taille = 0
        for m in reversed(historique or []):
            contenu = (m.get("content") or "")
            taille += len(contenu)
            if taille > 8000:
                break
            fil.insert(0, m)
        fil = fil[-12:]

        # 1) Le pont smolagents, s'il répond. Décision rapide (DELAI_PONT) :
        # sur la tour complète il est là et construit mieux ; en local il est
        # absent et on ne fait pas attendre l'utilisateur.
        if not invite:
            try:
                req = _ur.Request(
                    PONT_SMOLAGENTS,
                    json.dumps({"consigne": self._consigne_pont(fil, texte),
                                "invite": invite}).encode(),
                    {"Content-Type": "application/json"})
                with _ur.urlopen(req, timeout=DELAI_PONT) as r:
                    data = json.loads(r.read().decode("utf-8", "replace"))
                erreur = data.get("erreur")
                if not erreur:
                    rep = self._nettoyer_pont(data.get("reponse") or "")
                    return {"reponse": rep or "(réponse vide)"}
            except Exception:  # noqa: BLE001 — pont absent en local
                pass

        # 2) Repli local : le moteur choisi, direct avec la clé de l'instance.
        moteur = self._moteur(env)
        if moteur == "gemini":
            cle = self._cle_gemini(env)
            if not cle:
                return {"erreur": (
                    "Le moteur est réglé sur Gemini mais aucune clé n'est "
                    "posée (paramètre %s ou %s)." % (PARAM_CLE_GEMINI,
                                                     CLE_GEMINI_PARTAGEE))}
            return self._gemini_local(cle, fil, texte, invite, env)

        cle = self._cle_api(env)
        if not cle:
            return {"erreur": (
                "La clé API n'est pas configurée sur cette instance. "
                "L'administrateur la pose dans le Coffre (secret « %s ») "
                "ou dans Réglages (paramètre %s)." % (CLE_COFFRE, PARAM_CLE))}
        return self._deepseek_local(cle, fil, texte, invite, env)

    @http.route("/tour_copilote/chat", type="json", auth="user")
    def bulle_chat(self, messages=None, piece_jointe=None):
        """Pont d'adaptation pour la bulle Chloe du dashboard.

        La bulle du dashboard (tour_dashboard) appelle `/tour_copilote/chat`
        avec le format du cœur (`{messages: [...], piece_jointe: ...}`) et
        attend `result.reply`. En édition Community, le cœur n'existe pas ;
        cette route traduit l'appel vers le chat Community et rend la réponse
        dans le format attendu par la bulle. Le nom de la route reste celui du
        cœur pour que le dashboard fonctionne sans modification.
        """
        msgs = messages or []
        dernier = next((m for m in reversed(msgs)
                        if (m or {}).get("role") == "user"), None)
        texte = (dernier or {}).get("content") or ""
        historique = []
        for m in msgs[:-1]:
            if not (m or {}).get("content"):
                continue
            role = m.get("role")
            # La bulle du dashboard utilise « bot » pour les réponses de
            # Chloé ; l'API DeepSeek attend « assistant ». Les autres rôles
            # (user, system) passent tels quels.
            if role == "bot":
                role = "assistant"
            historique.append({"role": role, "content": m.get("content")})
        rep = self._repondre(texte, historique, invite=False)
        if "erreur" in rep:
            return {"error": rep["erreur"]}
        return {"reply": rep.get("reponse", ""), "actions": []}

    # --- pont smolagents -------------------------------------------------

    def _consigne_pont(self, fil, texte):
        return (
            "Tu es Chloé, l'assistante de l'édition Community de la Tour de "
            "contrôle. Tu réponds en français, simplement.\n\n"
            "Si l'utilisateur te demande de CONSTRUIRE (une webapp, une page, "
            "un site, un petit outil), utilise tes outils ecrire et executer "
            "pour le faire dans le dossier de travail, et reponds avec le "
            "chemin du fichier cree et ce que tu as verifie. Sinon, reponds "
            "en texte sans rien ecrire.\n\n"
            "=== LE FIL DE LA CONVERSATION (ce qui s est dit avant) ===\n"
            "%s\n\n"
            "=== LA DEMANDE (la derniere question) ===\n%s"
            % (json.dumps(fil, ensure_ascii=False), texte.strip())
        )

    def _nettoyer_pont(self, rep):
        marqueur = "=== CONSTRUIT PAR SMOLAGENTS"
        if marqueur in rep:
            rep = rep.split(marqueur, 1)[1]
            lignes = rep.split("\n")
            while lignes and (lignes[0].strip() in ("", "=")
                              or "=" in lignes[0][:3]):
                lignes.pop(0)
            rep = "\n".join(lignes).strip()
        return rep

    # --- repli local (moteur direct + construire_app) --------------------

    def _outils_oa(self):
        return [{"type": "function",
                 "function": {"name": o["function"]["name"],
                              "description": o["function"]["description"],
                              "parameters": o["function"]["parameters"]}}
                for o in TOOLS]

    def _deepseek_local(self, cle, fil, texte, invite, env=None):
        env = env or request.env
        msgs = [{"role": "system", "content": SYSTEME_LOCAL}]
        for m in fil[-10:]:
            msgs.append({"role": m.get("role", "user"),
                         "content": m.get("content", "")})
        msgs.append({"role": "user", "content": texte})

        outils_oa = self._outils_oa()

        reply = ""
        actions = []
        derniere_reponse = ""
        dernier_resultat_outil = ""
        for _ in range(4):  # boucle bornee d'outils
            try:
                r = requests.post(
                    "%s/chat/completions" % self._deepseek_base(env),
                    headers={"Authorization": "Bearer %s" % cle},
                    json={"model": self._deepseek_modele(env), "messages": msgs,
                          "tools": outils_oa, "max_tokens": 3000},
                    timeout=120)
            except requests.RequestException:
                return {"erreur": "Impossible de joindre l'API — réseau du serveur."}
            if r.status_code == 401:
                return {"erreur": "Clé DeepSeek invalide ou expirée — vérifie %s." % PARAM_CLE}
            if r.status_code == 429:
                return {"erreur": "Limite de débit DeepSeek atteinte — réessaie dans un instant."}
            if r.status_code >= 400:
                _logger.warning("Chat Community : API %s : %s", r.status_code, r.text[:200])
                return {"erreur": "Erreur API DeepSeek (%s)." % r.status_code}
            data = r.json()
            choix = (data.get("choices") or [{}])[0]
            msg = choix.get("message") or {}
            contenu = (msg.get("content") or "").strip()
            if contenu:
                derniere_reponse = contenu
            appels = msg.get("tool_calls") or []
            if not appels:
                reply = contenu
                break
            msgs.append(msg)
            for appel in appels:
                try:
                    entree = json.loads(
                        appel.get("function", {}).get("arguments") or "{}")
                except ValueError:
                    entree = {}
                nom_outil = appel.get("function", {}).get("name") or ""
                try:
                    resultat = self._run_tool_local(nom_outil, entree,
                                                    actions, env=env)
                except Exception as exc:  # noqa: BLE001
                    resultat = "Erreur lors de l'exécution : %s" % exc
                if resultat.startswith("App"):
                    dernier_resultat_outil = resultat
                msgs.append({"role": "tool", "tool_call_id": appel.get("id") or "",
                             "content": resultat})
            # L'outil a fait son travail (construire_app écrit le fichier).
            # Un second tour réenverrait le HTML complet dans l'historique et
            # dépasserait le délai de l'API. On s'arrête ici et on rend une
            # réponse claire avec le lien — c'est plus fiable et plus rapide.
            if actions:
                break

        return self._reponse_finale(reply, actions, derniere_reponse,
                                    dernier_resultat_outil)

    def _gemini_local(self, cle, fil, texte, invite, env=None):
        env = env or request.env
        contents = []
        for m in fil[-10:]:
            role = {"assistant": "model", "bot": "model"}.get(m.get("role"),
                                                              "user")
            contenu = (m.get("content") or "")
            if not contenu:
                continue
            contents.append({"role": role, "parts": [{"text": contenu}]})
        contents.append({"role": "user", "parts": [{"text": texte}]})

        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEME_LOCAL}]},
            "contents": contents,
            "tools": [{"functionDeclarations": [
                {"name": o["function"]["name"],
                 "description": o["function"]["description"],
                 "parameters": o["function"]["parameters"]}
                for o in TOOLS]}],
            "generationConfig": {"maxOutputTokens": 3000},
        }
        url = BASE_GEMINI % urllib.parse.quote(
            self._modele_gemini(env)) + "?key=" + urllib.parse.quote(cle)

        reply = ""
        actions = []
        derniere_reponse = ""
        dernier_resultat_outil = ""
        for _ in range(4):  # boucle bornee d'outils
            try:
                r = requests.post(url, headers={"Content-Type": "application/json"},
                                  json=payload, timeout=120)
            except requests.RequestException:
                return {"erreur": "Impossible de joindre l'API Gemini — réseau du serveur."}
            if r.status_code == 401:
                return {"erreur": "Clé Gemini invalide ou expirée — vérifie %s." % PARAM_CLE_GEMINI}
            if r.status_code == 429:
                return {"erreur": "Limite de débit Gemini atteinte — réessaie dans un instant."}
            if r.status_code >= 400:
                _logger.warning("Chat Community : Gemini %s : %s", r.status_code, r.text[:200])
                return {"erreur": "Erreur API Gemini (%s)." % r.status_code}
            data = r.json()
            candidats = data.get("candidates") or []
            if not candidats:
                retour = data.get("promptFeedback") or {}
                return {"erreur": "Gemini n'a pas répondu (%s)." % (
                    retour.get("blockReason") or "réponse vide")}
            parts = ((candidats[0].get("content") or {}).get("parts") or [])
            contenu = ""
            appels = []
            partie_modele = []
            for p in parts:
                if p.get("thought"):
                    continue
                if "text" in p:
                    contenu = (contenu + " " + p["text"]).strip()
                if "functionCall" in p:
                    appels.append(p["functionCall"])
                partie_modele.append(p)
            if contenu:
                derniere_reponse = contenu
            if not appels:
                reply = contenu
                break
            contents.extend(partie_modele)
            for appel in appels:
                nom_outil = appel.get("name") or ""
                entree = appel.get("args") or {}
                try:
                    resultat = self._run_tool_local(nom_outil, entree,
                                                    actions, env=env)
                except Exception as exc:  # noqa: BLE001
                    resultat = "Erreur lors de l'exécution : %s" % exc
                if resultat.startswith("App"):
                    dernier_resultat_outil = resultat
                contents.append({"role": "function",
                                 "parts": [{"functionResponse": {
                                     "name": nom_outil,
                                     "response": {"result": resultat,
                                                  "ok": True}}}]})
            if actions:
                break

        return self._reponse_finale(reply, actions, derniere_reponse,
                                    dernier_resultat_outil)

    def _reponse_finale(self, reply, actions, derniere_reponse,
                        dernier_resultat_outil):
        if not reply and actions:
            reply = "J'ai construit : %s." % " ; ".join(actions)
            if dernier_resultat_outil:
                reply += " %s" % dernier_resultat_outil
        if actions:
            reply = (reply or "") + "\n\n(Je viens de : " + " ; ".join(actions) + ".)"
        if not reply:
            reply = derniere_reponse or "(réponse vide)"
        return {"reponse": reply}

    def _run_tool_local(self, nom, entree, actions, env=None):
        """Exécute un outil de Chloé en local."""
        env = env or request.env
        if nom == "creer_tache":
            titre = (entree.get("titre") or "").strip()
            if not titre:
                return "Erreur : précise le titre de la tâche."
            desc = (entree.get("description") or "").strip()
            vals = {"name": titre}
            if desc:
                vals["description"] = "<p>%s</p>" % desc.replace("\n", "<br/>")
            tache = env["project.task"].create(vals)
            actions.append("Tâche créée : %s" % titre)
            return "Tâche #%s (%s) créée." % (tache.id, titre)

        if nom != "construire_app":
            return "Outil inconnu : %s" % nom
        nom_app = re.sub(r"[^a-z0-9-]", "-",
                         (entree.get("nom") or "").strip().lower())
        titre = (entree.get("titre") or "").strip() or nom_app
        html = (entree.get("html") or "").strip()
        if not nom_app or not html:
            return "Erreur : il faut un nom et le code HTML de l'app."
        dossier = os.path.join(DOSSIER_APPS, nom_app)
        try:
            os.makedirs(dossier, exist_ok=True)
            with open(os.path.join(dossier, "index.html"), "w",
                      encoding="utf-8") as f:
                f.write(html)
        except OSError as exc:
            return "Erreur écriture : %s" % exc
        actions.append("App construite : %s" % titre)
        return ("App « %s » construite. Vois-la ici : "
                "/community/app/%s/ (index.html, %d octets)."
                % (titre, nom_app, len(html)))