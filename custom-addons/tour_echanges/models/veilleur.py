import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Le brouillon de relance est UNIQUE et generique : dix-sept invites muets
# ne fabriquent pas dix-sept textes identiques dans la bibliotheque.
RELANCE_TITRE = "Relance invité — ton accès à la tour t'attend"
RELANCE_CORPS = (
    "Salut [Prénom],\n\n"
    "Ton compte sur la tour de contrôle est prêt depuis quelques jours et "
    "je ne t'y ai pas encore vu :\n"
    "https://tour.matourdecontrole.fr\n\n"
    "Si tu as perdu tes accès, dis-le moi et je te les renvoie. Et si tu "
    "as cinq minutes, va juste dire bonjour à Chloe (la bulle en bas à "
    "droite) : c'est le meilleur premier pas.\n\n"
    "Si ce n'est pas le moment pour toi, dis-le moi aussi — c'est une "
    "réponse qui me rend service.")


class EchangeVeilleur(models.AbstractModel):
    """Jonathan — le tour quotidien du courrier qu'on doit.

    Chaque detecteur rend la liste des besoins qu'il vient d'ouvrir.
    Un detecteur qui echoue n'empeche pas les autres de passer, et le
    tout se termine par UN courriel de synthese — jamais un par
    trouvaille.
    """

    _name = "echange.veilleur"
    _description = "Jonathan — la veille du courrier"

    @api.model
    def _cron_veiller(self):
        icp = self.env["ir.config_parameter"].sudo()
        if not icp.get_param("tour_echanges.veille_active"):
            # La veille ne tourne que la ou on l'a armee : la tour mere.
            # Sur la demo ou une instance cliente, Jonathan se tait.
            return
        nouveaux = []
        try:
            with self.env.cr.savepoint():
                nouveaux += self._v_invites_muets()
        except Exception:
            _logger.exception("Échanges : détecteur des invités en échec")
        try:
            with self.env.cr.savepoint():
                nouveaux += self._v_apps_muettes()
        except Exception:
            _logger.exception("Échanges : détecteur des apps muettes en échec")
        try:
            with self.env.cr.savepoint():
                nouveaux += self._v_mails_bloques()
        except Exception:
            _logger.exception("Échanges : détecteur des mails bloqués en échec")
        etat_cle = "inconnue"
        try:
            with self.env.cr.savepoint():
                plus, etat_cle = self._v_cle_demo()
                nouveaux += plus
        except Exception:
            _logger.exception("Échanges : sonde de la clé démo en échec")
        pouls = self._pouls_demo()
        self._digest(nouveaux, pouls, etat_cle)

    # ------------------------------------------------------------------
    # Détecteurs
    # ------------------------------------------------------------------

    def _v_invites_muets(self):
        """Les comptes internes jamais connectes → une relance chacun.

        Quand l'invite finit par se connecter, sa fiche encore ouverte
        se ferme toute seule : le besoin a disparu, la liste doit le
        dire.
        """
        Besoin = self.env["echange.besoin"].sudo()
        crees = []
        comptes = self.env["res.users"].sudo().search([
            ("active", "=", True),
            ("share", "=", False),
            ("login", "not in", ("admin", "odoo", "default", "__system__")),
        ])
        for u in comptes:
            if u.has_group("base.group_system"):
                continue
            code = "invite_muet_%s" % u.login
            existant = Besoin.search([("code", "=", code)], limit=1)
            if u.login_date:
                if existant and existant.etat in ("a_rediger", "redige"):
                    existant.write({
                        "etat": "sans_suite",
                        "detail": "Connecté le %s — plus besoin de relance."
                                  % u.login_date,
                    })
                continue
            if existant:
                continue
            crees.append(Besoin.create({
                "name": "Relancer %s — invité jamais connecté"
                        % (u.name or u.login),
                "code": code,
                "type_dest": "invite",
                "qui": u.name or u.login,
                "origine": "Compte créé le %s, aucune connexion depuis."
                           % (u.create_date and u.create_date.date()),
                "etat": "redige",
                "message_id": self._brouillon_relance().id,
            }))
        return crees

    def _v_apps_muettes(self):
        """Une app livree a quelqu'un, sans qu'on le lui ait dit.

        Le correctif du 29/07 previent desormais le demandeur au moment ou sa
        mission se termine. Ce detecteur est la CEINTURE : il attrape ce que le
        correctif ne peut pas attraper — les apps livrees AVANT lui, et les
        courriels partis en erreur. Un correctif protege l'avenir ; un filet
        rattrape le passe.

        Le critere est mesure, pas suppose : on regarde si un courriel est
        reellement parti a cette adresse. Pas de trace = elle n'a rien recu,
        quoi qu'en dise le code.

        DEUX FAUX POSITIFS PAYES AU PREMIER PASSAGE (29/07) :
          - les apps construites par Chloe appartiennent au compte SYSTEME
            (« Copilote », login __system__) : cinq relances proposees pour
            prevenir un robot ;
          - la preuve de contact etait cherchee dans mail_notification, alors
            qu'un signal ecrit un mail.mail avec email_to et rien d'autre.
            Sankara, prevenu dix minutes plus tot, restait dans la liste.
        Un filet qui crie pour rien finit par ne plus etre lu.
        """
        Besoin = self.env["echange.besoin"].sudo()
        crees = []
        maison = (self.env["tour.signal"]._destinataire() or "").strip().lower()
        techniques = ("__system__", "odoobot", "admin", "odoo", "default")
        missions = self.env["atelier.mission"].sudo().search([
            ("etat", "=", "terminee"), ("url", "!=", False),
        ])
        for m in missions:
            qui = m.create_uid
            adresse = (qui.email or "").strip()
            if not adresse or adresse.lower() == maison:
                continue
            if (qui.login or "").lower() in techniques:
                continue
            if qui.has_group("base.group_system"):
                continue
            code = "app_muette_%s" % m.id
            if Besoin.search_count([("code", "=", code)]):
                continue
            self.env.cr.execute(
                "SELECT count(*) FROM mail_mail WHERE lower(email_to) = %s",
                (adresse.lower(),))
            if self.env.cr.fetchone()[0]:
                continue
            crees.append(Besoin.create({
                "name": "Prévenir %s — son app est en ligne et il ne le sait pas"
                        % (qui.name or qui.login),
                "code": code,
                "type_dest": "client",
                "qui": qui.name or qui.login,
                "origine": "Mission %s publiée sur %s — aucun courriel reçu "
                           "par cette personne." % (m.id, m.url),
                "detail": "Elle possède l'application, elle est abonnée à la "
                          "fiche, et la tour ne lui a jamais rien envoyé.",
                "etat": "a_rediger",
            }))
        return crees

    def _v_mails_bloques(self):
        """Les courriels d'agents coinces dans les bases clientes.

        Verifie le 29/07 : la base test patrick-kamdem n'a AUCUN serveur
        mail — quatre courriels d'agents en erreur, invisibles depuis la
        tour. Un client sur son instance ne recevait rien, et personne ne
        le voyait. Le detecteur lit chaque base surveillee (les instances
        montees + le parametre tour_echanges.bases_surveillees) et ouvre
        UN besoin par base des que des courriels y restent en exception.
        La demo n'est pas surveillee : son absence de SMTP est une
        decision, pas une panne. Quand la base se remet a envoyer, la
        fiche se ferme toute seule.
        """
        Besoin = self.env["echange.besoin"].sudo()
        crees = []
        param = (self.env["ir.config_parameter"].sudo()
                 .get_param("tour_echanges.bases_surveillees")
                 or "patrick-kamdem")
        bases = {b.strip() for b in param.split(",") if b.strip()}
        if "abonnement.contrat" in self.env:
            for c in self.env["abonnement.contrat"].sudo().search(
                    [("instance_etat", "=", "montee")]):
                slug = (c.instance_url or "").split("//")[-1].split(".")[0]
                if slug:
                    bases.add(slug)
        import odoo.sql_db
        for base in sorted(bases):
            if base == self.env.cr.dbname:
                continue
            try:
                connexion = odoo.sql_db.db_connect(base)
                with connexion.cursor() as cr:
                    cr.execute("SELECT count(*) FROM mail_mail "
                               "WHERE state = 'exception'")
                    n = cr.fetchone()[0]
            except Exception as exc:  # noqa: BLE001
                _logger.info("Échanges : base %s illisible (%s)", base, exc)
                continue
            code = "mails_bloques_%s" % base
            fiche = Besoin.search([("code", "=", code)], limit=1)
            ouverte = fiche and fiche.etat in ("a_rediger", "redige")
            if n:
                if ouverte:
                    continue
                vals = {
                    "name": "Base %s : %d courriel(s) d'agents coincés — "
                            "le client ne reçoit rien" % (base, n),
                    "type_dest": "client",
                    "qui": base,
                    "origine": "Lecture directe de la base : %d mail(s) en "
                               "erreur d'envoi." % n,
                    "detail": "Cette base n'a probablement pas de serveur "
                              "mail sortant. La solution de fond attend la "
                              "décision « Mails des instances clientes » "
                              "dans Décisions.",
                    "etat": "a_rediger",
                    "date": fields.Datetime.now(),
                }
                if fiche:
                    fiche.write(vals)
                else:
                    fiche = Besoin.create(dict(vals, code=code))
                crees.append(fiche)
            elif ouverte:
                fiche.write({"etat": "sans_suite",
                             "detail": "Plus aucun courriel en erreur le %s."
                                       % fields.Date.today()})
        return crees

    def _brouillon_relance(self):
        Message = self.env["tour.message"].sudo()
        brouillon = Message.with_context(active_test=False).search(
            [("name", "=", RELANCE_TITRE)], limit=1)
        if not brouillon:
            brouillon = Message.create({
                "name": RELANCE_TITRE,
                "categorie": "relance",
                "pour_qui": "Tout invité resté muet",
                "remarque": "Préparé par Jonathan. Adapter le prénom, "
                            "envoyer en privé.",
                "corps": RELANCE_CORPS,
            })
        return brouillon

    def _v_cle_demo(self):
        """La cle d'IA de la demo repond-elle encore ?

        La sonde interroge l'API avec la cle du Coffre — un appel qui ne
        coute rien. 401 = cle morte : un besoin s'ouvre et un signal part
        le jour meme. Un silence reseau n'est PAS une cle morte : on ne
        crie pas au loup sur une coupure.
        """
        if "vault.secret" not in self.env:
            return [], "inconnue"
        try:
            cle = (self.env["vault.secret"].sudo()._lire(
                "deepseek-api-key",
                motif="Jonathan vérifie la clé de la démo") or "").strip()
        except Exception:
            cle = ""
        if not cle:
            return [], "absente"
        import requests
        try:
            r = requests.get(
                "https://api.deepseek.com/models",
                headers={"Authorization": "Bearer %s" % cle}, timeout=20)
        except requests.RequestException:
            return [], "inconnue"
        Besoin = self.env["echange.besoin"].sudo()
        fiche = Besoin.search([("code", "=", "cle_demo_morte")], limit=1)
        ouverte = fiche and fiche.etat in ("a_rediger", "redige")
        if r.status_code == 401:
            if ouverte:
                return [], "morte"
            vals = {
                "name": "La clé DeepSeek de la démo est morte — "
                        "la remplacer au Coffre",
                "type_dest": "demo",
                "qui": "Patrick",
                "origine": "Sonde quotidienne : l'API DeepSeek répond 401 "
                           "avec la clé du Coffre.",
                "detail": "Sur la démo, Chloe explique déjà aux visiteurs "
                          "que la clé n'est pas fournie. Remplacer la fiche "
                          "deepseek-api-key du Coffre puis recopier le "
                          "paramètre sur la base de la démo.",
                "etat": "a_rediger",
                "date": fields.Datetime.now(),
            }
            if fiche:
                fiche.write(vals)
            else:
                fiche = Besoin.create(dict(vals, code="cle_demo_morte"))
            self._signal(
                "La clé DeepSeek de la démo est morte",
                "<p>La sonde du matin a trouvé la clé <b>invalide, révoquée "
                "ou expirée</b> (401). Les visiteurs de la démo voient "
                "l'explication, mais Chloe y est muette.</p>"
                "<p>Remplacer la fiche <b>deepseek-api-key</b> du Coffre, "
                "puis recopier le paramètre sur la base de la démo.</p>",
                ton="attention")
            return [fiche], "morte"
        if r.status_code == 200 and ouverte:
            fiche.write({
                "etat": "sans_suite",
                "detail": "Clé redevenue valide le %s." % fields.Date.today(),
            })
        return [], ("valide" if r.status_code == 200 else "inconnue")

    def _pouls_demo(self):
        """Le pouls de la demo, lu directement dans sa base.

        Meme mecanisme que le module Environnements : une connexion vers
        la base visee, pas d'extension PostgreSQL. Une demo illisible
        rend None — le digest le dira sans inventer de chiffres.
        """
        base = (self.env["ir.config_parameter"].sudo()
                .get_param("tour_echanges.base_demo") or "tour_test")
        if base == self.env.cr.dbname:
            return None
        try:
            import odoo.sql_db
            connexion = odoo.sql_db.db_connect(base)
            with connexion.cursor() as cr:
                cr.execute("SELECT count(*) FROM copilote_usage")
                total = cr.fetchone()[0]
                cr.execute("SELECT count(*) FROM copilote_usage "
                           "WHERE create_date >= now() - interval '24 hours'")
                jour = cr.fetchone()[0]
            return {"base": base, "total": total, "jour": jour}
        except Exception as exc:  # noqa: BLE001
            _logger.info("Échanges : démo %s illisible (%s)", base, exc)
            return None

    # ------------------------------------------------------------------
    # La synthèse
    # ------------------------------------------------------------------

    def _digest(self, nouveaux, pouls, etat_cle):
        """UN courriel, seulement les jours ou il y a du courrier."""
        if not nouveaux:
            return
        lignes = "".join(
            "<li>[%s] %s</li>" % (dict(
                b._fields["type_dest"].selection).get(b.type_dest,
                                                      b.type_dest), b.name)
            for b in nouveaux)
        corps = ("<p><b>%d</b> message(s) à envoyer aujourd'hui :</p>"
                 "<ul>%s</ul>" % (len(nouveaux), lignes))
        if pouls:
            corps += ("<p>La démo : <b>%d</b> échange(s) avec Chloe sur "
                      "24 h (%d au total). Clé d'IA : %s.</p>"
                      % (pouls["jour"], pouls["total"], etat_cle))
        else:
            corps += "<p>La démo n'a pas pu être lue aujourd'hui.</p>"
        corps += ("<p>Les brouillons attendent dans "
                  "<b>Messages &gt; Courrier à faire (Jonathan)</b>.</p>")
        ton = "attention" if etat_cle == "morte" else "fait"
        self._signal("Le courrier du jour — %d message(s) à envoyer"
                     % len(nouveaux), corps, ton=ton)

    def _signal(self, titre, corps_html, ton="fait"):
        if "tour.signal" not in self.env:
            return
        try:
            self.env["tour.signal"]._signaler(
                agent="Jonathan", titre=titre, corps_html=corps_html, ton=ton)
        except Exception:
            _logger.exception("Échanges : signal raté")
