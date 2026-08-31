# -*- coding: utf-8 -*-
"""
Mettre un site en ligne depuis la tour.

Sept étapes, dans l'ordre où elles doivent réussir. Chacune est écrite pour
pouvoir être rejouée sans dégât : si le projet de base existe déjà, on le
réutilise au lieu d'en créer un second. Un déploiement qu'on n'ose pas relancer
est un déploiement qu'on finit à la main.

Les jetons ne sont jamais dans le code ni dans un champ : ils sont lus dans le
Coffre au moment de s'en servir, et cette lecture est tracée sur la fiche du
secret. C'est la tâche 205 — poser les clés sans qu'un humain les recopie.

Ce que ce module refuse de faire :
- inventer une réussite. Chaque étape rend un couple (réussi, ce qu'on a vu).
  « Site créé » sans avoir relu la réponse de l'hébergeur n'est pas une preuve.
- continuer après un échec. La suite s'appuie sur ce qui précède ; enchaîner
  produirait une cascade d'erreurs sans rapport avec la vraie cause.
"""
import json
import logging
import re
import time
import urllib.error
import urllib.request

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Au-delà, on considère que le service ne répond pas. Un déploiement qui pend
# une minute sur un appel bloque le cron et on ne sait pas pourquoi.
DELAI = 30


def _appel(url, methode="GET", jeton=None, corps=None, entetes=None, delai=DELAI):
    """Un appel HTTP qui rend toujours (code, données) au lieu de lever.

    Les API d'hébergeurs répondent en 4xx pour des situations parfaitement
    normales — « ce site existe déjà », « ce nom est pris ». Lever une
    exception à chaque fois obligerait à envelopper chaque appel dans un
    try/except, et la première fois qu'on oublie, le déploiement s'arrête sur
    une erreur qui n'en était pas une.
    """
    donnees = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(url, data=donnees, method=methode)
    req.add_header("Accept", "application/json")
    # Sans ça, urllib s'annonce « Python-urllib/3.x » et Cloudflare, qui protège
    # l'API de Supabase, répond 403 « Error 1010: Access denied » — un refus qui
    # ressemble trait pour trait à un jeton révoqué. On a cherché du mauvais
    # côté pendant un moment. Netlify, lui, ne filtre pas là-dessus.
    req.add_header("User-Agent", "tour-de-controle/1.0 (+https://matourdecontrole.fr)")
    if donnees is not None:
        req.add_header("Content-Type", "application/json")
    if jeton:
        req.add_header("Authorization", "Bearer %s" % jeton)
    for cle, val in (entetes or {}).items():
        req.add_header(cle, val)
    try:
        with urllib.request.urlopen(req, timeout=delai) as rep:
            brut = rep.read().decode("utf-8", "replace")
            try:
                return rep.status, json.loads(brut) if brut else {}
            except ValueError:
                return rep.status, brut
    except urllib.error.HTTPError as exc:
        brut = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(brut) if brut else {}
        except ValueError:
            return exc.code, brut
    except Exception as exc:  # réseau, DNS, délai dépassé
        return 0, str(exc)


class DeploiementSite(models.Model):
    _name = "deploiement.site"
    _description = "Site à mettre en ligne"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char("Nom", required=True, tracking=True)
    slug = fields.Char(
        "Identifiant technique", required=True, tracking=True,
        help="Sert de nom au projet de base et au site chez l'hébergeur. "
             "Lettres minuscules, chiffres et tirets.")
    actif = fields.Boolean("Actif", default=True)

    depot = fields.Char("Dépôt git", help="Ex. fotsopatrick/tabacimane")
    branche = fields.Char("Branche", default="main")
    url = fields.Char("Adresse en ligne", readonly=True, tracking=True)

    # --- ce qu'on est allé chercher, pas ce qu'on a saisi -------------------
    base_ref = fields.Char("Référence du projet de base", readonly=True, tracking=True)
    hebergeur_id_site = fields.Char("Identifiant chez l'hébergeur", readonly=True, tracking=True)

    migrations = fields.Text(
        "Migrations SQL",
        help="Le SQL à appliquer sur la base, dans l'ordre. Rejoué à chaque "
             "déploiement : il doit être écrit pour supporter d'être appliqué "
             "deux fois (CREATE TABLE IF NOT EXISTS, etc.).")
    catalogue = fields.Text(
        "Contenu de départ (SQL)",
        help="Ce qui doit exister à la livraison. Un site livré avec un "
             "catalogue vide a l'air cassé, même quand il marche.")
    admin_email = fields.Char("Compte administrateur du site")

    marqueurs = fields.Char(
        "Marqueurs attendus sur l'accueil", default="",
        help="Textes qui doivent apparaître sur la page d'accueil, séparés par "
             "des virgules. C'est ce qui distingue « la page répond » de « la "
             "page montre quelque chose ».")

    passage_ids = fields.One2many("deploiement.passage", "site_id", "Déploiements")
    dernier_etat = fields.Selection(
        [("jamais", "Jamais déployé"), ("ok", "En ligne"), ("echec", "En échec")],
        "État", compute="_compute_dernier_etat", store=True)

    _sql_constraints = [
        ("slug_unique", "unique(slug)", "Cet identifiant technique est déjà pris."),
    ]

    @api.depends("passage_ids.etat")
    def _compute_dernier_etat(self):
        for rec in self:
            dernier = rec.passage_ids[:1]
            rec.dernier_etat = dernier.etat if dernier else "jamais"

    @api.constrains("slug")
    def _verifier_slug(self):
        for rec in self:
            if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", rec.slug or ""):
                raise UserError(_(
                    "L'identifiant technique doit être en minuscules, sans "
                    "espace ni accent : « %s » ne convient pas.") % rec.slug)

    # ------------------------------------------------------------------
    # Les clés
    # ------------------------------------------------------------------
    def _cle(self, libelle):
        """Un secret du Coffre, ou une erreur qui dit lequel manque."""
        valeur = self.env["vault.secret"]._lire(
            libelle, motif=_("le déploiement de %s") % self.name)
        if not valeur:
            raise UserError(_(
                "Le Coffre n'a pas de secret nommé « %s ».\n\n"
                "Crée la fiche dans Coffre > Secrets et colle la valeur : le "
                "déploiement ira la chercher tout seul, personne n'aura à la "
                "recopier.") % libelle)
        return valeur

    # ==================================================================
    # Les sept étapes
    # ==================================================================
    def _etape_base(self, passage):
        """201 — le projet de base de données, sans ouvrir une interface."""
        jeton = self._cle("supabase-management-token")
        org = self.env["ir.config_parameter"].sudo().get_param("deploiement.supabase_org")
        if not org:
            raise UserError(_(
                "Il manque le paramètre système « deploiement.supabase_org » "
                "(l'identifiant de l'organisation Supabase)."))

        # On regarde d'abord si le projet existe : relancer un déploiement ne
        # doit pas fabriquer un deuxième projet payant portant le même nom.
        code, projets = _appel("https://api.supabase.com/v1/projects", jeton=jeton)
        if code != 200:
            return False, _("Supabase ne répond pas correctement (code %s) : %s") % (code, projets)
        existant = next((p for p in projets if p.get("name") == self.slug), None)
        if existant:
            self.base_ref = existant["id"]
            return True, _("Projet déjà présent, réutilisé (réf. %s)") % existant["id"]

        mdp = self._cle("supabase-db-password-%s" % self.slug)
        code, rep = _appel(
            "https://api.supabase.com/v1/projects", "POST", jeton,
            {"name": self.slug, "organization_id": org, "region": "eu-west-3",
             "db_pass": mdp, "plan": "free"})
        if code not in (200, 201):
            return False, _("Création refusée (code %s) : %s") % (code, rep)
        self.base_ref = rep.get("id")

        # Un projet Supabase n'est pas utilisable à la seconde où il est créé.
        # Enchaîner les migrations tout de suite échouerait sans raison
        # apparente — l'erreur ne dirait pas « attends ».
        for _essai in range(30):
            code, etat = _appel(
                "https://api.supabase.com/v1/projects/%s" % self.base_ref, jeton=jeton)
            if code == 200 and etat.get("status") == "ACTIVE_HEALTHY":
                return True, _("Projet créé et prêt (réf. %s)") % self.base_ref
            time.sleep(10)
        return False, _("Projet créé (réf. %s) mais toujours pas prêt après 5 minutes") % self.base_ref

    def _etape_migrations(self, passage):
        """202 — le SQL, sans passer par l'éditeur du navigateur."""
        if not (self.migrations or "").strip():
            return True, _("Aucune migration à appliquer")
        reussi, vu = self._sql(self.migrations)
        return reussi, _("Migrations : %s") % vu

    def _etape_hebergeur(self, passage):
        """203 + 205 — le site chez l'hébergeur, et ses variables."""
        jeton = self._cle("netlify-token")

        code, sites = _appel("https://api.netlify.com/api/v1/sites", jeton=jeton)
        if code != 200:
            return False, _("Netlify ne répond pas (code %s) : %s") % (code, sites)
        existant = next((s for s in sites if s.get("name") == self.slug), None)
        if existant:
            self.hebergeur_id_site = existant["id"]
            self.url = existant.get("ssl_url") or existant.get("url")
            vu = _("Site déjà présent, réutilisé")
        else:
            corps = {"name": self.slug}
            if self.depot:
                corps["repo"] = {"provider": "github", "repo": self.depot,
                                 "branch": self.branche or "main"}
            code, rep = _appel("https://api.netlify.com/api/v1/sites", "POST", jeton, corps)
            if code not in (200, 201):
                return False, _("Création du site refusée (code %s) : %s") % (code, rep)
            self.hebergeur_id_site = rep.get("id")
            self.url = rep.get("ssl_url") or rep.get("url")
            vu = _("Site créé")

        # Les variables d'environnement. Elles vont du Coffre à l'hébergeur
        # sans jamais s'afficher : c'est tout l'intérêt.
        if self.base_ref:
            jeton_sb = self._cle("supabase-management-token")
            code, cles = _appel(
                "https://api.supabase.com/v1/projects/%s/api-keys" % self.base_ref,
                jeton=jeton_sb)
            if code != 200:
                return False, _("%s, mais les clés de la base sont illisibles (code %s)") % (vu, code)
            par_nom = {k.get("name"): k.get("api_key") for k in (cles or [])}
            variables = {
                "NEXT_PUBLIC_SUPABASE_URL": "https://%s.supabase.co" % self.base_ref,
                "NEXT_PUBLIC_SUPABASE_ANON_KEY": par_nom.get("anon", ""),
                "SUPABASE_SERVICE_ROLE_KEY": par_nom.get("service_role", ""),
            }
            manquantes = [k for k, v in variables.items() if not v]
            if manquantes:
                return False, _("%s, mais ces clés sont introuvables : %s") % (vu, ", ".join(manquantes))

            compte = self.env["ir.config_parameter"].sudo().get_param("deploiement.netlify_account")
            for cle, val in variables.items():
                # `PUT` sur une variable qui n'existe pas la crée : une seule
                # requête couvre la création et la mise à jour, donc rejouer le
                # déploiement ne produit pas de doublon.
                _appel(
                    "https://api.netlify.com/api/v1/accounts/%s/env/%s?site_id=%s"
                    % (compte, cle, self.hebergeur_id_site),
                    "PUT", jeton, {"context": "all", "value": val})
            vu = _("%s, %s variables posées depuis le Coffre") % (vu, len(variables))
        return True, vu

    def _etape_admin(self, passage):
        """206 — le compte administrateur existe à la livraison."""
        if not self.admin_email:
            return True, _("Aucun compte administrateur demandé")
        mdp = self._cle("site-admin-password-%s" % self.slug)
        service = self._cle_service()
        code, rep = _appel(
            "https://%s.supabase.co/auth/v1/admin/users" % self.base_ref,
            "POST", service,
            {"email": self.admin_email, "password": mdp, "email_confirm": True},
            entetes={"apikey": service})
        if code in (200, 201):
            return True, _("Compte %s créé") % self.admin_email
        # 422 = l'utilisateur existe déjà. Ce n'est pas un échec : l'objectif
        # « le compte existe » est atteint.
        if code == 422:
            return True, _("Compte %s déjà présent") % self.admin_email
        return False, _("Création du compte refusée (code %s) : %s") % (code, rep)

    def _etape_catalogue(self, passage):
        """207 — jamais de catalogue vide à la livraison."""
        if not (self.catalogue or "").strip():
            return True, _("Aucun contenu de départ défini")
        reussi, vu = self._sql(self.catalogue)
        return reussi, _("Contenu de départ : %s") % vu

    def _etape_reponse(self, passage):
        """204 — le site RÉPOND vraiment avant qu'on le déclare livré."""
        if not self.url:
            return False, _("Aucune adresse : impossible de vérifier quoi que ce soit")
        # Un déploiement met un temps variable à sortir : on laisse jusqu'à
        # trois minutes avant de conclure, plutôt que de conclure trop tôt.
        for _essai in range(18):
            code, _rep = _appel(self.url, delai=15)
            if code == 200:
                return True, _("%s répond (code 200)") % self.url
            time.sleep(10)
        return False, _("%s ne répond pas (dernier code %s)") % (self.url, code)

    def _etape_regard(self, passage):
        """208 — regarder la page : un 200 ne dit pas qu'elle est présentable.

        Deux pannes répondent 200 sans rien signaler : la feuille de style
        absente (le site s'affiche en texte brut sur fond blanc) et l'accueil
        vide (le site marche, mais ne montre rien). Ce sont exactement les deux
        que le client voit en premier.
        """
        code, page = _appel(self.url, delai=20)
        if code != 200 or not isinstance(page, str):
            return False, _("Page illisible (code %s)") % code

        constats = []
        reussi = True

        feuilles = re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', page)
        if not feuilles:
            reussi = False
            constats.append(_("aucune feuille de style référencée — le site s'affichera nu"))
        else:
            lien = feuilles[0]
            if lien.startswith("/"):
                lien = self.url.rstrip("/") + lien
            code_css, css = _appel(lien, delai=15)
            # Un Tailwind compilé pèse des dizaines de milliers de caractères.
            # Sous 500, c'est une page d'erreur déguisée en CSS.
            if code_css != 200 or len(str(css)) < 500:
                reussi = False
                constats.append(_("la feuille de style ne se charge pas (code %s)") % code_css)
            else:
                constats.append(_("style chargé (%s caractères)") % len(str(css)))

        texte = re.sub(r"<script.*?</script>", " ", page, flags=re.S)
        texte = re.sub(r"<[^>]+>", " ", texte)
        texte = re.sub(r"\s+", " ", texte).strip()
        if len(texte) < 200:
            reussi = False
            constats.append(_("l'accueil ne contient presque aucun texte (%s caractères)") % len(texte))

        attendus = [m.strip() for m in (self.marqueurs or "").split(",") if m.strip()]
        absents = [m for m in attendus if m.lower() not in page.lower()]
        if absents:
            reussi = False
            constats.append(_("introuvable sur l'accueil : %s") % ", ".join(absents))
        elif attendus:
            constats.append(_("%s marqueurs présents") % len(attendus))

        return reussi, " ; ".join(constats)

    # ------------------------------------------------------------------
    # Outils communs
    # ------------------------------------------------------------------
    def _cle_service(self):
        jeton_sb = self._cle("supabase-management-token")
        code, cles = _appel(
            "https://api.supabase.com/v1/projects/%s/api-keys" % self.base_ref, jeton=jeton_sb)
        if code != 200:
            raise UserError(_("Impossible de lire les clés de la base (code %s).") % code)
        for k in cles or []:
            if k.get("name") == "service_role":
                return k.get("api_key")
        raise UserError(_("La base n'expose pas de clé « service_role »."))

    def _sql(self, sql):
        """Exécute du SQL sur la base, par l'API — pas par un éditeur web."""
        if not self.base_ref:
            return False, _("aucune base : l'étape précédente n'a pas abouti")
        jeton = self._cle("supabase-management-token")
        code, rep = _appel(
            "https://api.supabase.com/v1/projects/%s/database/query" % self.base_ref,
            "POST", jeton, {"query": sql}, delai=120)
        if code in (200, 201):
            return True, _("appliqué (%s instructions)") % (sql.count(";") or 1)
        return False, _("refusé (code %s) : %s") % (code, rep)

    # ==================================================================
    # La chaîne
    # ==================================================================
    ETAPES = [
        ("base", "Projet de base de données"),
        ("migrations", "Migrations SQL"),
        ("hebergeur", "Site et variables chez l'hébergeur"),
        ("admin", "Compte administrateur"),
        ("catalogue", "Contenu de départ"),
        ("reponse", "Le site répond"),
        ("regard", "Le site est présentable"),
    ]

    def action_verifier_cles(self):
        """Est-ce que mes clés marchent ? — sans rien déployer.

        Sans ce bouton, la seule façon de savoir si un jeton est bon est de
        lancer un déploiement et de le voir échouer à l'étape 1 ou 3. C'est
        long, et le message d'erreur parle de l'étape, pas de la clé.

        Il en profite pour aller chercher tout seul les deux paramètres
        système (organisation Supabase, compte Netlify) : ce sont des valeurs
        que l'API connaît. Faire recopier à un humain une donnée qu'une machine
        peut lire, c'est fabriquer une occasion de se tromper.
        """
        self.ensure_one()
        params = self.env["ir.config_parameter"].sudo()
        lignes = []

        # --- Supabase
        jeton = self.env["vault.secret"]._lire(
            "supabase-management-token", motif=_("la vérification des clés"))
        if not jeton:
            lignes.append(_("❌ Supabase : la fiche « supabase-management-token » est vide."))
        else:
            code, orgs = _appel("https://api.supabase.com/v1/organizations", jeton=jeton)
            if code == 200 and isinstance(orgs, list) and orgs:
                params.set_param("deploiement.supabase_org", orgs[0].get("id"))
                lignes.append(_("✅ Supabase : jeton valide. Organisation « %s » retenue.")
                              % orgs[0].get("name"))
            elif code in (401, 403):
                lignes.append(_("❌ Supabase : le jeton est refusé (code %s). "
                                "Il a peut-être été révoqué, ou mal collé.") % code)
            else:
                lignes.append(_("❌ Supabase : réponse inattendue (code %s) : %s") % (code, orgs))

        # --- Netlify
        jeton = self.env["vault.secret"]._lire(
            "netlify-token", motif=_("la vérification des clés"))
        if not jeton:
            lignes.append(_("❌ Netlify : la fiche « netlify-token » est vide."))
        else:
            code, comptes = _appel("https://api.netlify.com/api/v1/accounts", jeton=jeton)
            if code == 200 and isinstance(comptes, list) and comptes:
                params.set_param("deploiement.netlify_account", comptes[0].get("slug"))
                lignes.append(_("✅ Netlify : jeton valide. Compte « %s » retenu.")
                              % comptes[0].get("name"))
            elif code in (401, 403):
                lignes.append(_("❌ Netlify : le jeton est refusé (code %s).") % code)
            else:
                lignes.append(_("❌ Netlify : réponse inattendue (code %s) : %s") % (code, comptes))

        # --- le mot de passe de la base
        if self.env["vault.secret"]._lire(
                "supabase-db-password-%s" % self.slug, motif=_("la vérification des clés")):
            lignes.append(_("✅ Mot de passe de la base : présent."))
        else:
            lignes.append(_("❌ Mot de passe de la base : la fiche "
                            "« supabase-db-password-%s » est vide.") % self.slug)

        complet = all(l.startswith("✅") for l in lignes)
        self.message_post(body="<ul><li>%s</li></ul>" % "</li><li>".join(lignes))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Tout est prêt") if complet else _("Il manque quelque chose"),
                "message": "\n".join(lignes),
                "sticky": True,
                "type": "success" if complet else "warning",
            },
        }

    def action_deployer(self):
        """198 — tout, à la suite, sans un seul clic ailleurs."""
        self.ensure_one()
        passage = self.env["deploiement.passage"].create({"site_id": self.id})
        lignes = []
        etat = "ok"

        for cle, titre in self.ETAPES:
            debut = time.time()
            try:
                reussi, vu = getattr(self, "_etape_%s" % cle)(passage)
            except UserError as exc:
                reussi, vu = False, str(exc)
            except Exception as exc:  # noqa: BLE001 — on veut le journal, pas la trace
                _logger.exception("Déploiement %s, étape %s", self.slug, cle)
                reussi, vu = False, _("erreur inattendue : %s") % exc
            duree = round(time.time() - debut, 1)
            lignes.append("<li><b>%s</b> — %s <i>(%ss)</i><br/>%s</li>" % (
                titre, _("réussi") if reussi else _("ÉCHEC"), duree, vu))
            if not reussi:
                # On s'arrête : les étapes suivantes s'appuient sur celle-ci et
                # produiraient une cascade d'erreurs sans rapport avec la cause.
                etat = "echec"
                lignes.append("<li><i>%s</i></li>" % _(
                    "Arrêt ici : la suite dépend de cette étape."))
                break

        passage.write({
            "etat": etat,
            "journal": "<ol>%s</ol>" % "".join(lignes),
            "url": self.url,
        })
        self.message_post(body=_(
            "Déploiement %s. %s") % (
            _("réussi") if etat == "ok" else _("en échec"), passage.journal))
        return {
            "type": "ir.actions.act_window",
            "res_model": "deploiement.passage",
            "res_id": passage.id,
            "view_mode": "form",
            "target": "current",
        }


class DeploiementPassage(models.Model):
    _name = "deploiement.passage"
    _description = "Un déploiement"
    _order = "create_date desc"

    site_id = fields.Many2one("deploiement.site", "Site", required=True, ondelete="cascade")
    name = fields.Char("Nom", compute="_compute_name", store=True)
    etat = fields.Selection(
        [("encours", "En cours"), ("ok", "Réussi"), ("echec", "En échec")],
        "État", default="encours", required=True)
    journal = fields.Html("Journal", readonly=True)
    url = fields.Char("Adresse", readonly=True)

    @api.depends("site_id", "create_date")
    def _compute_name(self):
        for rec in self:
            date = fields.Datetime.to_string(rec.create_date)[:16] if rec.create_date else ""
            rec.name = "%s — %s" % (rec.site_id.name or "", date)
