# -*- coding: utf-8 -*-
"""Répondre à Victor depuis un courriel, sans se connecter.

Le geste visé : le téléphone vibre, on lit trois lignes, on tape « Accepter ».
Si ce geste demande de se connecter à la tour depuis un mobile, il ne se fait
pas — et la sécurité attend une semaine.

Ce qui protège ces adresses : un jeton de 32 octets tiré au hasard, propre à
UN constat. Il ne permet que de répondre à celui-là. Il ne lit rien, n'ouvre
aucune session, ne donne accès à aucune donnée — et le pire qu'un lien
intercepté permette, c'est de refuser un correctif de sécurité, ce qui se voit
dans le fil de la fiche.
"""
from odoo import http
from odoo.http import request

REPONSES = {
    "accepter": ("accepte", "C'est noté", "Je m'en occupe.",
                 "#22c55e"),
    "attente": ("attente", "Mis en attente", "Je te le représenterai plus tard.",
                "#f59e0b"),
    "refuser": ("refuse", "Refusé", "Je ne te le reproposerai pas.",
                "#94a3b8"),
}


class PagePentest(http.Controller):

    # LES CONTROLES QUE VICTOR SAIT JOUER (miroir de deploy/pentest.sh).
    # Ils sont ecrits ici pour que la carte montre AUSSI ce qui est passe :
    # un controle sans constat est un controle VERT, pas un controle absent.
    CONTROLES_PENTEST = [
        ("pentest_hsts", "En-tête HSTS", "le navigateur exige-t-il HTTPS ?"),
        ("pentest_nosniff", "En-tête nosniff", "le type de fichier est-il respecté ?"),
        ("pentest_clickjacking", "Anti-clickjacking", "la page peut-elle être encadrée ?"),
        ("pentest_banniere", "Bannière serveur", "la techno est-elle annoncée ?"),
        ("pentest_db_manager", "Gestionnaire de bases", "la porte /web/database est-elle ouverte ?"),
        ("pentest_db_list", "Liste des bases", "les noms de bases fuient-ils ?"),
        ("pentest_cookie_httponly", "Cookie HttpOnly", "le JS peut-il lire la session ?"),
        ("pentest_cookie_secure", "Cookie Secure", "la session part-elle en clair ?"),
        ("pentest_xmlrpc", "XML-RPC", "l interface machine est-elle bavarde ?"),
        ("pentest_rate_login", "Limite de connexions", "peut-on essayer sans fin ?"),
    ]

    def _banc_pentest(self):
        """Un controle = une puce. Etat : ko (constat ouvert), accepte (risque
        assume), ok (joue, rien trouve), jamais (sonde jamais passee)."""
        import datetime
        import os
        Constat = request.env["securite.constat"].sudo()
        # LA DATE DE LA DERNIERE SONDE. Sans elle, on ne peut RIEN affirmer :
        # une absence de constat n est pas une preuve que le controle est
        # passe. « Rien signale le 4 aout » se verifie ; « rien trouve » se
        # croit sur parole.
        chemin_json = "/mnt/atelier/instances/pentest/constats.json"
        quand = ""
        if os.path.exists(chemin_json):
            try:
                quand = datetime.datetime.fromtimestamp(
                    os.path.getmtime(chemin_json)).strftime("%d/%m à %H:%M")
            except Exception:  # noqa: BLE001
                quand = ""
        deja_joue = bool(quand)
        banc = []
        for code, nom, question in self.CONTROLES_PENTEST:
            c = Constat.search([("code", "=", code)], limit=1) \
                if "code" in Constat._fields else Constat.browse()
            if not c:
                c = Constat.search([("name", "ilike", nom)], limit=1)
            etat, libelle, detail, gravite = "jamais", "JAMAIS SONDÉ", "", ""
            if c:
                gravite = getattr(c, "gravite", "") or ""
                if getattr(c, "etat", "") == "accepte":
                    etat, libelle = "accepte", "risque assumé"
                else:
                    etat, libelle = "ko", "constat ouvert"
                detail = (getattr(c, "name", "") or "")
            elif deja_joue:
                # Pas « rien trouve » (qui laisserait croire a une preuve),
                # mais « rien signale le <date> » : un fait verifiable.
                etat, libelle = "ok", "rien signalé le %s" % quand
            banc.append({"code": code, "nom": nom, "etat": etat,
                         "libelle": libelle, "gravite": gravite,
                         "detail": detail or question})
        return banc

    @http.route("/tour/pentest/rejouer", type="http", auth="user",
                methods=["POST"], csrf=False, website=False)
    def pentest_rejouer(self, **kw):
        """Depose un ORDRE : l atelier lancera le vrai pentest sur la DEMO.
        La cible est en dur dans deploy/pentest.sh — cette route ne choisit
        rien, elle demande seulement « rejoue ». Reservee a l admin."""
        import json as _json
        import os
        if not request.env.user.has_group("base.group_system"):
            return request.make_response(
                _json.dumps({"ok": False, "erreur": "réservé à l administrateur"}),
                [("Content-Type", "application/json")])
        try:
            dossier = "/mnt/atelier/ordres"
            os.makedirs(dossier, exist_ok=True)
            with open(os.path.join(dossier, "pentest.ordre"), "w",
                      encoding="utf-8") as f:
                f.write("rejouer le pentest (demande depuis le cockpit)\n")
            ok, err = True, ""
        except Exception as exc:  # noqa: BLE001
            ok, err = False, str(exc)[:120]
        return request.make_response(
            _json.dumps({"ok": ok, "erreur": err}),
            [("Content-Type", "application/json")])

    @http.route("/tour/pentest", type="http", auth="user", website=False)
    def pentest(self, **kw):
        """La web app PENTEST — PRIVÉE. Réservée à l'admin (Victor y répond).

        Une page de pentest révèle la posture de sécurité de la tour : elle
        ne doit JAMAIS être publique. On y voit les constats de Victor et le
        dernier scan du cahier de tests."""
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        Constat = request.env["securite.constat"].sudo()
        constats = Constat.search([], order="create_date desc", limit=15)
        scan = ""
        try:
            import os
            chemin = "/srv/sites/cahier-de-tests/index.html"
            if os.path.exists(chemin):
                with open(chemin, encoding="utf-8") as f:
                    scan = f.read()
        except Exception:  # noqa: BLE001
            scan = ""
        import json as _json
        from markupsafe import Markup
        return request.render("tour_securite.pentest", {
            "constats": constats,
            "scan": scan,
            "banc_json": Markup(_json.dumps(self._banc_pentest(),
                                            ensure_ascii=False)),
        })

PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Victor — %(titre)s</title>
<style>
 body{margin:0;background:#020817;color:#e2e8f0;min-height:100vh;display:flex;
      align-items:center;justify-content:center;
      font-family:system-ui,-apple-system,"Segoe UI",sans-serif;padding:1.5rem}
 .c{max-width:26rem;text-align:center}
 .p{width:3.5rem;height:3.5rem;border-radius:50%%;background:%(couleur)s;
    margin:0 auto 1.25rem;display:flex;align-items:center;justify-content:center;
    font-size:1.6rem;color:#04140a}
 h1{font-size:1.5rem;margin:0 0 .5rem}
 p{color:#94a3b8;margin:0 0 .4rem}
 .q{color:#cbd5e1;font-weight:500;margin-top:1.25rem}
</style></head><body><div class="c">
<div class="p">%(icone)s</div>
<h1>%(titre)s</h1>
<p>%(suite)s</p>
<div class="q">%(quoi)s</div>
</div></body></html>"""


class TourSecurite(http.Controller):

    @http.route("/securite/<string:jeton>/<string:reponse>",
                type="http", auth="public", website=False, csrf=False)
    def repondre(self, jeton, reponse, **kw):
        if reponse not in REPONSES:
            return request.not_found()

        constat = request.env["securite.constat"].sudo().search(
            [("jeton", "=", jeton)], limit=1)
        if not constat:
            # Volontairement identique a un lien inconnu : ne pas indiquer
            # qu'un jeton a existe. On ne renseigne pas celui qui cherche.
            return request.not_found()

        etat, titre, suite, couleur = REPONSES[reponse]
        deja = constat.etat == etat
        if not deja:
            constat._repondre(etat)

        return request.make_response(PAGE % {
            "titre": titre if not deja else "Déjà répondu",
            "suite": suite,
            "quoi": constat.name,
            "couleur": couleur,
            "icone": {"accepte": "✓", "attente": "⏳", "refuse": "×"}[etat],
        }, headers=[("Content-Type", "text/html; charset=utf-8")])
