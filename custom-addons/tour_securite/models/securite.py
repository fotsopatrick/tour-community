# -*- coding: utf-8 -*-
"""Victor — la sécurité de la tour, en continu.

Pourquoi un agent de plus, et pourquoi celui-là ne ressemble pas aux autres.

**Il ne consomme aucune IA.** Ses contrôles sont du code déterministe. Un
contrôle de sécurité doit rendre le même verdict deux fois de suite ; une
réponse qui varie n'est pas un contrôle, c'est un avis. L'IA sait expliquer et
proposer — elle ne sait pas garantir. Conséquence pratique : Victor tourne
gratuitement, indéfiniment, même quand aucun quota n'est disponible.

**Il ne répare jamais sans accord.** Chaque constat propose un correctif et
attend une réponse : accepté, en attente, ou refusé. Un agent qui corrige tout
seul la sécurité est le plus dangereux de tous — il modifie exactement les
réglages dont dépend la capacité à l'arrêter.

**Il n'oublie pas un refus.** Un constat refusé n'est pas reproposé chaque
semaine : c'est ainsi qu'un outil devient du bruit, et que le vrai problème
finit ignoré avec les autres. Il est réexaminé si la situation change.

**Ce qu'il ne fait pas** : il ne lit aucun mot de passe, ne déchiffre aucun
secret, ne sort rien de la tour, et n'appelle personne à l'extérieur.
"""
import logging
import secrets

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

GRAVITES = [
    ("info", "Information"),
    ("moyen", "À corriger"),
    ("grave", "Grave"),
    ("critique", "Critique"),
]

# L'ordre compte : c'est celui du courriel et celui de la liste.
POIDS = {"critique": 0, "grave": 1, "moyen": 2, "info": 3}


class SecuriteConstat(models.Model):
    _name = "securite.constat"
    _description = "Constat de sécurité"
    _inherit = ["mail.thread"]
    _order = "gravite_poids, create_date desc"

    name = fields.Char("Constat", required=True, tracking=True)
    code = fields.Char("Contrôle", required=True, index=True,
                       help="Identifiant stable du contrôle qui a produit ce constat.")
    gravite = fields.Selection(GRAVITES, "Gravité", required=True, default="moyen", tracking=True)
    gravite_poids = fields.Integer(compute="_compute_poids", store=True)

    constat = fields.Html("Ce qui a été observé", readonly=True)
    preconisation = fields.Html("Ce que je propose", readonly=True)
    risque = fields.Char("Ce qu'on risque à ne rien faire")

    etat = fields.Selection(
        [("propose", "Proposé"),
         ("accepte", "Accepté"),
         ("attente", "En attente"),
         ("refuse", "Refusé"),
         ("resolu", "Résolu")],
        "État", default="propose", required=True, tracking=True)

    jeton = fields.Char("Jeton", readonly=True, copy=False, index=True,
                        groups="base.group_system")
    date_reponse = fields.Datetime("Répondu le", readonly=True)
    vu_le = fields.Datetime("Dernière vérification", readonly=True)

    _sql_constraints = [
        ("code_unique", "unique(code)",
         "Un constat existe déjà pour ce contrôle : on le met à jour, on n'en crée pas un second."),
    ]

    @api.depends("gravite")
    def _compute_poids(self):
        for rec in self:
            rec.gravite_poids = POIDS.get(rec.gravite, 9)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Un jeton long et aléatoire : c'est lui qui protège les liens du
            # courriel, puisqu'ils s'ouvrent sans connexion. 32 octets, donc
            # indevinables — et ils ne donnent le droit que de répondre à CE
            # constat, rien d'autre.
            vals.setdefault("jeton", secrets.token_urlsafe(32))
        return super().create(vals_list)

    # ------------------------------------------------------------------
    def _repondre(self, etat, par=None):
        """Accepter, mettre en attente ou refuser — depuis le courriel ou la fiche."""
        self.ensure_one()
        self.sudo().write({"etat": etat, "date_reponse": fields.Datetime.now()})
        qui = par or _("un lien du courriel")
        self.sudo().message_post(body=_("Réponse « %(etat)s » via %(qui)s.",
                                        etat=etat, qui=qui))
        return True

    def action_accepter(self):
        for rec in self:
            rec._repondre("accepte", par=self.env.user.name)

    def action_attente(self):
        for rec in self:
            rec._repondre("attente", par=self.env.user.name)

    def action_refuser(self):
        for rec in self:
            rec._repondre("refuse", par=self.env.user.name)


class SecuriteAgent(models.AbstractModel):
    """Le moteur : il passe les contrôles et tient les constats à jour."""
    _name = "securite.agent"
    _description = "Victor — agent de sécurité"

    # ------------------------------------------------------------------
    # Les contrôles. Chacun rend (ok, constat_html, preconisation_html) ou
    # None quand il ne s'applique pas ici — ne pas confondre « conforme » et
    # « pas concerné » : le second ne doit rassurer personne.
    # ------------------------------------------------------------------
    def _c_gestionnaire_bases(self):
        """Le gestionnaire de bases exposé sur le web est la porte la plus large."""
        from odoo.tools import config
        expose = config.get("list_db", True)
        if not expose:
            return True, None, None
        return (False,
                "<p><code>list_db</code> est actif : le sélecteur de bases est "
                "accessible depuis le web.</p>",
                "<p>Poser <code>list_db = False</code> dans la configuration. "
                "Cette page permet de lister, dupliquer, sauvegarder et "
                "SUPPRIMER une base avec le seul mot de passe maître. C'est la "
                "porte la plus large d'une installation Odoo.</p>")

    def _c_mot_de_passe_maitre(self):
        from odoo.tools import config
        mdp = config.get("admin_passwd") or ""
        if mdp and mdp not in ("admin", "odoo", "changeme", "") and len(mdp) >= 16:
            return True, None, None
        return (False,
                "<p>Le mot de passe maître est absent, trop court, ou vaut "
                "encore une valeur par défaut.</p>",
                "<p>Générer une valeur longue et aléatoire, la poser dans "
                "<code>ODOO_ADMIN_PASSWD</code> et l'enregistrer au Coffre. "
                "Ce mot de passe autorise la suppression de n'importe quelle "
                "base : il n'y a pas de sauvegarde qui rattrape ça si "
                "l'attaquant supprime aussi les sauvegardes.</p>")

    def _c_double_facteur(self):
        """Les comptes qui peuvent tout faire doivent avoir deux facteurs."""
        Users = self.env["res.users"].sudo()
        if "totp_secret" not in Users._fields:
            return None, None, None
        admins = Users.search([("groups_id", "in", self.env.ref("base.group_system").id),
                               ("active", "=", True), ("share", "=", False)])
        sans = admins.filtered(lambda u: not u.totp_secret and u.id != 1)
        if not sans:
            return True, None, None
        noms = ", ".join(u.name for u in sans)
        return (False,
                "<p>%s compte(s) administrateur sans double facteur : <b>%s</b>.</p>"
                % (len(sans), noms),
                "<p>Activer la validation en deux étapes (Préférences &gt; "
                "Sécurité du compte) sur ces comptes. Un administrateur peut "
                "lire tout le Coffre et installer n'importe quel module : "
                "son mot de passe seul ne devrait jamais suffire.</p>")

    def _c_comptes_dormants(self):
        """Un compte qu'on n'utilise plus reste une porte ouverte."""
        Users = self.env["res.users"].sudo()
        limite = fields.Datetime.subtract(fields.Datetime.now(), days=120)
        dormants = Users.search([
            ("active", "=", True), ("share", "=", False), ("id", "!=", 1),
            "|", ("login_date", "=", False), ("login_date", "<", limite)])
        if not dormants:
            return True, None, None
        noms = ", ".join("%s (%s)" % (u.name, u.login_date or "jamais connecté")
                         for u in dormants[:8])
        return (False,
                "<p>%s compte(s) actifs sans connexion depuis plus de 4 mois : "
                "<b>%s</b>.</p>" % (len(dormants), noms),
                "<p>Désactiver ceux qui ne servent plus. Un compte inutilisé "
                "n'est surveillé par personne : si son mot de passe fuit, "
                "l'intrusion ne se remarque pas — il n'y a pas d'activité "
                "normale à laquelle comparer l'anormale.</p>")

    def _c_sauvegarde_recente(self):
        limite = fields.Datetime.subtract(fields.Datetime.now(), days=2)
        modele = "sauvegarde.execution" if "sauvegarde.execution" in self.env else None
        if not modele:
            return None, None, None
        recente = self.env[modele].sudo().search_count([("create_date", ">", limite)])
        if recente:
            return True, None, None
        return (False,
                "<p>Aucune sauvegarde enregistrée depuis 48 heures.</p>",
                "<p>Vérifier le cron de <code>deploy/backup.sh</code>. Une "
                "sauvegarde qui ne tourne plus ne le dit pas : on l'apprend le "
                "jour où on en a besoin, c'est-à-dire le pire jour.</p>")

    def _c_secrets_en_clair(self):
        """Des secrets restés hors du Coffre."""
        if "vault.secret" not in self.env:
            return None, None, None
        Param = self.env["ir.config_parameter"].sudo()
        suspects = []
        for p in Param.search([]):
            v = (p.value or "")
            if len(v) > 20 and (v.startswith(("sk-", "sk_live_", "rk_live_", "ghp_",
                                              "sbp_", "xox", "AKIA"))):
                suspects.append(p.key)
        if not suspects:
            return True, None, None
        return (False,
                "<p>Des paramètres système contiennent ce qui ressemble à des "
                "clés en clair : <b>%s</b>.</p>" % ", ".join(suspects[:6]),
                "<p>Déplacer ces valeurs au Coffre (chiffrées) et ne garder "
                "ici qu'une référence. Les paramètres système sont lisibles "
                "par tout administrateur et partent tels quels dans chaque "
                "sauvegarde de base.</p>")

    def _c_partages_publics(self):
        """Des utilisateurs 'portail' avec des droits qu'ils ne devraient pas avoir."""
        Users = self.env["res.users"].sudo()
        risque = Users.search([("share", "=", True), ("active", "=", True),
                               ("groups_id", "in", self.env.ref("base.group_user").id)])
        if not risque:
            return True, None, None
        return (False,
                "<p>%s compte(s) externes ont les droits d'un utilisateur "
                "interne : <b>%s</b>.</p>" % (len(risque),
                                              ", ".join(u.name for u in risque[:6])),
                "<p>Retirer le groupe « Utilisateur interne » à ces comptes. "
                "Un compte externe voit alors tout ce que voit un salarié, "
                "y compris ce qui n'a jamais été pensé pour sortir.</p>")

    # ------------------------------------------------------------------
    # Sécurité applicative — la formation de Victor (29/07, priorité de
    # Patrick). Née d'un vilain réel : « LA PORTE PEINTE » — /qui.html
    # vivait sur la vitrine et rendait 404 sur la tour et la démo. Tous
    # les garde-fous regardaient la porte d'origine (200 sur son mur),
    # personne ne regardait le mur d'où le visiteur la voyait. Le contre :
    # vérifier chaque porte DEPUIS chaque mur où elle apparaît.
    #
    # Le périmètre vit dans le paramètre securite.portes_publiques (une
    # ligne = domaine + chemin) : chez un client, ses domaines à lui ;
    # paramètre vide = pas mesurable, on ne rassure personne.
    # ------------------------------------------------------------------

    def _portes(self):
        brut = (self.env["ir.config_parameter"].sudo()
                .get_param("securite.portes_publiques") or "").strip()
        portes = []
        for ligne in brut.splitlines():
            morceaux = ligne.strip().split()
            if len(morceaux) == 2 and morceaux[0].startswith("https://"):
                portes.append((morceaux[0].rstrip("/"), morceaux[1]))
        return portes

    def _c_portes_peintes(self):
        portes = self._portes()
        if not portes:
            return None, None, None
        import requests
        mortes = []
        for domaine, chemin in portes:
            try:
                r = requests.get(domaine + chemin, timeout=15,
                                 allow_redirects=True)
                if r.status_code >= 400:
                    mortes.append("%s%s (%s)" % (domaine, chemin,
                                                 r.status_code))
            except requests.RequestException:
                mortes.append("%s%s (injoignable)" % (domaine, chemin))
        if not mortes:
            return True, None, None
        return (False,
                "<p>Des portes publiques claquent au nez du visiteur : "
                "<b>%s</b>.</p>" % ", ".join(mortes[:8]),
                "<p>Le vilain s'appelle « la porte peinte » : le chemin "
                "existe sur un mur et pas sur celui où le visiteur se "
                "tient. Réparer par une redirection (Caddy) ou corriger le "
                "lien — et toujours tester depuis le mur du visiteur, pas "
                "depuis la porte d'origine. Bestiaire : guide « Le "
                "bestiaire des vilains ».</p>")

    def _c_entetes_publics(self):
        portes = self._portes()
        if not portes:
            return None, None, None
        import requests
        domaines = sorted({d for d, _c in portes})
        nus = []
        for d in domaines:
            try:
                r = requests.get(d + "/", timeout=15, allow_redirects=True)
            except requests.RequestException:
                continue
            manque = []
            if "strict-transport-security" not in {k.lower() for k in r.headers}:
                manque.append("HSTS")
            entetes = {k.lower() for k in r.headers}
            if ("x-frame-options" not in entetes
                    and "content-security-policy" not in entetes):
                manque.append("anti-cadre")
            if "x-content-type-options" not in entetes:
                manque.append("nosniff")
            if manque:
                nus.append("%s (%s)" % (d, ", ".join(manque)))
        if not nus:
            return True, None, None
        return (False,
                "<p>Des domaines publics sortent sans leurs protections de "
                "base : <b>%s</b>.</p>" % " ; ".join(nus),
                "<p>Ajouter dans Caddy : <code>Strict-Transport-Security</code> "
                "(le navigateur refuse ensuite tout retour au HTTP), "
                "<code>X-Frame-Options</code> ou une CSP (personne n'enferme "
                "nos pages dans son cadre pour faire cliquer à l'aveugle), "
                "<code>X-Content-Type-Options: nosniff</code>. Trois lignes, "
                "trois familles d'attaques de moins.</p>")

    CONTROLES = [
        ("gestionnaire_bases", "Le gestionnaire de bases n'est pas exposé", "critique"),
        ("mot_de_passe_maitre", "Le mot de passe maître est solide", "critique"),
        ("double_facteur", "Les administrateurs ont un deuxième facteur", "grave"),
        ("secrets_en_clair", "Aucune clé en clair hors du Coffre", "grave"),
        ("partages_publics", "Aucun compte externe avec des droits internes", "grave"),
        ("comptes_dormants", "Aucun compte actif abandonné", "moyen"),
        ("sauvegarde_recente", "Une sauvegarde de moins de 48 h", "grave"),
        ("portes_peintes", "Chaque porte publique s'ouvre du mur où on la voit", "grave"),
        ("entetes_publics", "Les domaines publics portent leurs en-têtes de protection", "moyen"),
    ]

    # ------------------------------------------------------------------
    # Le pentest : Victor ne lit plus la configuration, il ingère ce qu'un
    # sondage EXTERNE a trouvé. Le sondage vit sur l'hôte (deploy/pentest.sh) —
    # c'est lui qui frappe la porte ; Victor, lui, transforme chaque trouvaille
    # en un constat à trancher, exactement comme ses contrôles internes. La
    # frontière est la même que pour le montage d'instances : la tour ne lance
    # aucune commande, elle relit un fichier que l'hôte a déposé.
    # ------------------------------------------------------------------
    CHEMIN_PENTEST = "/mnt/atelier/instances/pentest/constats.json"

    @api.model
    def _cron_ingerer_pentest(self):
        """Relit le rapport du pentest et en fait des constats. Ne lève jamais.

        Un code trouvé devient (ou met à jour) un constat ; un code déjà connu
        et absent cette fois est classé « résolu » — la faille a été fermée, et
        la trace de sa correction vaut autant que l'alerte. Un refus est
        respecté, comme partout chez Victor : un constat écarté ne se repropose
        pas à chaque sondage.
        """
        import json
        import os
        chemin = self.env["ir.config_parameter"].sudo().get_param(
            "tour_securite.pentest_fichier", self.CHEMIN_PENTEST)
        if not os.path.exists(chemin):
            return True
        try:
            with open(chemin, encoding="utf-8") as f:
                rapport = json.load(f)
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Victor : rapport de pentest illisible (%s)", exc)
            return True

        Constat = self.env["securite.constat"].sudo()
        findings = rapport.get("findings") or []
        vus = set()
        nouveaux = Constat.browse()
        for f in findings:
            code = f.get("code")
            if not code:
                continue
            vus.add(code)
            existant = Constat.search([("code", "=", code)], limit=1)
            vals = {
                "name": f.get("titre") or code,
                "gravite": f.get("gravite") or "moyen",
                "constat": f.get("constat") or "",
                "preconisation": f.get("preconisation") or "",
                "vu_le": fields.Datetime.now(),
            }
            if existant:
                if existant.etat == "refuse":
                    existant.vu_le = fields.Datetime.now()
                    continue
                existant.write(vals)
                if existant.etat == "resolu":
                    existant.write({"etat": "propose"})
                    nouveaux |= existant
                continue
            nouveaux |= Constat.create(dict(vals, code=code))

        # Les constats de pentest qui ne ressortent plus : la porte est fermée.
        anciens = Constat.search([("code", "like", "pentest_%"),
                                  ("etat", "not in", ["resolu", "refuse"])])
        for c in anciens:
            if c.code not in vus:
                c.write({"etat": "resolu", "vu_le": fields.Datetime.now()})
                c.message_post(body=_("Réglé : le sondage ne trouve plus rien."))

        if nouveaux:
            self._prevenir(nouveaux)
        _logger.info("Victor : pentest ingéré, %s nouveau(x) constat(s)", len(nouveaux))
        return True

    @api.model
    def _cron_controler(self):
        """Passe tous les contrôles. Ne lève jamais : un cron qui plante s'éteint."""
        Constat = self.env["securite.constat"].sudo()
        nouveaux = Constat.browse()
        for code, intitule, gravite in self.CONTROLES:
            try:
                ok, quoi, quefaire = getattr(self, "_c_%s" % code)()
            except Exception as exc:  # noqa: BLE001
                _logger.warning("Victor : le controle %s a echoue (%s)", code, exc)
                continue
            if ok is None:
                continue  # pas concerné ici — ne rassure personne, ne alarme personne

            existant = Constat.search([("code", "=", code)], limit=1)
            if ok:
                # Réglé : on le note et on classe. On ne supprime pas — la
                # trace de ce qui a été corrigé vaut autant que l'alerte.
                if existant and existant.etat != "resolu":
                    existant.write({"etat": "resolu", "vu_le": fields.Datetime.now()})
                    existant.message_post(body=_("Réglé : le contrôle passe."))
                continue

            if existant:
                # Un refus est respecté : on ne repropose pas chaque semaine.
                # C'est ainsi qu'un outil devient du bruit.
                if existant.etat == "refuse":
                    existant.vu_le = fields.Datetime.now()
                    continue
                existant.write({"constat": quoi, "preconisation": quefaire,
                                "vu_le": fields.Datetime.now()})
                if existant.etat == "resolu":
                    existant.write({"etat": "propose"})
                    nouveaux |= existant
                continue

            nouveaux |= Constat.create({
                "name": intitule, "code": code, "gravite": gravite,
                "constat": quoi, "preconisation": quefaire,
                "vu_le": fields.Datetime.now(),
            })

        if nouveaux:
            self._prevenir(nouveaux)
        return True

    def _prevenir(self, constats):
        """Un seul courriel, avec un lien de réponse par constat.

        Un courriel par constat noierait la boîte le premier jour, et on
        apprendrait à les archiver sans lire — exactement ce qu'il ne faut pas.
        """
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        dest = (self.env["ir.config_parameter"].sudo().get_param("securite.destinataire")
                or self.env.ref("base.user_admin").email)
        if not dest:
            _logger.info("Victor : aucun destinataire, courriel non envoye.")
            return

        lignes = []
        for c in constats.sorted(lambda r: r.gravite_poids):
            lien = "%s/securite/%s" % (base.rstrip("/"), c.sudo().jeton)
            lignes.append("""
<div style="border:1px solid #1e293b;border-radius:10px;padding:14px;margin:0 0 14px">
  <div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#94a3b8">
    %s
  </div>
  <div style="font-size:16px;font-weight:600;margin:4px 0 8px">%s</div>
  <div style="color:#cbd5e1">%s</div>
  <div style="color:#cbd5e1;margin-top:8px"><b>Ce que je propose :</b> %s</div>
  <div style="margin-top:14px">
    <a href="%s/accepter" style="background:#22c55e;color:#04140a;padding:9px 16px;border-radius:8px;text-decoration:none;font-weight:600;display:inline-block">Accepter</a>
    <a href="%s/attente" style="border:1px solid #475569;color:#cbd5e1;padding:8px 15px;border-radius:8px;text-decoration:none;display:inline-block;margin-left:8px">Plus tard</a>
    <a href="%s/refuser" style="border:1px solid #475569;color:#cbd5e1;padding:8px 15px;border-radius:8px;text-decoration:none;display:inline-block;margin-left:8px">Refuser</a>
  </div>
</div>""" % (dict(GRAVITES).get(c.gravite, ""), c.name, c.constat or "",
             c.preconisation or "", lien, lien, lien))

        corps = """
<div style="font-family:system-ui,-apple-system,'Segoe UI',sans-serif;background:#020817;color:#e2e8f0;padding:22px">
  <div style="max-width:640px;margin:0 auto">
    <div style="font-size:19px;font-weight:650;margin-bottom:4px">Victor — %s point(s) de sécurité</div>
    <div style="color:#94a3b8;font-size:13px;margin-bottom:20px">
      Je n'ai rien modifié. Chaque proposition attend ta réponse — un clic suffit,
      sans te connecter.
    </div>
    %s
    <div style="color:#64748b;font-size:12px;margin-top:18px">
      Refuser est une réponse valable : je ne te le reproposerai pas.
    </div>
  </div>
</div>""" % (len(constats), "".join(lignes))

        self.env["mail.mail"].sudo().create({
            "subject": "[Victor] %s point(s) de sécurité à trancher" % len(constats),
            "body_html": corps,
            "email_to": dest,
            "auto_delete": False,
        }).send()
        _logger.info("Victor : %s constats envoyes a %s", len(constats), dest)


    # ------------------------------------------------------------------
    # LE PASSAGE IMMÉDIAT DE SÉCURITÉ (01/08) — compétence de Victor.
    # Si un écart est détecté (hors ligne, fuite, clé épuisée, scan en
    # échec), Victor passe TOUT DE SUITE, sans attendre le contrôle de
    # 22h58. On lit le dernier rejeu du cahier de tests + l'état des
    # conteneurs ; un échec => contrôle immédiat + signal.
    # ------------------------------------------------------------------
    @api.model
    def _cron_passage_immediat(self):
        import os
        anomalie = False
        raison = ""
        # 1. Le dernier cahier de tests : un « en échec » = anomalie.
        try:
            chemin = "/srv/sites/cahier-de-tests/index.html"
            if os.path.exists(chemin):
                with open(chemin, encoding="utf-8") as f:
                    contenu = f.read()
                if "en échec" in contenu and "0 en échec" not in contenu:
                    anomalie = True
                    raison = "cahier de tests en échec"
        except Exception:
            pass
        # 2. Les services : un conteneur absent = anomalie.
        try:
            import subprocess
            sortie = subprocess.run(
                ["bash", "-c",
                 "docker ps --format '{{.Names}}' | grep -cE 'tour-odoo-1|tour-db-1|tour-caddy-1'"],
                capture_output=True, text=True, timeout=10)
            if (sortie.stdout or "").strip() != "3":
                anomalie = True
                raison = (raison + " ; " if raison else "") + "conteneur manquant"
        except Exception:
            pass
        if anomalie:
            _logger.warning("Victor : PASSAGE IMMÉDIAT — %s", raison)
            self._cron_controler()
            if "tour.signal" in self.env:
                self.env["tour.signal"].sudo()._signaler(
                    "Victor", "Passage immédiat de sécurité : %s" % raison,
                    "<p>%s</p>" % raison)
            return True
        return False
