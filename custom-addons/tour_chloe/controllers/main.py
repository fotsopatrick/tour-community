# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

from odoo.addons.tour_copilote.controllers.main import (
    executer_chat, _TourCopiloteCoeur)

_logger = logging.getLogger(__name__)

ETATS_MISSION = {
    "brouillon": "Brouillon",
    "envoyee": "Envoyée",
    "en_cours": "En cours",
    "terminee": "Terminée",
    "echec": "Échec",
}


class ChloeWebapp(http.Controller):
    """Webapp Chloe : onglets de chat a gauche, chat au centre, etapes a droite.

    Le moteur est EXACTEMENT celui du copilote (executer_chat) : meme Chloé,
    memes outils, memes gardes. On ne touche pas au copilote existant, on
    ajoute une page neuve.
    """

    def _conversation(self, conv_id):
        conv = request.env["chloe.conversation"].search(
            [("id", "=", conv_id), ("user_id", "=", request.env.user.id)],
            limit=1)
        if conv:
            return conv
        # Onglet inconnu ou d'un autre compte : on cree une conversation propre.
        return request.env["chloe.conversation"].create({
            "name": "Nouvelle conversation",
        })

    def _messages(self, conv):
        try:
            donnees = json.loads(conv.messages or "[]")
            return donnees if isinstance(donnees, list) else []
        except Exception:
            return []

    def _etapes(self):
        """Les missions du compte courant et leurs etapes cochees en direct."""
        env = request.env
        missions = env["atelier.mission"].search(
            [("create_uid", "=", env.user.id)],
            order="create_date desc", limit=8)
        resultat = []
        for m in missions:
            resultat.append({
                "id": m.id,
                "nom": m.name,
                "etat": m.etat or "",
                "etat_label": ETATS_MISSION.get(m.etat, m.etat or ""),
                "etapes": [{
                    "nom": e.nom,
                    "etat": e.etat,
                    "detail": e.detail or "",
                } for e in m.etape_ids],
            })
        return resultat

    @http.route("/tour/chloe", type="http", auth="user", website=False)
    def page(self, **kw):
        return request.render("tour_chloe.page", {})

    @http.route("/tour_chloe/liste", type="json", auth="user", csrf=False)
    def liste(self):
        convs = request.env["chloe.conversation"].search(
            [("user_id", "=", request.env.user.id)],
            order="write_date desc", limit=40)
        return [{"id": c.id, "name": c.name} for c in convs]

    @http.route("/tour_chloe/nouveau", type="json", auth="user", csrf=False)
    def nouveau(self):
        conv = request.env["chloe.conversation"].create({
            "name": "Nouvelle conversation",
        })
        return {"id": conv.id, "name": conv.name}

    @http.route("/tour_chloe/ouvrir", type="json", auth="user", csrf=False)
    def ouvrir(self, conv_id=0):
        conv = self._conversation(int(conv_id or 0))
        return {
            "id": conv.id,
            "name": conv.name,
            "messages": self._messages(conv),
            "etapes": self._etapes(),
        }

    @http.route("/tour_chloe/renommer", type="json", auth="user", csrf=False)
    def renommer(self, conv_id, name):
        conv = self._conversation(int(conv_id or 0))
        nom = (name or "").strip()
        if nom:
            conv.write({"name": nom[:120]})
        return {"id": conv.id, "name": conv.name}

    @http.route("/tour_chloe/envoyer", type="json", auth="user", csrf=False)
    def envoyer(self, conv_id, message):
        conv = self._conversation(int(conv_id or 0))
        texte = (message or "").strip()
        if not texte:
            return {"error": "Message vide."}

        messages = self._messages(conv)
        if conv.name == "Nouvelle conversation":
            conv.write({"name": texte[:60] or "Conversation"})

        messages.append({"role": "user", "content": texte})
        try:
            resultat = executer_chat(request.env, messages)
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Chloe webapp : executer_chat a echoue")
            resultat = {"error": "Chloe n'a pas repondu : %s" % exc}

        if isinstance(resultat, dict) and resultat.get("error"):
            reply = "Erreur : %s" % resultat["error"]
            messages.append({"role": "assistant", "content": reply})
            conv.write({"messages": json.dumps(messages, ensure_ascii=False)})
            return {
                "reply": reply,
                "messages": messages,
                "etapes": self._etapes(),
            }

        # ASYNCHRONE (correctif 14/08). Le moteur smolagents ne repond pas
        # dans l'appel : il rend un jeton, et la vraie reponse se releve
        # ensuite sur /tour_chloe/resultat. Avant ce correctif, la webapp
        # ecrivait l'accuse de reception (« La reponse arrive dans un
        # instant ») EN BASE comme etant la reponse de Chloe, et ne relevait
        # jamais le jeton : l'utilisateur n'a jamais eu de reponse, sur aucune
        # conversation, depuis le passage en async du 10/08. La bulle de
        # l'accueil (chloe-bulle.js) releve, elle ; c'est pour ca qu'elle
        # marchait et pas cette page.
        jeton = (resultat or {}).get("jeton")
        if jeton and (resultat or {}).get("async"):
            # On ne persiste QUE la question. La reponse sera ecrite par
            # /tour_chloe/resultat quand le harnais aura fini.
            conv.write({"messages": json.dumps(messages, ensure_ascii=False)})
            return {
                "async": True,
                "jeton": jeton,
                "attente": (resultat or {}).get("reply")
                or "Je m'en occupe...",
                "messages": messages,
                "etapes": self._etapes(),
            }

        reply = (resultat or {}).get("reply", "")
        messages.append({"role": "assistant", "content": reply})
        conv.write({"messages": json.dumps(messages, ensure_ascii=False)})
        return {
            "reply": reply,
            "messages": messages,
            "etapes": self._etapes(),
        }

    @http.route("/tour_chloe/resultat", type="json", auth="user", csrf=False)
    def resultat(self, conv_id, jeton):
        """Releve la vraie reponse d'un jeton async et l'ecrit dans le fil.

        Rend {"etat": "envoye"} tant que le harnais travaille, puis
        {"etat": "termine", "reply": ..., "messages": [...]} une fois la
        reponse ecrite en base. Le meme coeur que /tour_copilote/resultat
        est reutilise — on ne duplique pas le moteur.
        """
        conv = self._conversation(int(conv_id or 0))
        coeur = _TourCopiloteCoeur()
        try:
            etat, reponse, erreur = coeur._relever_smolagents(jeton)
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Chloe webapp : relevage du jeton a echoue")
            return {"etat": "echec", "erreur": str(exc)}

        if etat == "envoye":
            return {"etat": "envoye"}

        if etat == "termine":
            actions = []
            texte = coeur._nettoyer_reponse_smolagents(
                reponse or "(reponse vide)", actions)
            fini = "termine"
        else:
            texte = ("Chloe n'a pas pu repondre : %s"
                     % (erreur or "reponse non prete"))
            fini = "echec"

        # Idempotent : si la reponse a deja ete ecrite (double relevage,
        # onglet rouvert), on ne l'empile pas une seconde fois.
        messages = self._messages(conv)
        if not (messages and messages[-1].get("role") == "assistant"):
            messages.append({"role": "assistant", "content": texte})
            conv.write({"messages": json.dumps(messages, ensure_ascii=False)})

        return {
            "etat": fini,
            "reply": texte,
            "messages": messages,
            "etapes": self._etapes(),
        }
