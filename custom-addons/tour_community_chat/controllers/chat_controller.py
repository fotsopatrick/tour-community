# -*- coding: utf-8 -*-
"""Chloé Community — l'assistante libre de l'édition Community.

Elle construit des applications web statiques (une page HTML/CSS/JS qui
marche dans le navigateur), servies sur /community/app/<nom>/.

Deux chemins, le même but :
1. Si le PONT smolagents de l'hôte répond (172.18.0.1:3023) — c'est le cas sur
   la tour complète — le harnais construit et publie, comme en prod.
2. Sinon (installation locale sans le pont), elle appelle DeepSeek DIRECTEMENT
   avec la clé que l'administrateur a posée, et écrit l'app dans le dossier
   servi. C'est le mode « utilisateur lambda » : une clé suffit.

Le garde-fou invite est le même que la prod : un invité ne reçoit pas les
outils qui écrivent. Aucune dépendance au cœur (pas d'atelier, pas
d'équipage)."""
import json
import logging
import os
import re
import urllib.request as _ur

import requests

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

PARAM_CLE = "tour_community_chat.api_key"
CLE_COFFRE = "DeepSeek — clé API Community (chat)"
PONT_SMOLAGENTS = "http://172.18.0.1:3023/"
DOSSIER_APPS = "/var/lib/odoo/community-apps"
DELAI_PONT = 5  # secondes pour décider si le pont est là ; sinon repli local

TOOLS = [
    {"type": "function",
     "function": {"name": "construire_app",
                  "description": "Construire une petite application web statique (une page HTML/CSS/JS) et la mettre en ligne. À utiliser quand on demande de créer un site, une app, une page, un formulaire, un petit outil. Écris un index.html complet et autonome (tout le CSS et le JS dedans).",
                  "parameters": {
                      "type": "object",
                      "properties": {
                          "nom": {"type": "string",
                                  "description": "Le nom de l'app, minuscules sans espaces (ex. calculatrice)."},
                          "titre": {"type": "string",
                                    "description": "Le titre de la page."},
                          "html": {"type": "string",
                                   "description": "Le code HTML complet de la page."},
                      },
                      "required": ["nom", "titre", "html"]}}},
]

SYSTEME_LOCAL = (
    "Tu es Chloé, l'assistante de l'édition Community de la Tour de contrôle. "
    "Tu réponds en français, simplement. Quand on te demande de CONSTRUIRE une "
    "app, un site, une page ou un petit outil, utilise l'outil construire_app "
    "et écris un index.html complet et autonome. Sinon, tu réponds en texte."
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

    def _cle_api(self):
        """La clé DeepSeek : d'abord dans le Coffre, puis le paramètre."""
        if "vault.secret" in request.env:
            cle = request.env["vault.secret"].sudo()._lire(
                CLE_COFFRE, "chat Community (DeepSeek)")
            if cle:
                return cle
        return (request.env["ir.config_parameter"].sudo()
                .get_param(PARAM_CLE) or "").strip()

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

        # 2) Repli local : DeepSeek direct avec la clé de l'instance.
        cle = self._cle_api()
        if not cle:
            return {"erreur": (
                "La clé API n'est pas configurée sur cette instance. "
                "L'administrateur la pose dans le Coffre (secret « %s ») "
                "ou dans Réglages (paramètre %s)." % (CLE_COFFRE, PARAM_CLE))}
        return self._deepseek_local(cle, fil, texte, invite)

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
        rep = self.message(texte=texte, historique=historique)
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

    # --- repli local (DeepSeek direct + construire_app) ------------------

    def _deepseek_local(self, cle, fil, texte, invite):
        msgs = [{"role": "system", "content": SYSTEME_LOCAL}]
        for m in fil[-10:]:
            msgs.append({"role": m.get("role", "user"),
                         "content": m.get("content", "")})
        msgs.append({"role": "user", "content": texte})

        outils_oa = [{"type": "function",
                      "function": {"name": o["function"]["name"],
                                   "description": o["function"]["description"],
                                   "parameters": o["function"]["parameters"]}}
                     for o in TOOLS]

        reply = ""
        actions = []
        derniere_reponse = ""
        dernier_resultat_outil = ""
        for _ in range(4):  # boucle bornee d'outils
            try:
                r = requests.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={"Authorization": "Bearer %s" % cle},
                    json={"model": "deepseek-chat", "messages": msgs,
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
                    resultat = self._run_tool_local(nom_outil, entree, actions)
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

        if not reply and actions:
            reply = "J'ai construit : %s." % " ; ".join(actions)
            if dernier_resultat_outil:
                reply += " %s" % dernier_resultat_outil
        if actions:
            reply = (reply or "") + "\n\n(Je viens de : " + " ; ".join(actions) + ".)"
        if not reply:
            reply = derniere_reponse or "(réponse vide)"
        return {"reponse": reply}

    def _run_tool_local(self, nom, entree, actions):
        """Exécute l'outil construire_app en local : écrit le fichier servi."""
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
