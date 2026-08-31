# -*- coding: utf-8 -*-
"""Outil de rappel — la mémoire indexée de la tour.

Convention unique pour que TOUTES les webapps (même futures) s'y branchent :
- la tour (Odoo) déclare ses modèles dans _modeles() — une ligne par modèle ;
- chaque site statique dépose un `memoire.json` à sa racine (voir le format
  dans la page) — un nouveau site n'a qu'à déposer son fichier.

Garde-fous (consignés dans tour_garde_fous, code tour_memoire_rappel) :
  pilote seul, q borné et échappé, résultats limités, secrets masqués,
  fichiers bornés, JSON strict. Aucun SQL brut : recherche ORM en ilike.
"""
import json
import os
import re

from odoo import http
from odoo.http import request

_MAX_ENTREES = 20
_MAX_Q = 120
_MAX_FICHIER = 256 * 1024  # 256 Ko max par memoire.json

# Le même masque que le service « Qui travaille ? » : rien de sensible ne
# sort de la mémoire, même si un enregistrement en porte par erreur.
_SECRETS = [
    (re.compile(r"sk-ant-[A-Za-z0-9\-_]{8,}"), "sk-ant-***"),
    (re.compile(r"sk-[A-Za-z0-9\-_]{16,}"), "sk-***"),
    (re.compile(r"AIza[0-9A-Za-z\-_]{20,}"), "AIza***"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "ghp_***"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
     "-----BEGIN PRIVATE KEY-----***"),
    (re.compile(r"Tour2026Admin!|33762388938|62 38 89 38"), "***"),
]


def _rediger(texte):
    if not texte:
        return texte
    for motif, remplacement in _SECRETS:
        texte = motif.sub(remplacement, texte)
    return texte


class TourMemoire(http.Controller):
    """Le rappel : interroger la mémoire, rends les entrées pertinentes."""

    # ------------------------------------------------------------------
    # Convention : une entrée de mémoire = {titre, resume, cles, url,
    # date, statut, source, type}. C'est le contrat que toute webapp suit.
    # ------------------------------------------------------------------

    def _pilote(self):
        return request.env.user.has_group("base.group_system")

    def _modeles(self):
        """Le registre des sources Odoo. Une ligne par modèle = une webapp
        branchée. Un nouveau module n'a qu'à ajouter sa ligne ici."""
        registre = [
            # (modèle, libellé, champs à chercher, patron d'URL)
            ("project.task", "Tâche", ["name", "description"],
             "/web#id=%s&model=project.task&view_type=form"),
            ("atelier.mission", "Mission", ["name", "consigne"],
             "/web#id=%s&model=atelier.mission&view_type=form"),
            ("braignak.etude", "Étude Braignak", ["name", "contenu"],
             "/web#id=%s&model=braignak.etude&view_type=form"),
            ("decision.fiche", "Décision", ["name", "resume"],
             "/web#id=%s&model=decision.fiche&view_type=form"),
            ("equipe.guide", "Guide", ["name", "contenu"],
             "/web#id=%s&model=equipe.guide&view_type=form"),
            ("tour.message", "Message", ["name", "contenu"],
             "/web#id=%s&model=tour.message&view_type=form"),
        ]
        env = request.env
        modeles = []
        for nom, label, champs, patron in registre:
            if nom in env:
                modeles.append({
                    "model": nom, "label": label,
                    "champs": [c for c in champs if c in env[nom]._fields],
                    "url": patron,
                })
        return modeles

    def _sources_static(self):
        """Les `memoire.json` des sites statiques, depuis les dossiers
        déclarés (paramètre tour_memoire.dossiers, défaut /srv/sites)."""
        icp = request.env["ir.config_parameter"].sudo()
        dossiers = icp.get_param("tour_memoire.dossiers", "/srv/sites")
        entrees = []
        for d in dossiers.split(","):
            d = d.strip()
            if not d or not os.path.isdir(d):
                continue
            for nom in sorted(os.listdir(d)):
                chemin = os.path.join(d, nom, "memoire.json")
                if not os.path.isfile(chemin):
                    continue
                if os.path.getsize(chemin) > _MAX_FICHIER:
                    continue
                try:
                    with open(chemin, encoding="utf-8") as f:
                        data = json.load(f)
                except (OSError, ValueError):
                    continue
                if not isinstance(data, list):
                    continue
                for e in data:
                    if not isinstance(e, dict):
                        continue
                    entrees.append({
                        "source": nom,
                        "type": "site",
                        "titre": _rediger(str(e.get("titre") or ""))[:200],
                        "resume": _rediger(str(e.get("resume") or ""))[:300],
                        "cles": [str(c) for c in (e.get("cles") or [])][:20],
                        "url": str(e.get("url") or "")[:250],
                        "date": str(e.get("date") or ""),
                        "statut": str(e.get("statut") or "public"),
                    })
        return entrees

    def _search_odoo(self, q):
        env = request.env
        entrees = []
        for src in self._modeles():
            Modele = env[src["model"]]
            if not Modele.check_access_rights("read", raise_exception=False):
                continue
            feuilles = [(champ, "ilike", q) for champ in src["champs"]]
            if not feuilles:
                continue
            # Domaine OR plate : ['|'] * (n-1) + feuilles
            domaine = (["|"] * (len(feuilles) - 1)) + feuilles
            if not domaine:
                continue
            try:
                ids = Modele.search(domaine, limit=_MAX_ENTREES,
                                    order="write_date desc")
            except Exception:  # noqa: BLE001 — un modèle qui flanche ne tue pas le rappel
                continue
            for rec in ids:
                titre = str(getattr(rec, "name", False) or "")[:200]
                resume = ""
                for champ in src["champs"][1:]:
                    val = getattr(rec, champ, False)
                    if val:
                        resume = str(val)
                        break
                entrees.append({
                    "source": "tour",
                    "type": src["label"],
                    "titre": _rediger(titre),
                    "resume": _rediger(resume)[:300],
                    "cles": [],
                    "url": src["url"] % rec.id,
                    "date": (rec.write_date.strftime("%d/%m/%Y")
                             if getattr(rec, "write_date", None) else ""),
                    "statut": "interne",
                })
        return entrees

    @staticmethod
    def _marque(entree, tokens):
        texte = ("%s %s %s"
                 % (entree["titre"], entree["resume"],
                    " ".join(entree["cles"]))).lower()
        return all(t in texte for t in tokens)

    # ------------------------------------------------------------------
    # Routes — toutes sous le verrou pilote.
    # ------------------------------------------------------------------

    @http.route("/tour/memoire", type="http", auth="user", website=False)
    def page(self, **kw):
        if not self._pilote():
            return request.redirect("/tour/dashboard")
        return request.render("tour_memoire.page", {})

    @http.route("/tour/memoire/rappel", type="http", auth="user",
                website=False)
    def rappel(self, **kw):
        if not self._pilote():
            return self._json({"error": "reserve au pilote"}, status=403)
        q = (kw.get("q") or "").strip()
        if not q:
            return self._json({"q": "", "entrees": []})
        if len(q) > _MAX_Q:
            q = q[:_MAX_Q]
        # Échappement des jokers LIKE : %% et _ ne doivent pas élargir la
        # recherche au-delà de ce que le pilote a demandé.
        q_esc = q.replace("%", r"\%").replace("_", r"\_")
        tokens = [t for t in q.lower().split() if t]
        entrees = self._search_odoo(q_esc)
        entrees += [e for e in self._sources_static()
                    if self._marque(e, tokens)]
        entrees = entrees[:_MAX_ENTREES]
        return self._json({"q": q, "entrees": entrees})

    @http.route("/tour/memoire/data", type="http", auth="user",
                website=False)
    def data(self, **kw):
        if not self._pilote():
            return self._json({"error": "reserve au pilote"}, status=403)
        return self._json({
            "modeles": [{"model": m["model"], "label": m["label"]}
                        for m in self._modeles()],
            "statiques": self._sources_static()[:_MAX_ENTREES],
        })

    @staticmethod
    def _json(payload, status=200):
        return request.make_response(
            json.dumps(payload, ensure_ascii=False),
            status=status,
            headers=[("Content-Type", "application/json; charset=utf-8")],
        )
