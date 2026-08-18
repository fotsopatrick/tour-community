# -*- coding: utf-8 -*-
"""Vibe — le testeur.

Ce qu'il fait : il déroule un cahier de recette sur les sites qu'on lui confie,
retient la version testée, et prévient **quand quelque chose qui marchait ne
marche plus**. C'est cette dernière phrase qui compte : un test qui échoue
depuis toujours n'est pas une alerte, c'est du bruit.

Pourquoi il existe. Le 26/07, le site d'un client est resté en ligne avec un
catalogue vide et un panneau de filtres qui débordait, pendant que personne ne
regardait. Les deux étaient visibles en dix secondes — encore fallait-il que
quelqu'un ouvre la page.

**Le choix de conception, et il est délibéré : la v1 ne pilote pas de
navigateur.** Elle fait des vérifications HTTP en Python standard. Ça paraît
pauvre, et c'est exactement ce qu'il faut :

- ça attrape ce qui casse vraiment — une page morte, une image absente, un
  catalogue vide, un texte disparu ;
- ça ne demande **aucune** infrastructure nouvelle (ni Playwright, ni
  navigateur, ni moteur d'atelier) : ça tourne dans le cron, ce soir ;
- et surtout ça ne se trompe **jamais**. Un testeur qui crie au loup pour un
  détail cosmétique est désactivé en une semaine, et plus rien n'est testé.

Les gestes qui demandent un vrai navigateur (ajouter au panier, se connecter,
utiliser le back-office) sont notés comme tels et attendent le moteur dédié.
Dix vérifications qui ne mentent jamais valent mieux que cinquante
approximatives.
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

DELAI = 20  # secondes par requête : au-delà, le site est considéré en peine
AGENT = "Mozilla/5.0 (compatible; TourDeControle-Recette/1.0)"

TYPES_ETAPE = [
    ("page", "La page répond"),
    ("contient", "La page contient un texte"),
    ("absent", "La page NE contient PAS un texte"),
    ("image", "Une image se charge vraiment"),
    ("navigateur", "Demande un vrai navigateur (non exécuté en v1)"),
]


class RecetteCahier(models.Model):
    """Une liste d'étapes réutilisable, par type de produit."""

    _name = "recette.cahier"
    _description = "Vibe — cahier de recette"
    _order = "name"

    name = fields.Char("Cahier", required=True)
    type_produit = fields.Char(
        "Type de produit", help="Boutique en ligne, vitrine, application…")
    note = fields.Text("À quoi il sert")
    etape_ids = fields.One2many("recette.etape", "cahier_id", "Étapes")
    nb_etapes = fields.Integer("Étapes", compute="_compute_nb")

    @api.depends("etape_ids")
    def _compute_nb(self):
        for rec in self:
            rec.nb_etapes = len(rec.etape_ids)


class RecetteEtape(models.Model):
    _name = "recette.etape"
    _description = "Vibe — étape de recette"
    _order = "cahier_id, sequence, id"

    cahier_id = fields.Many2one("recette.cahier", required=True, ondelete="cascade")
    sequence = fields.Integer("Ordre", default=10)
    name = fields.Char("Ce qu'on vérifie", required=True)
    type_etape = fields.Selection(TYPES_ETAPE, string="Nature", required=True,
                                  default="page")
    chemin = fields.Char(
        "Chemin", default="/",
        help="Ajouté à l'adresse du site. Exemple : /catalogue")
    attendu = fields.Char(
        "Texte attendu",
        help="Pour « contient » et « absent ». Insensible à la casse.")
    critique = fields.Boolean(
        "Critique", default=False,
        help="Coché : sa panne est traitée comme urgente (page d'accueil, "
             "catalogue). Décoché : anomalie normale.")

    # D OU VIENT CETTE ETAPE : d un bug qu on a corrige.
    #
    # Le manque, dit par Patrick : quand il signale un bug, on le corrige — et
    # rien ne garantit qu il ne reviendra pas. Un correctif sans verification
    # qui le suit est un correctif qu on refera.
    #
    # Une etape nee d un bug vaut plus que les autres : elle a ete ecrite
    # apres avoir vu la panne pour de vrai, pas en imaginant ce qui pourrait
    # casser.
    tache_id = fields.Many2one(
        "project.task", "Bug d'origine", ondelete="set null",
        help="La tâche du bug qui a fait naître cette vérification. Elle est "
             "rejouée chaque nuit : le bug ne peut plus revenir en silence.")
    # LA DERNIÈRE DATE DE TEST (01/08, Patrick : « que Victor mette la
    # dernière date de test sur ces tests, sur la webapp qui affiche le
    # résultat »). Chaque test montre quand il a été exécuté pour la
    # dernière fois — un test qu'on ne relit pas, on le voit vieillir.
    dernier_test = fields.Datetime(
        "Dernier test", compute="_dernier_test", store=False,
        help="La date du dernier passage qui a exécuté cette étape.")

    @api.depends()
    def _dernier_test(self):
        Resultat = self.env["recette.resultat"].sudo()
        for e in self:
            # id desc = le passage le plus récent (un résultat est créé à
            # chaque exécution). L'order pointé (passage_id/create_date)
            # n'existe pas : search ne connaît pas les chemins pointés.
            r = Resultat.search(
                [("etape_id", "=", e.id)],
                order="id desc", limit=1)
            e.dernier_test = r.passage_id.create_date if r else False


class RecetteCible(models.Model):
    _name = "recette.cible"
    _description = "Vibe — site surveillé"
    _order = "name"

    name = fields.Char("Site", required=True)
    url_base = fields.Char("Adresse", required=True,
                           help="Sans barre oblique finale. Ex : https://exemple.fr")
    cahier_id = fields.Many2one("recette.cahier", string="Cahier", required=True)
    actif = fields.Boolean("Surveillé", default=True)
    version = fields.Char(
        "Version testée", readonly=True,
        help="Empreinte de la page d'accueil. Sert à savoir que le site a "
             "changé depuis le dernier passage — sans dépôt à interroger.")
    passage_ids = fields.One2many("recette.passage", "cible_id", "Passages",
                                  readonly=True)
    dernier_etat = fields.Selection(
        [("ok", "Tout passe"), ("anomalie", "Anomalies"),
         ("regression", "Régression"), ("jamais", "Jamais testé")],
        string="État", default="jamais", readonly=True)
    dernier_passage = fields.Datetime("Dernier passage", readonly=True)

    # ------------------------------------------------------------------
    def _lire(self, chemin):
        """Rend (code, corps, type_contenu). Ne lève jamais."""
        url = "%s%s" % (self.url_base.rstrip("/"), chemin or "/")
        requete = urllib.request.Request(url, headers={"User-Agent": AGENT})
        try:
            with urllib.request.urlopen(requete, timeout=DELAI) as rep:
                brut = rep.read(2_000_000)
                return rep.status, brut, rep.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            return exc.code, b"", ""
        except Exception as exc:  # noqa: BLE001 — réseau : tout peut arriver
            _logger.info("Recette : %s injoignable (%s)", url, exc)
            return 0, b"", ""

    def _executer_etape(self, etape):
        """Rend (ok, detail). `ok` à None = étape non exécutable en v1."""
        if etape.type_etape == "navigateur":
            return None, _("Demande un vrai navigateur — pas exécuté")

        code, corps, type_contenu = self._lire(etape.chemin)
        if code == 0:
            return False, _("Aucune réponse du serveur")
        if etape.type_etape == "page":
            return (code == 200), _("Code HTTP %s") % code
        if etape.type_etape == "image":
            if code != 200:
                return False, _("Code HTTP %s") % code
            if "image" not in (type_contenu or ""):
                return False, _("Type de contenu « %s » au lieu d'une image") % type_contenu
            if len(corps) < 100:
                return False, _("Image vide (%s octets)") % len(corps)
            return True, _("%s octets, %s") % (len(corps), type_contenu)

        # « absent » se contente d'une page qui ne répond pas : si la page
        # n'existe pas, le texte n'y est certainement pas. Sans cette
        # exception, vérifier qu'une adresse inexistante ne rend pas l'accueil
        # échouait à cause du 404 — c'est-à-dire au moment précis où le
        # résultat était bon. Un testeur qui se trompe là est un testeur qu'on
        # éteint.
        if code != 200 and etape.type_etape == "absent":
            return True, _("Page absente (code %s), donc le texte aussi") % code
        if code != 200:
            return False, _("Code HTTP %s") % code
        texte = corps.decode("utf-8", "replace")
        # On compare sans les balises : un texte peut être coupé par du HTML.
        sans_balises = re.sub(r"<[^>]+>", " ", texte)
        present = (etape.attendu or "").lower() in sans_balises.lower()
        if etape.type_etape == "contient":
            return present, (_("Texte trouvé") if present
                             else _("« %s » introuvable") % etape.attendu)
        return (not present), (_("Absent, comme attendu") if not present
                               else _("« %s » ne devrait pas être là") % etape.attendu)

    # ------------------------------------------------------------------
    def action_passer(self):
        """Déroule le cahier. C'est aussi le bouton de la fiche."""
        Passage = self.env["recette.passage"]
        for cible in self:
            if not cible.cahier_id.etape_ids:
                raise UserError(_("Le cahier « %s » n'a aucune étape.",
                                  cible.cahier_id.name))
            debut = time.time()
            lignes, nb_ok, nb_ko = [], 0, 0
            for etape in cible.cahier_id.etape_ids:
                ok, detail = cible._executer_etape(etape)
                lignes.append((0, 0, {
                    "etape_id": etape.id,
                    "nom": etape.name,
                    "etat": "ignore" if ok is None else ("ok" if ok else "ko"),
                    "detail": detail,
                    "critique": etape.critique,
                }))
                if ok is True:
                    nb_ok += 1
                elif ok is False:
                    nb_ko += 1

            code, corps, _ct = cible._lire("/")
            empreinte = str(abs(hash(corps[:200_000])))[:12] if corps else False

            passage = Passage.create({
                "cible_id": cible.id,
                "duree": int(time.time() - debut),
                "nb_ok": nb_ok,
                "nb_ko": nb_ko,
                "version": empreinte,
                "resultat_ids": lignes,
            })
            cible._conclure(passage, empreinte)
        return True

    def _conclure(self, passage, empreinte):
        """Compare au passage précédent et alerte SI ET SEULEMENT SI ça régresse."""
        self.ensure_one()
        precedent = self.env["recette.passage"].search(
            [("cible_id", "=", self.id), ("id", "!=", passage.id)],
            order="create_date desc", limit=1)

        # Une régression, c'est une étape qui passait et qui ne passe plus.
        # Sans cette comparaison, on renotifierait chaque nuit pour la même
        # chose — et on serait ignoré dès la troisième nuit.
        regressions = []
        if precedent:
            avant = {r.etape_id.id: r.etat for r in precedent.resultat_ids}
            for r in passage.resultat_ids:
                if r.etat == "ko" and avant.get(r.etape_id.id) == "ok":
                    regressions.append(r)

        etat = "ok" if passage.nb_ko == 0 else "anomalie"
        if regressions:
            etat = "regression"
        self.write({
            "dernier_etat": etat,
            "dernier_passage": fields.Datetime.now(),
            "version": empreinte or self.version,
        })
        passage.write({"regression": bool(regressions)})
        if regressions:
            self._alerter(passage, regressions)

    def _alerter(self, passage, regressions):
        """Une tâche datée + un courriel dont l'objet dit tout."""
        self.ensure_one()
        critique = any(r.critique for r in regressions)
        noms = ", ".join(r.nom for r in regressions[:3])
        titre = _("[REGRESSION] %(site)s — %(quoi)s",
                  site=self.name, quoi=noms)

        Task = self.env["project.task"].sudo()
        # Jamais deux fois la même tâche ouverte : la deuxième ne serait plus
        # lue, et la première non plus.
        if Task.search_count([("name", "=", titre),
                              ("state", "not in", ("1_done", "1_canceled"))]):
            return
        projet = self.env["project.project"].sudo().search(
            [("name", "ilike", "ODOO")], limit=1)
        detail = "".join(
            "<li><b>%s</b> — %s</li>" % (r.nom, r.detail) for r in regressions)
        tache = Task.create({
            "name": titre,
            "project_id": projet.id or False,
            "priority": "1" if critique else "0",
            "description": _(
                "<p>Vibe a trouvé une régression sur <b>%(site)s</b> "
                "(<a href='%(url)s'>%(url)s</a>).</p>"
                "<p>Ce qui marchait au passage précédent et ne marche plus :</p>"
                "<ul>%(detail)s</ul>"
                "<p>%(gravite)s</p>",
                site=self.name, url=self.url_base, detail=detail,
                gravite=(_("Une étape <b>critique</b> est touchée : le site est "
                           "probablement inutilisable pour un visiteur.")
                         if critique else
                         _("Aucune étape critique n'est touchée."))),
        })
        passage.tache_id = tache.id

        modele = self.env.ref("tour_recette.mail_regression", False)
        if modele:
            try:
                modele.send_mail(passage.id, force_send=False)
            except Exception:  # noqa: BLE001 — pas de courriel configuré
                _logger.info("Recette : courriel non envoyé (serveur sortant ?)")

    # ------------------------------------------------------------------
    @api.model
    def _cron_passer(self):
        for cible in self.sudo().search([("actif", "=", True)]):
            try:
                cible.action_passer()
            except Exception:  # noqa: BLE001 — un site en panne ne bloque pas les autres
                _logger.exception("Recette : passage en echec sur %s", cible.name)


class RecettePassage(models.Model):
    _name = "recette.passage"
    _description = "Vibe — passage de recette"
    _order = "create_date desc"
    _rec_name = "cible_id"

    cible_id = fields.Many2one("recette.cible", required=True, ondelete="cascade")
    duree = fields.Integer("Durée (s)", readonly=True)
    nb_ok = fields.Integer("Réussies", readonly=True)
    nb_ko = fields.Integer("Échouées", readonly=True)
    version = fields.Char("Version", readonly=True)
    regression = fields.Boolean("Régression", readonly=True)
    tache_id = fields.Many2one("project.task", string="Tâche créée", readonly=True)
    resultat_ids = fields.One2many("recette.resultat", "passage_id", "Détail")


class RecetteResultat(models.Model):
    _name = "recette.resultat"
    _description = "Vibe — résultat d'une étape"
    _order = "passage_id, id"

    passage_id = fields.Many2one("recette.passage", required=True, ondelete="cascade")
    etape_id = fields.Many2one("recette.etape", ondelete="set null")
    nom = fields.Char("Étape", readonly=True)
    etat = fields.Selection(
        [("ok", "Passe"), ("ko", "Échoue"), ("ignore", "Non exécutée")],
        string="Résultat", readonly=True)
    detail = fields.Char("Détail", readonly=True)
    critique = fields.Boolean("Critique", readonly=True)
