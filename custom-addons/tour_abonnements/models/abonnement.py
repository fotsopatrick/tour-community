# -*- coding: utf-8 -*-
"""Les abonnements — la brique que Community n'a pas.

Odoo Enterprise vend `sale_subscription`. En Community, il n'y a rien : pas de
récurrence, pas de relance, pas de gestion d'échec de carte. Trois offres à
25, 35 et 45 € par mois n'ont donc aucun moteur.

**Le choix qui commande tout le reste : Stripe est la source de vérité de la
facturation, la tour est la source de vérité du contrat.**

On ne réimplémente pas la récurrence. Refaire les relances, la carte qui
expire, le prorata, la TVA par pays et la résiliation, c'est des mois de
travail — et chaque bug se paie en argent réel qui ne rentre pas, ou pire, qui
rentre deux fois. Stripe fait ça depuis dix ans. La tour, elle, sait ce qu'un
client a le droit d'utiliser, et c'est elle qui monte l'instance.

Conséquence pratique : **la tour n'appelle presque jamais Stripe**. Elle écoute.
Stripe pousse ses événements sur un webhook signé, la tour met le contrat à
jour. Un système qui interroge sans arrêt manque toujours l'événement qui
compte ; un système qui écoute le reçoit une fois, avec sa signature.

Ce que ce module ne fait PAS : encaisser lui-même. Aucun numéro de carte ne
touche jamais la tour — c'est Stripe qui affiche le formulaire, sur son
domaine. On ne veut ni la responsabilité ni la conformité qui vont avec.
"""
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _stripe(env, chemin, methode="GET", donnees=None):
    """Appel à l'API Stripe avec la clé déjà configurée dans le fournisseur.

    On lit la clé du `payment.provider` plutôt que d'en demander une nouvelle :
    elle y est, elle marche, et une clé de moins qui traîne est une clé de
    moins qui fuit.
    """
    prov = env["payment.provider"].sudo().search([("code", "=", "stripe")], limit=1)
    cle = prov.stripe_secret_key if prov else False
    if not cle:
        raise UserError(_(
            "Aucune clé secrète Stripe n'est configurée dans le fournisseur de "
            "paiement. Sans elle, impossible de créer un abonnement."))

    url = "https://api.stripe.com/v1/%s" % chemin
    corps = None
    if donnees is not None:
        # Stripe attend du form-urlencoded, y compris pour les structures
        # imbriquées (metadata[x], line_items[0][price]).
        corps = urllib.parse.urlencode(donnees, doseq=True).encode()
    req = urllib.request.Request(url, data=corps, method=methode)
    req.add_header("Authorization", "Bearer %s" % cle)
    req.add_header("User-Agent", "tour-de-controle/1.0 (+https://matourdecontrole.fr)")
    if corps is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30) as rep:
            return json.loads(rep.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise UserError(_("Stripe a répondu %(code)s : %(detail)s",
                          code=exc.code, detail=detail)) from exc


class AbonnementOffre(models.Model):
    _name = "abonnement.offre"
    _description = "Offre commerciale"
    _order = "sequence, prix"

    name = fields.Char("Offre", required=True)
    code = fields.Char("Code", required=True, help="Identifiant stable, sert dans les liens.")
    sequence = fields.Integer(default=10)
    prix = fields.Float("Prix", required=True)
    periode = fields.Selection(
        [("mois", "Par mois"), ("unique", "Paiement unique")],
        "Récurrence", default="mois", required=True)
    accroche = fields.Char("En une phrase")
    detail = fields.Text("Ce qui est compris")
    actif = fields.Boolean("Actif", default=True)
    publie = fields.Boolean(
        "Publié", default=False,
        help="Tant que ce n'est pas coché, aucun lien de paiement n'est proposé. "
             "Un prix affiché engage : on ne publie pas un brouillon.")

    duree_jours = fields.Integer(
        "Duree de vie (jours)", default=0,
        help="0 = sans limite. Au-dela, l'instance est supprimee apres ce "
             "nombre de jours. Une demo qui vit pour toujours est un "
             "abonnement a vie paye une fois.")

    # Ce qui est LIVRE au payeur. Par defaut une instance Odoo ; pour la balise
    # SOS, un CODE d'acces a la Zone Detresse (3 €/mois, verdict Braignak du
    # 31/07). Le code est livre par courriel et valide par la balise.
    # TROISIEME SERVICE (04/08) : l acces a un agent, sans instance.
    #
    # Braignak se vend 79 EUR/mois. Avec les deux seules valeurs d origine, il
    # aurait fallu le declarer « instance » — et `_souscription` monte une
    # instance Odoo complete pour toute offre mensuelle. Chaque abonne a
    # Braignak aurait donc declenche le montage d une tour entiere : des
    # minutes de serveur, un sous-domaine, un certificat, pour un service qui
    # n en a aucun besoin. On ne plie pas le sens d un champ pour eviter d en
    # ajouter un.
    service = fields.Selection(
        [("instance", "Instance Odoo"),
         ("zone_detresse", "Code Zone Détresse"),
         ("acces", "Accès à un agent (sans instance)")],
        "Service livré", default="instance", required=True,
        help="instance = une tour Odoo montee pour le client. "
             "zone_detresse = un code d'acces a la balise SOS, sans instance. "
             "acces = un acces a un agent (Braignak...), sans instance.")

    stripe_product_id = fields.Char("Produit Stripe", readonly=True, copy=False)
    stripe_price_id = fields.Char("Tarif Stripe", readonly=True, copy=False)
    lien_paiement = fields.Char("Lien de paiement", readonly=True, copy=False)

    contrat_ids = fields.One2many("abonnement.contrat", "offre_id", "Contrats")
    nb_contrats = fields.Integer("Abonnés", compute="_compute_nb")

    _sql_constraints = [("code_unique", "unique(code)", "Ce code est déjà pris.")]

    @api.depends("contrat_ids.etat")
    def _compute_nb(self):
        for rec in self:
            rec.nb_contrats = len(rec.contrat_ids.filtered(lambda c: c.etat == "actif"))

    # ------------------------------------------------------------------
    def action_publier_chez_stripe(self):
        """Crée le produit, le tarif et le lien de paiement chez Stripe.

        Idempotent : si le produit existe déjà, on le réutilise. Relancer ne
        doit pas fabriquer trois tarifs pour la même offre — on se retrouverait
        avec des clients au même prix affiché mais sur des tarifs différents,
        et plus aucun moyen de faire une remise proprement.
        """
        for rec in self:
            if not rec.publie:
                raise UserError(_(
                    "L'offre « %s » n'est pas publiée. Un lien de paiement sur "
                    "un prix en brouillon engagerait sur un montant non "
                    "arrêté.") % rec.name)

            if not rec.stripe_product_id:
                prod = _stripe(rec.env, "products", "POST", {
                    "name": rec.name,
                    "description": (rec.accroche or "")[:300] or rec.name,
                    "metadata[code]": rec.code,
                })
                rec.stripe_product_id = prod["id"]

            if not rec.stripe_price_id:
                d = {
                    "product": rec.stripe_product_id,
                    "unit_amount": int(round(rec.prix * 100)),
                    "currency": "eur",
                    "metadata[code]": rec.code,
                }
                if rec.periode == "mois":
                    d["recurring[interval]"] = "month"
                tarif = _stripe(rec.env, "prices", "POST", d)
                rec.stripe_price_id = tarif["id"]

            if not rec.lien_paiement:
                base = rec.env["ir.config_parameter"].sudo().get_param("web.base.url")
                d = {
                    "line_items[0][price]": rec.stripe_price_id,
                    "line_items[0][quantity]": 1,
                    # Ce que Stripe renverra dans l'événement : c'est ce qui
                    # permet à la tour de savoir QUELLE offre a été payée.
                    "metadata[code]": rec.code,
                    "after_completion[type]": "redirect",
                    "after_completion[redirect][url]":
                        "%s/abonnement/merci" % base.rstrip("/"),
                }
                # Cette métadonnée-là n'existe QUE pour un abonnement. La
                # poser sur un paiement unique fait répondre 400 à Stripe —
                # et le message d'erreur ne dit pas laquelle des dix clés
                # pose problème.
                if rec.periode == "mois":
                    d["subscription_data[metadata][code]"] = rec.code
                lien = _stripe(rec.env, "payment_links", "POST", d)
                rec.lien_paiement = lien["url"]
        return True


class AbonnementContrat(models.Model):
    _name = "abonnement.contrat"
    _description = "Contrat d'abonnement"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char("Référence", readonly=True, default="Nouveau", copy=False)
    partner_id = fields.Many2one("res.partner", "Client", required=True, tracking=True)
    offre_id = fields.Many2one("abonnement.offre", "Offre", required=True, tracking=True)
    etat = fields.Selection(
        [("actif", "Actif"),
         ("impaye", "Impayé"),
         ("resilie", "Résilié")],
        "État", default="actif", required=True, tracking=True)

    date_debut = fields.Date("Depuis", default=fields.Date.context_today)
    date_fin = fields.Date("Résilié le")
    montant = fields.Float("Montant", tracking=True)

    stripe_customer_id = fields.Char("Client Stripe", readonly=True, copy=False, index=True)
    stripe_subscription_id = fields.Char("Abonnement Stripe", readonly=True, copy=False, index=True)

    instance_url = fields.Char("Instance livrée", tracking=True)
    instance_etat = fields.Selection(
        [("a_monter", "À monter"), ("montee", "Montée"), ("sans_objet", "Sans objet")],
        "Instance", default="a_monter", tracking=True)

    # Zone Détresse : le code d'accès à la balise, livré au payeur. La balise
    # (zone-detresse) le valide auprès de la tour avant d'accepter une position.
    zone_detresse_code = fields.Char(
        "Code Zone Détresse", readonly=True, copy=False, index=True,
        help="Code d'acces a la balise SOS, genere a la souscription et "
             "envoye par courriel au payeur. Unique.")

    date_expiration = fields.Date(
        "Expire le", help="Calculee a la souscription pour les offres a duree "
        "limitee. Vide = pas de limite.")
    avertie_le = fields.Date("Avertie le", readonly=True)

    _sql_constraints = [
        # Deux contrats pour un meme abonnement Stripe = deux instances
        # montees et deux courriels de bienvenue pour un seul abonne. Le
        # journal des evenements l'empeche deja en amont ; celle-ci est la
        # ceinture, au cas ou un contrat soit cree par un autre chemin.
        # Postgres accepte plusieurs NULL sur une colonne unique, donc les
        # contrats sans abonnement (paiement unique) ne se genent pas.
        ("stripe_sub_unique", "unique(stripe_subscription_id)",
         "Un contrat existe deja pour cet abonnement Stripe."),
        # Un code par payeur, jamais deux fois le meme (deux contrats avec le
        # meme code = deux balises qu'on ne peut plus distinguer).
        ("zd_code_unique", "unique(zone_detresse_code)",
         "Ce code Zone Détresse est déjà attribué."),
    ]

    date_demontage = fields.Date(
        "Instance à démonter le", readonly=True, tracking=True,
        help="Posée à la résiliation. L'instance vit encore quelques jours "
             "après le départ du client, puis elle est démontée.")

    # Combien de jours l'instance survit à la résiliation.
    #
    # TRENTE, parce que les CGV publiées le promettent (« les données restent
    # conservées trente jours avant suppression ») : le code s'aligne sur le
    # contrat, jamais l'inverse. L'ancienne valeur — sept jours, choisie pour
    # le coût serveur — contredisait la promesse : un client fidèle au
    # contrat aurait perdu ses données au huitième jour (relevé du 29/07,
    # contrôle des promesses). Si un jour le délai doit redescendre, on
    # change d'abord les CGV, on attend leur entrée en vigueur, PUIS ce
    # nombre.
    JOURS_APRES_RESILIATION = 30

    facture_ids = fields.One2many("account.move", "abonnement_contrat_id", "Factures")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nouveau") == "Nouveau":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "abonnement.contrat") or "ABO/%s" % int(time.time())
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Le montage de l'instance
    # ------------------------------------------------------------------
    DOSSIER = "/mnt/atelier/instances"

    def _slug(self):
        """Un identifiant technique tire du client. Il devient un nom de base
        ET un sous-domaine : il ne peut donc contenir que ce qui est valide
        dans les deux."""
        self.ensure_one()
        import re
        import unicodedata
        brut = (self.partner_id.name or self.partner_id.email or "client")
        brut = unicodedata.normalize("NFKD", brut).encode("ascii", "ignore").decode()
        brut = re.sub(r"[^a-zA-Z0-9]+", "-", brut).strip("-").lower()[:24] or "client"
        base, n = brut, 1
        # On ne prend jamais un identifiant deja pris : deux clients sur la
        # meme base serait la pire panne possible, et elle serait silencieuse.
        while self.search([("id", "!=", self.id),
                           ("instance_url", "ilike", "//%s." % base)], limit=1):
            n += 1
            base = "%s-%s" % (brut[:20], n)
        return base

    # ------------------------------------------------------------------
    # Zone Détresse : le code d'accès à la balise
    # ------------------------------------------------------------------
    @api.model
    def _generer_code_zone_detresse(self):
        """Un code lisible pour un humain, jamais devine, jamais deux fois.

        Exemple : ZD-7K3P-M9QX. Les caractères ambigus (0/O, 1/I) sont exclus.
        """
        import random
        alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
        for _ in range(50):
            code = "ZD-" + "-".join(
                "".join(random.choice(alphabet) for _ in range(4))
                for _ in range(2))
            if not self.search([("zone_detresse_code", "=", code)], limit=1):
                return code
        raise UserError(_("Impossible de générer un code Zone Détresse unique."))

    def action_monter_instance(self):
        """Depose la demande. La tour ne lance AUCUNE commande — c'est un
        script de l'hote qui ramasse. Ce script cree des bases de donnees :
        si un jour quelqu'un obtient le droit d'ecrire dans la tour, il ne doit
        pas heriter du droit d'en creer."""
        import json
        import os
        for rec in self:
            if rec.instance_etat == "montee":
                raise UserError(_("L'instance de ce contrat est deja montee."))
            if not rec.partner_id.email:
                raise UserError(_(
                    "Ce client n'a pas de courriel : impossible de lui creer "
                    "un compte, ni de lui envoyer ses acces."))
            slug = rec._slug()
            try:
                os.makedirs(rec.DOSSIER, exist_ok=True)
                chemin = os.path.join(rec.DOSSIER, "%s.json" % rec.name.replace("/", "-"))
                with open(chemin, "w") as f:
                    json.dump({"slug": slug, "email": rec.partner_id.email,
                               "nom": rec.partner_id.name,
                               "contrat": rec.name}, f)
            except OSError as exc:
                raise UserError(_(
                    "Impossible de deposer la demande (%s). Le volume "
                    "/mnt/atelier est-il monte ?") % exc) from exc
            rec.message_post(body=_(
                "Demande de montage deposee (identifiant technique : %s). "
                "Le serveur la ramasse dans la minute.") % slug)
        return True

    @api.model
    def _cron_expirer(self):
        """Avertir, puis supprimer. Ne leve jamais.

        Deux avertissements avant de detruire : a J-2 et le jour meme. Une
        suppression sans preavis, meme annoncee dans les conditions, se vit
        comme une panne — et c'est le dernier souvenir qu'on laisse.

        Ce cron NE SUPPRIME PAS la base lui-meme : la tour ne lance aucune
        commande. Il depose une demande de suppression que le script de l'hote
        ramasse, exactement comme pour le montage.
        """
        import json
        import os
        aujourd_hui = fields.Date.context_today(self)
        for c in self.search([("etat", "=", "actif"),
                              ("date_expiration", "!=", False)]):
            reste = (c.date_expiration - aujourd_hui).days
            if reste in (2, 0) and c.avertie_le != aujourd_hui:
                c._avertir_expiration(reste)
                c.avertie_le = aujourd_hui
            if reste > 0:
                continue
            # Le jour venu : on demande la suppression a l'hote.
            if not c._demander_suppression():
                continue
            c.write({"etat": "resilie", "instance_etat": "sans_objet",
                     "date_fin": aujourd_hui})
            c.message_post(body=_(
                "Duree de vie atteinte. Suppression de l'instance demandee."))

        # LES RESILIATIONS. Ce deuxieme passage manquait entierement.
        #
        # Trouve par Lois le 27/07, et c'est son constat le plus grave : le
        # premier passage ne regarde que les contrats a duree limitee, c'est-a-
        # dire les demos. Resilier un abonnement MENSUEL ne demontait donc
        # jamais rien. Ce n'est pas une course rare entre deux evenements,
        # c'est le chemin normal de tout client qui part — et la base, le
        # sous-domaine et le worker Odoo continuaient de tourner
        # indefiniment, pour un service que plus personne ne paie.
        for c in self.search([("etat", "=", "resilie"),
                              ("date_demontage", "!=", False),
                              ("date_demontage", "<=", aujourd_hui),
                              ("instance_etat", "=", "montee")]):
            if not c._demander_suppression():
                continue
            c.write({"instance_etat": "sans_objet", "date_demontage": False})
            c.message_post(body=_(
                "Delai apres resiliation ecoule. Suppression de l'instance "
                "demandee."))
        return True

    @api.model
    def _cron_livraisons_en_souffrance(self):
        """Un client qui a paye et n'a rien recu doit crier tout seul.

        Trouve par Lois : un paiement sans adresse de courriel fait lever le
        montage, l'exception est avalee, le remerciement se tait — et le
        contrat reste bloque en << a monter >> sans qu'aucun cron ne le
        reprenne. Le seul filet etait un courriel a l'administrateur. S'il est
        rate ou filtre, un client qui a paye reste sans rien, indefiniment, et
        plus rien ne le signale.

        Ce cron ne repare pas : il rend visible. Reparer tout seul un montage
        dont on ignore la cause d'echec, c'est le relancer en boucle.
        """
        limite = fields.Datetime.subtract(fields.Datetime.now(), hours=2)
        bloques = self.search([("etat", "=", "actif"),
                               ("instance_etat", "=", "a_monter"),
                               ("create_date", "<=", limite)])
        if not bloques:
            return True
        lignes = []
        for c in bloques:
            age = fields.Datetime.now() - fields.Datetime.to_datetime(c.create_date)
            manque = _("sans courriel") if not c.partner_id.email else _("cause inconnue")
            lignes.append(
                "<li><b>%s</b> — %s — paye depuis %s h — %s</li>" % (
                    c.name, c.partner_id.display_name or _("client inconnu"),
                    int(age.total_seconds() // 3600), manque))
        corps = _(
            "<p>%s contrat(s) paye(s) dont l'instance n'a jamais ete "
            "montee :</p><ul>%s</ul><p>Un contrat paye et non livre est la "
            "chose la plus grave qui puisse arriver a cette tour. Le montage "
            "se relance depuis la fiche du contrat, bouton "
            "<b>Monter l'instance</b>.</p>",
            len(bloques), "".join(lignes))
        if "tour.signal" in self.env:
            self.env["tour.signal"]._signaler(
                agent="Abonnements", titre=_("Livraison en souffrance"),
                corps_html=corps, ton="echec")
        return True

    def _programmer_demontage(self):
        """Poser la date a laquelle l'instance d'un client parti sera demontee.

        Pourquoi une date et pas une suppression immediate : le client vient
        peut-etre de se tromper de bouton, ou veut recuperer ses donnees. Et
        parce qu'une suppression declenchee par un webhook est une suppression
        qu'aucun humain n'a vue passer.
        """
        for rec in self:
            if rec.instance_etat == "montee" and not rec.date_demontage:
                rec.date_demontage = fields.Date.add(
                    fields.Date.context_today(rec),
                    days=rec.JOURS_APRES_RESILIATION)
                rec.message_post(body=_(
                    "Instance conservee jusqu'au %s, puis demontee.")
                    % rec.date_demontage)
            elif rec.instance_etat == "a_monter":
                # Resiliation pendant que le montage est en vol : on annule la
                # demande plutot que de livrer les acces a quelqu'un qui vient
                # de partir.
                rec.instance_etat = "sans_objet"
                rec.message_post(body=_(
                    "Montage annule : le contrat a ete resilie avant la "
                    "livraison."))

    def _demander_suppression(self):
        """Deposer la demande de suppression pour l'hote. Rend True si deposee.

        La tour ne supprime pas de base elle-meme : elle depose un fichier, et
        le script de l'hote le ramasse. Ce droit-la ne doit jamais s'heriter
        d'un acces a la tour.
        """
        import json
        import os
        self.ensure_one()
        nom = (self.instance_url or "").split("//")[-1].split(".")[0]
        if not nom:
            return False
        try:
            os.makedirs(self.DOSSIER, exist_ok=True)
            chemin = os.path.join(
                self.DOSSIER, "supprimer-%s.json" % self.name.replace("/", "-"))
            with open(chemin, "w") as f:
                json.dump({"slug": nom, "contrat": self.name,
                           "action": "supprimer"}, f)
        except OSError as exc:
            self.message_post(body=_("Suppression non demandee : %s") % exc)
            return False
        return True

    def _avertir_expiration(self, reste):
        self.ensure_one()
        if not self.partner_id.email:
            return
        quand = _("dans deux jours") if reste == 2 else _("aujourd'hui")
        corps = _("""
<div style="font-family:system-ui,-apple-system,'Segoe UI',sans-serif;line-height:1.65">
<p>Bonjour %(nom)s,</p>
<p>Votre acces d'essai a <a href="%(url)s">%(url)s</a> prend fin
<b>%(quand)s</b>.</p>
<p><b>Ce qui se passera :</b> l'instance et son contenu seront supprimes. Ce
n'est pas recuperable ensuite — on prefere le dire clairement plutot que de
le glisser dans des conditions generales.</p>
<p><b>Si vous voulez continuer</b>, repondez simplement a ce message : on
bascule votre instance en abonnement et <b>tout ce que vous avez saisi est
conserve</b>. Rien a refaire.</p>
<p><b>Si vous voulez partir</b>, vous n'avez rien a faire — et si vous voulez
emporter vos donnees, dites-le, on vous les envoie.</p>
<p>— Patrick, Code Nomi Nomi</p>
</div>""", nom=self.partner_id.name or "", url=self.instance_url or "",
            quand=quand)
        self.env["mail.mail"].sudo().create({
            "subject": _("Votre essai prend fin %s") % quand,
            "body_html": corps,
            "email_from": self._expediteur(),
            "email_to": self.partner_id.email,
            "auto_delete": False,
        }).send()
        self.message_post(body=_("Avertissement d'expiration envoye (%s).") % quand)

    @api.model
    def _cron_relever_instances(self):
        """Relit les comptes rendus et envoie les acces. Ne leve jamais."""
        import json
        import os
        dossier = os.path.join(self.DOSSIER, "resultats")
        if not os.path.isdir(dossier):
            return
        for fichier in os.listdir(dossier):
            if not fichier.endswith(".json"):
                continue
            ref = fichier[:-5].replace("-", "/")
            contrat = self.search([("name", "=", ref)], limit=1)
            if not contrat or contrat.instance_etat == "montee":
                continue
            try:
                with open(os.path.join(dossier, fichier)) as f:
                    r = json.load(f)
            except Exception:
                continue
            if not r.get("ok"):
                contrat.message_post(body=_(
                    "Montage impossible : %s") % r.get("erreur", "raison inconnue"))
                continue
            contrat.write({"instance_url": r["url"], "instance_etat": "montee"})
            contrat._envoyer_acces(r["login"], r["mdp"])
            # On efface le compte rendu APRES envoi : il contient un mot de
            # passe en clair, et il n'a plus aucune utilite une fois transmis.
            try:
                os.remove(os.path.join(dossier, fichier))
            except OSError:
                pass

    def _expediteur(self):
        """L'adresse d'envoi, calculee explicitement.

        Un courriel poste depuis le WEBHOOK part dans un contexte public :
        aucun utilisateur, donc Odoo ne sait pas de quelle adresse envoyer et
        leve. Celui du cron passait, lui — c'est ce qui rendait le defaut
        invisible jusqu'au premier vrai paiement.
        """
        icp = self.env["ir.config_parameter"].sudo()
        depuis = icp.get_param("mail.default.from") or "contact"
        domaine = icp.get_param("mail.catchall.domain") or "matourdecontrole.fr"
        if "@" not in depuis:
            depuis = "%s@%s" % (depuis, domaine)
        return self.env.company.email or depuis

    def _remercier(self):
        """Un mot tout de suite, avant les acces.

        Deux courriels et pas un seul, parce qu'ils ne font pas le meme
        travail : celui-ci part a la SECONDE du paiement, l'autre deux minutes
        plus tard quand l'instance repond. Entre les deux il y a un silence —
        et un silence apres avoir donne sa carte, meme court, c'est la ou
        l'inquietude s'installe. Autant l'occuper.

        Stripe envoie deja un recu. Un recu n'est pas un merci : il prouve une
        transaction, il ne dit rien a personne.
        """
        self.ensure_one()
        if not self.partner_id.email:
            return
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url")

        # ZONE DETRESSE : pas d'instance, un CODE d'acces a la balise.
        if self.zone_detresse_code:
            url = "%s/zone-detresse/zone-detresse.html?code=%s" % (
                (base or "").rstrip("/"), self.zone_detresse_code)
            corps = _("""
<div style="font-family:system-ui,-apple-system,'Segoe UI',sans-serif;line-height:1.65;color:#1e293b">
<p>Bonjour %(nom)s,</p>
<p><b>Merci.</b> Votre acces a la Zone Detresse est pret.</p>
<p>Ouvrez cette page sur votre telephone et ajoutez-la a vos favoris :</p>
<p style="background:#f1f5f9;border-radius:8px;padding:14px;word-break:break-all">
<a href="%(url)s">%(url)s</a></p>
<p>Le code d'acces (il est deja dans le lien, ne le partagez pas) :</p>
<p style="background:#f1f5f9;border-radius:8px;padding:14px;font-family:monospace;font-size:1.1em"><b>%(code)s</b></p>
<p>Bouton SOS, envoi de la position GPS, renvoi automatique toutes les 5 heures,
alerte par courriel apres 7 jours sans signal.</p>
<p style="font-size:.9em;color:#64748b"><b>Limite assumee</b> : ce service est
sans garantie de disponibilite continue (best effort). Resiliable a tout moment
: un mot a votre assistante, c'est fait sous 24 h ouvrees.</p>
<p>A tout de suite,<br/>Patrick — Code Nomi Nomi</p>
</div>""",
                nom=self.partner_id.name or "", url=url,
                code=self.zone_detresse_code)
            self.env["mail.mail"].sudo().create({
                "subject": _("Merci — votre Zone Détresse est prête"),
                "body_html": corps,
                "email_from": self._expediteur(),
                "email_to": self.partner_id.email,
                "auto_delete": False,
            }).send()
            return

        corps = _("""
<div style="font-family:system-ui,-apple-system,'Segoe UI',sans-serif;line-height:1.65;color:#1e293b">
<p>Bonjour %(nom)s,</p>
<p><b>Merci.</b> Vous venez de nous confier quelque chose de plus qu'un
paiement : vous pariez sur un outil que vous n'avez pas encore utilise. On en
a conscience, et on ne l'oublie pas.</p>
<p>Votre tour est en cours de preparation. <b>Vous recevrez son adresse et vos
acces d'ici deux a trois minutes</b>, a cette meme adresse. Si rien n'arrive
dans le quart d'heure, repondez a ce message : c'est qu'il y a un probleme, et
on le reglera.</p>
<p>En attendant, le <a href="%(guide)s">guide de la tour</a> explique chaque
module en une page. Il n'y a rien a installer, rien a configurer : tout se
fait depuis le navigateur.</p>
<p><b>Premier geste conseille : changez votre mot de passe.</b> Une fois
connecte, touchez votre initiale en haut a droite, puis Preferences, onglet
Securite du compte, bouton Changer le mot de passe. Ce n'est pas evident a
trouver, alors on vous le dit ici.</p>
<p>Votre tour parle <b>francais</b>. Pour l'anglais : votre initiale en haut
a droite, Preferences, champ Langue — l'anglais est deja charge, le
changement est immediat.</p>
<p>Offre souscrite : <b>%(offre)s</b> — %(montant)s EUR%(recurrence)s.</p>
<p style="font-size:.9em;color:#64748b"><b>Resiliable a tout moment</b> : un
mot a votre assistante ou une reponse a ce courriel, et c'est fait sous 24 h
ouvrees. Le mois entame reste du, et le service reste
accessible jusqu a son terme — on prefere le dire maintenant plutot que vous
le faire decouvrir au moment de partir.</p>
<p>A tout de suite,<br/>Patrick — Code Nomi Nomi</p>
</div>""",
            nom=self.partner_id.name or "",
            guide="%s/odoo/guides" % (base or "").rstrip("/"),
            offre=self.offre_id.name,
            montant=("%.2f" % self.montant).replace(".", ","),
            recurrence=_(" par mois") if self.offre_id.periode == "mois" else "")
        self.env["mail.mail"].sudo().create({
            "subject": _("Merci — votre tour de controle se prepare"),
            "body_html": corps,
            "email_from": self._expediteur(),
            "email_to": self.partner_id.email,
            "auto_delete": False,
        }).send()
        self.message_post(body=_("Remerciement envoye a %s.") % self.partner_id.email)

    def _envoyer_acces(self, login, mdp):
        """Le seul courriel qui contient un mot de passe. Il dit de le changer,
        et pourquoi : un mot de passe qui a voyage par courriel n'est plus un
        secret, il est une commodite de premiere connexion."""
        self.ensure_one()
        corps = _("""
<div style="font-family:system-ui,-apple-system,'Segoe UI',sans-serif;line-height:1.6">
<p>Bonjour %(nom)s,</p>
<p>Votre tour de controle est prete.</p>
<p style="background:#f1f5f9;border-radius:8px;padding:14px">
<b>Adresse :</b> <a href="%(url)s">%(url)s</a><br/>
<b>Identifiant :</b> %(login)s<br/>
<b>Mot de passe :</b> <code>%(mdp)s</code>
</p>
<p><b>Changez ce mot de passe des votre premiere connexion</b> (votre nom en
haut a droite, puis Preferences). Celui-ci a voyage par courriel : il vous
depanne aujourd'hui, il ne protege rien demain.</p>
<p>Tout est vide et vous appartient. Si vous ne savez pas par ou commencer,
ouvrez l'application <b>Guides</b> depuis votre tour : elle explique chaque
module en une page, en francais, sans jargon.</p>
<p>Et merci encore d'avoir fait ce pas. Une remarque, une question, une chose
qui ne marche pas : repondez a ce message, il arrive directement chez moi.</p>
<p>Une question, un probleme, une idee : repondez simplement a ce message.</p>
<p>— Patrick, Code Nomi Nomi</p>
</div>""", nom=self.partner_id.name or "", url=self.instance_url,
            login=login, mdp=mdp)
        self.env["mail.mail"].sudo().create({
            "subject": _("Votre tour de controle est prete"),
            "body_html": corps,
            "email_from": self._expediteur(),
            "email_to": self.partner_id.email,
            "auto_delete": False,
        }).send()
        self.message_post(body=_("Acces envoyes a %s.") % self.partner_id.email)

    def action_resilier(self):
        """Résilie chez Stripe ET dans la tour. L'un sans l'autre facture un
        client qui n'a plus rien, ou laisse un accès à quelqu'un qui ne paie
        plus. Les deux erreurs se découvrent tard et coûtent cher."""
        for rec in self:
            if rec.stripe_subscription_id:
                try:
                    _stripe(rec.env, "subscriptions/%s" % rec.stripe_subscription_id, "DELETE")
                except UserError as exc:
                    rec.message_post(body=_("Résiliation Stripe refusée : %s") % exc)
            rec.write({"etat": "resilie", "date_fin": fields.Date.context_today(rec)})
            rec.message_post(body=_("Contrat résilié par %s.") % rec.env.user.name)
            rec._programmer_demontage()


class AccountMove(models.Model):
    _inherit = "account.move"

    abonnement_contrat_id = fields.Many2one(
        "abonnement.contrat", "Contrat", index=True, copy=False,
        help="La facture vient d'un paiement d'abonnement encaissé par Stripe.")


class AbonnementEvenement(models.Model):
    """Les evenements Stripe deja traites. Une ligne, une fois, pour toujours.

    Deux failles critiques que Lois a trouvees le 27/07, et qui n'en font
    qu'une :

    - Le garde-fou anti-doublon de `_souscription` testait
      `objet.get("subscription")`. Pour une offre a paiement UNIQUE — celle a
      1 EUR, precisement celle qu'on utilise pour tester — ce champ est vide,
      donc le garde-fou ne s'executait jamais. Stripe qui reessaie, ou un
      renvoi manuel depuis son tableau de bord, creait un second contrat et
      montait une seconde instance pour un seul euro encaisse.
    - Le `search` puis le `create` ne sont pas atomiques, et
      `stripe_subscription_id` n'avait aucune contrainte d'unicite. Deux
      livraisons simultanees du meme evenement passaient toutes les deux.

    La reponse aux deux est la meme, et elle est en amont : **on retient
    l'identifiant de l'evenement**. Stripe garde le meme `event.id` a chaque
    reessai — c'est fait pour ca. La contrainte d'unicite est posee en base et
    non en Python : elle est le seul verrou qui tienne quand deux requetes
    arrivent en meme temps. Le code peut verifier avant, la base tranche.
    """

    _name = "abonnement.evenement"
    _description = "Evenement Stripe deja traite"
    _order = "id desc"

    stripe_event_id = fields.Char("Identifiant Stripe", required=True, index=True)
    type_ev = fields.Char("Type")
    resultat = fields.Char("Ce qui a ete fait")

    _sql_constraints = [
        ("event_unique", "unique(stripe_event_id)",
         "Cet evenement Stripe a deja ete traite."),
    ]


class AbonnementWebhook(models.AbstractModel):
    """Traitement des événements Stripe. Séparé du contrôleur pour être testable."""
    _name = "abonnement.webhook"
    _description = "Événements Stripe"

    @api.model
    def verifier_signature(self, corps, entete):
        """Sans cette vérification, n'importe qui offre des abonnements gratuits.

        Le webhook est une adresse publique : elle DOIT l'être, Stripe appelle
        depuis ses serveurs. Un faux message « paiement reçu » créerait un
        contrat actif et déclencherait la livraison d'une instance, sans qu'un
        euro soit entré. La signature est donc la seule chose qui distingue
        Stripe d'un inconnu.
        """
        # NOTRE secret d'abord, celui d'Odoo en repli.
        #
        # Chaque endpoint enregistré chez Stripe a SON propre secret. Celui du
        # fournisseur de paiement Odoo signe les événements envoyés à l'adresse
        # d'Odoo ; il ne signera jamais ceux envoyés à la nôtre. Utiliser le
        # mauvais fait échouer la vérification sur CHAQUE vrai paiement — et
        # comme on rejette silencieusement, on ne verrait qu'un webhook muet.
        secret = self.env["ir.config_parameter"].sudo().get_param(
            "abonnement.webhook_secret")
        if not secret:
            prov = self.env["payment.provider"].sudo().search(
                [("code", "=", "stripe")], limit=1)
            secret = prov.stripe_webhook_secret if prov else False
        if not secret:
            return False, "aucun secret de webhook configuré"
        try:
            parts = dict(p.split("=", 1) for p in (entete or "").split(","))
            horodatage, signature = parts["t"], parts["v1"]
        except Exception:
            return False, "en-tête de signature illisible"

        # Fenêtre de 5 minutes : au-delà, un message rejoué (capté sur le
        # réseau, ou dans un journal) ne doit plus être accepté.
        if abs(time.time() - int(horodatage)) > 300:
            return False, "message trop ancien"

        attendu = hmac.new(
            secret.encode(), ("%s.%s" % (horodatage, corps)).encode(), hashlib.sha256
        ).hexdigest()
        # Comparaison à temps constant : une comparaison normale fuit la
        # signature caractère par caractère.
        if not hmac.compare_digest(attendu, signature):
            return False, "signature invalide"
        return True, ""

    @api.model
    def traiter(self, evenement):
        type_ev = evenement.get("type")
        objet = (evenement.get("data") or {}).get("object") or {}

        # UN EVENEMENT NE SE TRAITE QU'UNE FOIS.
        #
        # On pose la ligne AVANT d'agir, pas apres : si le traitement plante a
        # mi-chemin, on veut savoir qu'on a deja essaye. Rejouer un demi-
        # montage est pire que ne rien faire — ca cree une deuxieme instance
        # a cote de la premiere, a moitie faite.
        ev_id = evenement.get("id")
        if ev_id:
            Journal = self.env["abonnement.evenement"].sudo()
            if Journal.search_count([("stripe_event_id", "=", ev_id)]):
                return "deja traite (%s)" % ev_id
            try:
                with self.env.cr.savepoint():
                    Journal.create({"stripe_event_id": ev_id, "type_ev": type_ev})
            except Exception:
                # La contrainte d'unicite a parle : une autre requete traite
                # le meme evenement en ce moment meme. C'est exactement le cas
                # que le `search` ci-dessus ne peut pas attraper.
                return "deja traite (%s, simultane)" % ev_id
        methode = {
            "checkout.session.completed": self._souscription,
            "invoice.paid": self._paiement,
            "invoice.payment_failed": self._echec,
            "customer.subscription.deleted": self._resiliation,
        }.get(type_ev)
        if not methode:
            return "ignoré (%s)" % type_ev
        return methode(objet)

    # ------------------------------------------------------------------
    def _client(self, objet):
        """Le partenaire, retrouvé ou créé. Jamais dupliqué sur le courriel."""
        email = (objet.get("customer_email")
                 or (objet.get("customer_details") or {}).get("email")
                 or objet.get("customer_email"))
        nom = ((objet.get("customer_details") or {}).get("name")
               or email or _("Client Stripe"))
        Partner = self.env["res.partner"].sudo()
        p = Partner.search([("email", "=ilike", email)], limit=1) if email else Partner
        if not p:
            p = Partner.create({"name": nom, "email": email, "customer_rank": 1})
        return p

    def _souscription(self, objet):
        code = (objet.get("metadata") or {}).get("code")
        offre = self.env["abonnement.offre"].sudo().search([("code", "=", code)], limit=1)
        if not offre:
            return "offre inconnue (%s)" % code

        Contrat = self.env["abonnement.contrat"].sudo()
        sub = objet.get("subscription")
        if sub and Contrat.search([("stripe_subscription_id", "=", sub)], limit=1):
            return "déjà enregistré"

        partner = self._client(objet)
        # Zone Détresse : on livre un CODE, pas une instance. Le code est
        # genere ici, envoye dans le remerciement, et valide par la balise.
        zd = offre.service == "zone_detresse"
        # Ni instance, ni code : un acces se donne, il ne se monte pas.
        sans_instance = offre.service in ("zone_detresse", "acces")
        vals = {
            "partner_id": partner.id,
            "offre_id": offre.id,
            "montant": offre.prix,
            "stripe_customer_id": objet.get("customer"),
            "stripe_subscription_id": sub,
            "instance_etat": "sans_objet" if sans_instance else (
                "a_monter" if offre.periode == "mois" else "sans_objet"),
            "date_expiration": (
                fields.Date.add(fields.Date.context_today(self),
                                days=offre.duree_jours)
                if offre.duree_jours else False),
        }
        if zd:
            vals["zone_detresse_code"] = (
                self.env["abonnement.contrat"]._generer_code_zone_detresse())
        contrat = Contrat.create(vals)
        contrat.message_post(body=_(
            "Souscription encaissée par Stripe. Offre : %(offre)s, %(prix)s €.",
            offre=offre.name, prix=offre.prix))
        # Le montage part TOUT DE SUITE. C'est le maillon entre « il a payé »
        # et « il a sa tour » : le faire attendre une intervention humaine,
        # c'est laisser un client payé devant une porte fermée.
        if contrat.instance_etat == "a_monter":
            try:
                contrat.action_monter_instance()
            except Exception as exc:  # noqa: BLE001
                # On n'interrompt pas : le paiement est encaissé, le contrat
                # doit exister même si le montage échoue. On le signale.
                contrat.message_post(body=_(
                    "Montage non demandé : %s. À relancer à la main.") % exc)
        contrat._remercier()
        # La cagnotte, tout de suite. Le releve tourne toutes les 4 h : sans
        # ca, on paie et l'accueil affiche encore zero pendant des heures —
        # ce qui donne l'impression que le paiement n'est pas passe, alors
        # qu'il l'est. C'est le seul moment ou le chiffre INTERESSE.
        try:
            self.env["stripe.releve"]._cron_relever()
        except Exception:  # noqa: BLE001 — un chiffre n'interrompt pas un paiement
            pass
        self._prevenir(contrat, nouveau=True)
        return "contrat %s créé" % contrat.name

    def _paiement(self, objet):
        contrat = self.env["abonnement.contrat"].sudo().search(
            [("stripe_subscription_id", "=", objet.get("subscription"))], limit=1)
        if not contrat:
            return "aucun contrat pour cet abonnement"
        if contrat.etat == "impaye":
            contrat.write({"etat": "actif"})
            contrat.message_post(body=_("Paiement reçu : le contrat redevient actif."))
        else:
            contrat.message_post(body=_(
                "Échéance payée (%s €).", (objet.get("amount_paid") or 0) / 100.0))
        return "paiement enregistré sur %s" % contrat.name

    def _echec(self, objet):
        contrat = self.env["abonnement.contrat"].sudo().search(
            [("stripe_subscription_id", "=", objet.get("subscription"))], limit=1)
        if not contrat:
            return "aucun contrat"
        contrat.write({"etat": "impaye"})
        contrat.message_post(body=_(
            "Paiement refusé. Stripe relance automatiquement — on ne coupe "
            "l'accès qu'après sa dernière tentative."))
        self._prevenir(contrat, nouveau=False)
        return "impayé sur %s" % contrat.name

    def _resiliation(self, objet):
        contrat = self.env["abonnement.contrat"].sudo().search(
            [("stripe_subscription_id", "=", objet.get("id"))], limit=1)
        if not contrat:
            return "aucun contrat"
        contrat.write({"etat": "resilie", "date_fin": fields.Date.context_today(contrat)})
        contrat.message_post(body=_("Abonnement résilié chez Stripe."))
        contrat._programmer_demontage()
        self._prevenir(contrat, nouveau=False)
        return "résilié %s" % contrat.name

    def _prevenir(self, contrat, nouveau):
        dest = self.env["ir.config_parameter"].sudo().get_param(
            "securite.destinataire") or "contact@matourdecontrole.fr"
        titre = (_("Nouvel abonné : %s") % contrat.partner_id.name if nouveau
                 else _("Abonnement %s : %s") % (contrat.name, contrat.etat))
        corps = _(
            "<p><b>%(titre)s</b></p>"
            "<p>Offre : %(offre)s — %(montant)s €<br/>"
            "Client : %(client)s (%(email)s)<br/>"
            "État : %(etat)s</p>"
            "<p>%(suite)s</p>",
            titre=titre, offre=contrat.offre_id.name, montant=contrat.montant,
            client=contrat.partner_id.name, email=contrat.partner_id.email or "—",
            etat=contrat.etat,
            suite=_("L'instance est à monter.") if contrat.instance_etat == "a_monter"
            else _("Rien à livrer."))
        # Meme piege que pour le remerciement : ce courriel part du WEBHOOK,
        # donc sans utilisateur, donc Odoo ne sait pas de quelle adresse
        # envoyer. Il avait ete corrige sur les courriels au client et oublie
        # sur ceux qui previennent Patrick — c'est-a-dire ceux qu'on ne voit
        # pas partir, donc ceux dont on ne remarque pas l'absence.
        icp = self.env["ir.config_parameter"].sudo()
        depuis = icp.get_param("mail.default.from") or "contact"
        domaine = icp.get_param("mail.catchall.domain") or "matourdecontrole.fr"
        if "@" not in depuis:
            depuis = "%s@%s" % (depuis, domaine)
        self.env["mail.mail"].sudo().create({
            "subject": "[Tour] %s" % titre,
            "body_html": corps,
            "email_from": self.env.company.email or depuis,
            "email_to": dest,
            "auto_delete": False,
        }).send()
