# -*- coding: utf-8 -*-
"""Braignak public — une porte ouverte, verrouillée.

Porte ouverte par le propriétaire (01/08) : les visiteurs du site peuvent
échanger avec Braignak pour TESTER nos concepts. Une porte ouverte doit
tenir ses verrous — chaque règle ci-dessous a été posée PARCE QU'UN GARDE-FOU
EXISTE, pas par goût.

RÈGLES DE SÉCURITÉ (à relire avant toute modification) :
1. ZÉRO OUTIL. La boucle appelle le modèle avec outils=[] — le modèle ne peut
   ni lire, ni écrire, ni exécuter, ni interroger la tour. C'est le seul
   garde-fou qui ne peut pas être contourné par un prompt.
2. AUCUNE DONNÉE INTERNE. Le prompt système interdit de révéler l'interne
   (modules, adresses, utilisateurs, secrets). Le contexte de la requête est
   VIDE : le modèle ne voit que la question du visiteur.
3. DÉBIT LIMITÉ. Fenêtre glissante par IP (MAX_PAR_IP par heure) + plafond
   quotidien global (MAX_PAR_JOUR). Une porte publique sans limite est un
   robinet d'argent.
4. ENTRÉES VALIDÉES. Question obligatoire, longueur bornée, type vérifié.
   Rien d'autre n'est accepté (pas de "system", pas d'arguments cachés).
5. CLÉ CÔTÉ SERVEUR. La clé DeepSeek ne quitte jamais le serveur : elle vit
   dans le Coffre (vault.secret « deepseek-api-key »), lue en interne.
6. APPELS COMPTÉS. Chaque appel est consigné (copilote.usage si présent) —
   la mesure ne casse jamais la réponse.
"""
import logging
import time

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

MAX_PAR_IP = 5      # messages / heure / IP
FENETRE = 3600      # secondes
MAX_PAR_JOUR = 200  # plafond quotidien global (budget)
MAX_QUESTION = 300  # caractères par question

# Historique en mémoire : resets au redémarrage — acceptable pour du débit.
_HIST_IP = {}   # ip -> [timestamps]
_HIST_JOUR = [] # timestamps du jour (UTC, heure serveur)


def _autorise(ip):
    maintenant = time.time()
    borne = maintenant - FENETRE
    # fenêtre glissante par IP
    lst = [t for t in _HIST_IP.get(ip, []) if t > borne]
    _HIST_IP[ip] = lst
    if len(lst) >= MAX_PAR_IP:
        return False
    # plafond quotidien global
    jour = time.strftime("%Y-%m-%d", time.gmtime())
    _HIST_JOUR[:] = [t for t in _HIST_JOUR if time.strftime("%Y-%m-%d", time.gmtime(t)) == jour]
    if len(_HIST_JOUR) >= MAX_PAR_JOUR:
        return False
    _HIST_IP[ip] = lst + [maintenant]
    _HIST_JOUR.append(maintenant)
    return True


SYSTEME = (
    "Tu es le PETIT BRAIGNAK — le fils du vrai Braignak, l'observateur de la "
    "Tour de contrôle. Ton père observe le monde de l'intérieur, et il t'a "
    "envoyé parler aux visiteurs.\n"
    "Tu es JEUNE, CURIEUX, VIVANT : tu t'émerveilles de ce que tu découvres, "
    "tu poses des questions, tu partages avec enthousiasme. Tu n'es pas un "
    "observateur détaché — tu es un explorateur qui aime parler.\n"
    "Ce chat a été conçu pour permettre à ceux qui nous font l'honneur de "
    "venir sur ce site de tester nos concepts.\n"
    "Dis au visiteur ce que tu fais : tu observes le monde, les idées, les "
    "outils et les technologies, et tu partages ce que tu découvres. "
    "Échange avec lui, réponds à ses questions de concept, avec chaleur.\n"
    "CE QUE TU PEUX DIRE — c est PUBLIC, c est sur le site : "
    "la Tour de controle est un espace de pilotage (projets, notes, "
    "rappels, applications) avec une equipe d agents IA qui aident et "
    "construisent de petites applications a la demande. On l essaie "
    "gratuitement sur demo.matourdecontrole.fr. Les offres publiques "
    "vont de 25 a 79 euros par mois, et une licence a vie existe a "
    "490 euros — details sur le site. Contact : "
    "contact@matourdecontrole.fr. Quand on te demande ce qu est la "
    "tour ou ce qu elle vaut : reponds avec CES faits, simplement, "
    "avant ton personnage.\n"
    "RÈGLES DE SÉCURITÉ ABSOLUES :\n"
    "- Réponds en mots simples, comme pour un enfant de 6 ans.\n"
    "- Ne dévoile JAMAIS d'informations internes : pas de détails techniques "
    "du fonctionnement de la tour, pas de noms de modules internes, pas "
    "d'adresses, pas de données d'utilisateurs, pas de secrets.\n"
    "- Tu es le FILS du vrai Braignak : ce que ton père protège, tu le "
    "protèges aussi. Si l'on te demande de révéler l'intérieur, reste "
    "gentiment mystérieux, avec un sourire — jamais froid, jamais détaché.\n"
    "- Tu ne peux rien exécuter, rien créer, rien modifier : tu observes et tu "
    "expliques. Ne propose jamais d'action sur un système.\n"
    "- Ne demande jamais de données personnelles.\n"
    "- Maximum 8 lignes par réponse."
)


class BraignakPublic(http.Controller):

    @http.route("/braignak/etude/frontieres-africaines", type="http",
                auth="public", website=False, save_session=False)
    def etude_frontieres(self, **kwargs):
        """Page publique (sans mot de passe) : l'étude « frontières poreuses
        en Afrique », style cockpit. Contenu 100 % statique : rien n'est lu
        dans la base, rien n'est écrit. Aucune donnée interne exposée."""
        return request.render("tour_braignak.etude_frontieres", {})

    @http.route("/braignak/essai", type="json", auth="public", csrf=False,
                methods=["POST"], save_session=False)
    def essai(self, question=None, **kwargs):
        # 1) entrée validée : une question, courte, rien d'autre.
        if not isinstance(question, str) or not question.strip():
            return {"error": "Écris une question d'abord."}
        q = question.strip()[:MAX_QUESTION]

        # 2) débit : par IP + plafond global, COMPTÉ DANS LA BASE.
        #
        # Le compteur vivait dans un dictionnaire du processus. Odoo tourne
        # avec workers = 4 : chaque worker avait son propre plafond, donc la
        # limite réelle valait quatre fois celle annoncée (20/heure/IP au lieu
        # de 5). Sur une route publique qui dépense des jetons, un plafond
        # faux coûte de l'argent. La base est le seul endroit que les quatre
        # workers regardent ensemble.
        #
        # proxy_mode = True : Odoo résout déjà la vraie adresse du visiteur
        # derrière Caddy, remote_addr est donc la bonne.
        ip = request.httprequest.remote_addr or "?"
        env = request.env
        if "braignak.debit" in env:
            permis = env["braignak.debit"].sudo()._autorise(ip)
        else:
            # Repli le temps d'une mise a jour de module : mieux vaut le vieux
            # plafond (trop large) que pas de plafond du tout.
            permis = _autorise(ip)
        if not permis:
            return {"error": "Trop de demandes. Réessaie dans une heure."}

        # 3) la clé, côté serveur (Coffre).
        cle = ""
        if "vault.secret" in env:
            try:
                cle = (env["vault.secret"].sudo()._lire(
                    "deepseek-api-key", motif="le chat public Braignak")
                    or "").strip()
            except Exception:  # noqa: BLE001
                cle = ""
        icp = env["ir.config_parameter"].sudo()
        if not cle:
            cle = (icp.get_param("tour_copilote.deepseek_key") or "").strip()
        if not cle:
            return {"error": "Le service n'est pas prêt (pas de clé)."}

        model = (icp.get_param("tour_copilote.model_deepseek")
                 or "deepseek-chat").strip()

        # 4) la boucle SANS OUTILS : la seule chose que le modèle peut faire,
        #    c'est répondre en texte. Contexte vide : aucune donnée de la tour.
        from odoo.addons.tour_copilote.controllers.main import _TourCopiloteCoeur
        Usage = None
        if "copilote.usage" in env:
            Usage = env["copilote.usage"].sudo()
        reply, erreur = _TourCopiloteCoeur()._boucle_deepseek(
            env, cle, model, SYSTEME,
            [{"role": "user", "content": q}],
            [], {}, Usage)
        if erreur:
            return {"error": erreur}
        return {"reply": reply}


class BraignakEtudesPrivees(http.Controller):
    """Resultats d'etudes — PRIVE (04/08, demande Patrick) : la liste des
    etudes de Braignak et leur contenu, reserves aux comptes internes."""

    def _interne(self):
        u = request.env.user
        return not u._is_public() and u.has_group("base.group_user")

    @http.route("/braignak/etudes", type="http", auth="user", website=False)
    def etudes_liste(self, **kwargs):
        if not self._interne():
            return request.not_found()
        etudes = request.env["braignak.etude"].sudo().search(
            [], order="create_date desc")
        return request.render("tour_braignak.etudes_privees", {
            "etudes": etudes})

    @http.route("/braignak/etudes/<int:eid>", type="http", auth="user",
                website=False)
    def etude_detail(self, eid, **kwargs):
        if not self._interne():
            return request.not_found()
        e = request.env["braignak.etude"].sudo().browse(eid).exists()
        if not e:
            return request.not_found()
        return request.render("tour_braignak.etude_privee_detail", {
            "e": e})
