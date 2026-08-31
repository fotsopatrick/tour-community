# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

ETATS = {
    "a_faire": ("À faire", "○"),
    "en_cours": ("En cours", "◐"),
    "faite": ("Faite", "●"),
}


class QuetesPages(http.Controller):

    def _xp_patrick(self, env):
        """La compétence « Quêtes de carrière » de Patrick, si elle existe."""
        Comp = env["equipe.competence"].sudo()
        c = Comp.search([("code", "=", "patrick_quetes")], limit=1)
        if not c:
            return {"valeur": 0, "xp": 0, "etoiles": 0, "existe": False}
        return {"valeur": c.valeur or 0, "xp": c.xp or 0,
                "etoiles": c.etoiles or 0, "existe": True}

    @http.route("/tour/quetes", type="http", auth="user", website=False)
    def quetes(self, **kw):
        env = request.env
        est_admin = env.user.has_group("base.group_system")
        # Les quêtes montrent le travail de carrière du propriétaire (XP,
        # offres, guildes) : un invité ne voit que ses données (règle de
        # Patrick, 01/08). Réservé à l'admin tant que le module n'est pas
        # multi-utilisateur.
        if not est_admin:
            return request.redirect("/tour/dashboard")

        Domaines = env["quete.domaine"].sudo()
        Guildes = env["quete.guilde"].sudo().search([])
        Quetes = env["quete.fiche"].sudo().search([], order="etat, id desc")
        Offres = env["quete.offre"].sudo().search([], order="id desc")

        domaines = [{
            "id": d.id, "emoji": d.emoji, "name": d.name,
            "nb_quetes": d.nb_quetes, "nb_faites": d.nb_faites,
        } for d in Domaines.search([])]

        guildes = [{
            "id": g.id, "embleme": g.embleme, "name": g.name,
            "objectif": g.objectif, "active": g.active,
            "membres": [m.name for m in g.membre_ids],
            "nb_quetes": g.nb_quetes, "nb_faites": g.nb_faites,
        } for g in Guildes]

        quetes = []
        for q in Quetes:
            etat_nom, etat_signe = ETATS.get(q.etat, (q.etat, "•"))
            quetes.append({
                "id": q.id, "name": q.name, "description": q.description,
                "xp": q.xp, "etat": q.etat, "etat_nom": etat_nom,
                "etat_signe": etat_signe,
                "domaine": (q.domaine_id.emoji + " " + q.domaine_id.name)
                if q.domaine_id else "",
                "guilde": q.guilde_id.name or "",
                "source": q.source, "skill": q.skill or "",
                "date_faite": q.date_faite,
                "offre": q.offre_id.name or "",
            })

        offres = []
        for o in Offres:
            offres.append({
                "id": o.id, "name": o.name, "entreprise": o.entreprise,
                "etat": o.etat, "nb_skills": o.nb_skills,
                "nb_quetes": o.nb_quetes, "nb_faites": o.nb_faites,
                "couverture": o.couverture,
                "skills": [s for s in (o.skills or "").split("|") if s],
            })

        return request.render("tour_quetes.page_quetes", {
            "domaines": domaines,
            "guildes": guildes,
            "quetes": quetes,
            "offres": offres,
            "xp": self._xp_patrick(env),
            "est_admin": est_admin,
        })

    @http.route("/tour/descente", type="http", auth="user", website=False)
    def descente(self, **kw):
        """La Descente — la quête « plonger dans la machine couche par couche,
        jusqu'au traitement des biais ». Webapp pour TOUS les connectés."""
        env = request.env
        Projet = env["project.project"].sudo().search(
            [("name", "like", "%Descente%")], limit=1)
        taches = []
        if Projet:
            for t in env["project.task"].sudo().search(
                    [("project_id", "=", Projet.id)], order="id desc"):
                taches.append({"name": t.name, "state": t.state})
        couches = [
            ("1", "La vitrine", "ce que le monde voit"),
            ("2", "Les circuits", "le workflow, les règles"),
            ("3", "Les agents", "les métiers écrits"),
            ("4", "Les garde-fous", "le tunnel, les limites"),
            ("5", "Le moteur", "deepseek / opencode"),
            ("6", "Les biais", "ce qui fausse le raisonnement — on mesure et on corrige à la frontière"),
        ]
        return request.render("tour_quetes.page_descente", {
            "couches": couches, "taches": taches,
        })

    @http.route("/tour/mon-histoire", type="http", auth="user", website=False)
    def mon_histoire(self, **kw):
        """Mon histoire — la quête d'aventuriers, écrite par le travail réel.
        PRIVÉ : le propriétaire seul (un invité ne voit pas l'histoire interne)."""
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        Rep = request.env["reponse.fiche"].sudo()
        reps = Rep.search([], order="date desc", limit=300)
        chapitres = {}
        for r in reps:
            cle = (r.date.strftime("%Y-%m") if r.date else "?")
            chapitres.setdefault(cle, []).append({
                "name": r.name,
                "auteur": r.auteur or "",
                "reponse": (r.reponse or "")[:260],
                "date": r.date.strftime("%d/%m/%Y") if r.date else "",
            })
        return request.render("tour_quetes.page_mon_histoire", {
            "chapitres": [{"cle": c, "aventures": chapitres[c]}
                          for c in sorted(chapitres, reverse=True)],
            "total": len(reps),
        })

    @http.route("/tour/commande", type="http", auth="user", website=False,
                methods=["GET", "POST"])
    def commande(self, **kw):
        """La webapp shell — « quiconque a l'accès peut envoyer une commande
        à la machine ». Pilote seulement. La commande part au service hôte
        CONFINÉ (bwrap, 3215, réseau Docker uniquement), chaque exécution est
        journalisée."""
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        if request.httprequest.method == "POST":
            commande = (kw.get("commande") or "").strip()
            token = ""
            try:
                with open("/mnt/commandes-token", encoding="utf-8") as f:
                    token = f.read().strip()
            except OSError:
                token = ""
            import json as _json
            import urllib.request
            resultat = {"code": 0, "stdout": "", "stderr": ""}
            if commande:
                try:
                    corps = _json.dumps(
                        {"token": token, "commande": commande}).encode()
                    req = urllib.request.Request(
                        "http://172.17.0.1:3215/", data=corps,
                        headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=35) as rep:
                        resultat = _json.loads(rep.read().decode("utf-8"))
                except Exception as exc:  # noqa: BLE001
                    resultat = {"code": 0, "stdout": "",
                                "stderr": "service indisponible : %s" % exc}
            return request.render("tour_quetes.page_commande", {
                "commande": commande, "resultat": resultat})
        return request.render("tour_quetes.page_commande",
                              {"commande": "", "resultat": None})

    @http.route("/tour/articles-confidentiels", type="http", auth="user",
                website=False)
    def articles_confidentiels(self, **kw):
        """Les articles CONFIDENTIELS (fonctionnement machine) — privés,
        pilote seulement. Jamais sur la vitrine publique."""
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        import os
        dossier = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "src", "articles-confidentiels")
        fichiers = []
        if os.path.isdir(dossier):
            fichiers = sorted(
                n for n in os.listdir(dossier)
                if n.endswith(".html") and n.startswith("article-"))
        return request.render("tour_quetes.page_articles_confidentiels", {
            "fichiers": fichiers,
        })

    @http.route("/tour/articles-confidentiels/<fichier>", type="http",
                auth="user", website=False)
    def article_confidentiel(self, fichier=None, **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        import os
        base = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "src", "articles-confidentiels")
        chemin = os.path.join(base, os.path.basename(fichier or ""))
        if not (fichier and fichier.startswith("article-")
                and os.path.isfile(chemin)):
            return request.not_found()
        with open(chemin, encoding="utf-8") as f:
            corps = f.read()
        return request.make_response(corps,
                                     headers=[("Content-Type", "text/html; charset=utf-8")])

    @http.route("/tour/documents", type="http", auth="user", website=False)
    def documents(self, **kw):
        """MES DOCUMENTS — un espace privé (pilote seulement) où Patrick
        dépose et télécharge ses fichiers sensibles (ex. sa clé SSH) de
        n'importe où, une fois connecté. Jamais public."""
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        import os
        dossier = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "documents")
        os.makedirs(dossier, exist_ok=True)
        fichiers = []
        for n in sorted(os.listdir(dossier)):
            p = os.path.join(dossier, n)
            if os.path.isfile(p):
                fichiers.append({"nom": n, "octets": os.path.getsize(p)})
        return request.render("tour_quetes.page_documents", {
            "fichiers": fichiers,
        })

    @http.route("/tour/documents/<fichier>", type="http", auth="user",
                website=False)
    def document(self, fichier=None, **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        import os
        base = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "documents")
        chemin = os.path.join(base, os.path.basename(fichier or ""))
        if not (fichier and os.path.isfile(chemin)):
            return request.not_found()
        with open(chemin, "rb") as f:
            corps = f.read()
        return request.make_response(
            corps,
            headers=[("Content-Type", "application/octet-stream"),
                     ("Content-Disposition",
                      "attachment; filename=%s" % os.path.basename(chemin))])

    @http.route("/tour/documents/deposer", type="http", auth="user",
                website=False, methods=["POST"])
    def deposer_document(self, **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        import os
        dossier = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "documents")
        os.makedirs(dossier, exist_ok=True)
        f = request.httprequest.files.get("fichier")
        if f and f.filename:
            nom = os.path.basename(f.filename)
            f.save(os.path.join(dossier, nom))
        return request.redirect("/tour/documents")

    @http.route("/tour/quetes/generer", type="http", auth="user",
                methods=["POST"], website=False)
    def generer(self, poste="", entreprise="", texte="", **kw):
        env = request.env
        poste = (poste or "").strip()
        texte = (texte or "").strip()
        if not poste or not texte:
            raise ValueError("Le poste et le texte de l'offre sont requis.")
        Offre = env["quete.offre"].sudo()
        offre = Offre.create({
            "name": poste[:200],
            "entreprise": (entreprise or "").strip()[:200],
            "texte": texte,
        })
        offre.action_generer_quetes()
        return request.redirect("/tour/quetes#offre-%d" % offre.id)

    @http.route("/tour/quetes/terminer", type="http", auth="user",
                methods=["POST"], website=False)
    def terminer(self, quete_id="", **kw):
        env = request.env
        if quete_id:
            env["quete.fiche"].sudo().browse(int(quete_id)).action_terminer()
        return request.redirect("/tour/quetes")

    @http.route("/tour/quetes/en_cours", type="http", auth="user",
                methods=["POST"], website=False)
    def en_cours(self, quete_id="", **kw):
        env = request.env
        if quete_id:
            env["quete.fiche"].sudo().browse(int(quete_id)).action_en_cours()
        return request.redirect("/tour/quetes")

    @http.route("/tour/quetes/relancer", type="http", auth="user",
                methods=["POST"], website=False)
    def relancer(self, quete_id="", **kw):
        env = request.env
        if quete_id:
            env["quete.fiche"].sudo().browse(int(quete_id)).action_relancer()
        return request.redirect("/tour/quetes")
