# -*- coding: utf-8 -*-
"""Le bus des agents.

Deux agents qui doivent se parler n'avaient aucun chemin : l'un rendait son
rapport à Patrick, l'autre attendait, et le premier ne savait jamais que le
second avait besoin de lui. Ce module ouvre le chemin, sans rien relâcher des
règles de la tour :

- **La trace d'abord, le broker ensuite.** Un message d'agent à agent est un
  fait d'armes : il doit survivre même si le broker tombe. On écrit le journal
  d'abord, on pousse sur Redis en bonus — jamais l'inverse.
- **Le journal ne s'efface pas.** Des agents qui peuvent nettoyer leurs
  échanges sont des agents qui peuvent effacer leurs dettes.
- **Patrick voit tout.** Le bus lui appartient : il n'est pas sur un réseau
  partagé, il est posé sur le serveur de la tour, et seul son compte le lit.
- **Le broker est un moyen, pas une fin.** Redis est choisi parce que c'est le
  plus léger (quelques Mo, zéro persistance, sous-milliseconde). S'il n'est
  pas joignable, la tour continue de fonctionner : seuls les messages
  host→tour attendent son retour.
"""
import datetime
import json
import unicodedata
import logging
import socket

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# La file des messages posés par l'HÔTE (les missions de l'atelier) et qui
# attendent que la tour les ramasse dans son journal.
# La file est PAR BASE (08/08) : la prod et la demo partagent le
# meme broker Redis, mais chacune ne ramasse que sa propre file —
# sinon elles se volent les messages mutuellement.
FILE_PREFIXE = "bus"
# La file des messages que la TOUR pousse pour d'éventuels écouteurs sur
# l'hôte. Le journal reste la mémoire ; le broker est juste le tuyau.
FILE_SORTANTE = "tour:bus:sortant"


class _Redis:
    """Un client RESP minimal, sans aucune dépendance.

    Toute la puissance de Redis n'est pas là : juste les cinq commandes dont
    le bus a besoin (PING, AUTH, LPUSH, RPOP, LLEN). Un client de plus à
    installer serait un conteneur de plus à maintenir ; cette classe tient
    dans trente lignes et fait le travail.
    """

    def __init__(self, adresse, port, mot_de_passe=""):
        self.sock = socket.create_connection((adresse, port), timeout=2)
        self._f = self.sock.makefile("rb")
        if mot_de_passe:
            self.commander("AUTH", mot_de_passe)

    def commander(self, *arguments):
        sortie = b"*%d\r\n" % len(arguments)
        for arg in arguments:
            octets = arg.encode() if isinstance(arg, str) else str(arg).encode()
            sortie += b"$%d\r\n%s\r\n" % (len(octets), octets)
        self.sock.sendall(sortie)
        return self._lire()

    def _lire(self):
        ligne = self._f.readline()
        if not ligne:
            raise ConnectionError("broker : connexion fermée")
        prefixe, donnee = ligne[:1], ligne[1:-2]
        if prefixe == b"+":
            return donnee.decode()
        if prefixe == b"-":
            raise RuntimeError(donnee.decode())
        if prefixe == b":":
            return int(donnee)
        if prefixe == b"$":
            longueur = int(donnee)
            if longueur < 0:
                return None
            contenu = self._f.read(longueur)
            self._f.read(2)
            return contenu.decode()
        if prefixe == b"*":
            return [self._lire() for _ in range(int(donnee))]
        raise RuntimeError("broker : réponse inattendue %r" % ligne)

    def fermer(self):
        try:
            self.sock.close()
        except Exception:  # noqa: BLE001
            pass


class TourBus(models.Model):
    _name = "tour.bus.message"
    _description = "Message entre agents de la tour"
    _order = "create_date desc"

    expediteur = fields.Char("De", required=True)
    destinataire = fields.Char("À", required=True)
    sujet = fields.Char("Sujet", required=True)
    corps = fields.Text("Message")
    jeton = fields.Char("Jeton", index=True, copy=False,
                        help="Identifiant unique, pour ne jamais ramasser deux "
                             "fois le même message du broker.")
    lu = fields.Boolean("Lu", default=False)

    # ---- L'ETAT DU MESSAGE (07/08) --------------------------------------
    # « lu » ne disait rien du travail : un message lu par un agent mort en
    # route restait lu pour toujours. Ces champs disent OU EN EST le message,
    # pas seulement s'il a ete vu.
    etat = fields.Selection(
        [("nouveau", "Nouveau"),
         ("pris", "Pris"),
         ("fait", "Fait"),
         ("echoue", "Echoue"),
         ("bloque", "Bloque")],
        string="Etat", default="nouveau", required=True, index=True,
        help="Nouveau : personne ne l'a encore attrape. Pris : un agent "
             "travaille dessus. Fait : c'est termine. Echoue : l'agent a "
             "rendu les armes, on reessaiera. Bloque : trop d'essais, "
             "Patrick doit regarder.")
    pris_le = fields.Datetime("Pris le", readonly=True, copy=False)
    pris_par = fields.Char("Pris par", readonly=True, copy=False,
                           help="Le nom de l'agent qui l'a attrape.")
    tentative = fields.Integer("Tentatives", default=0, readonly=True,
                               copy=False)
    reponse_a = fields.Many2one(
        "tour.bus.message", string="Repond a", ondelete="restrict",
        index=True, copy=False,
        help="Le message auquel celui-ci repond : c'est ce qui fait un fil.")
    mission_id = fields.Many2one(
        "atelier.mission", string="Mission nee de ce message",
        ondelete="set null", index=True, copy=False,
        help="La mission de l'atelier que ce message a declenchee. Sans ce "
             "lien, on ne savait pas si une demande avait vraiment donne "
             "du travail.")

    _sql_constraints = [
        ("jeton_unique", "unique(jeton)",
         "Ce message a déjà été ramassé une fois : on ne le compte pas deux."),
    ]

    # Ce qu'un agent a ECRIT ne bouge jamais (expediteur, destinataire, sujet,
    # corps, jeton, reponse_a) : c'est la trace. Ce qui bouge, c'est OU EN EST
    # le message. Les deux ne sont pas la meme chose et ne se melangent pas.
    CHAMPS_DE_TRAVAIL = {
        "lu", "etat", "pris_le", "pris_par", "tentative", "mission_id",
    }

    def write(self, vals):
        if vals and set(vals) <= self.CHAMPS_DE_TRAVAIL:
            return super().write(vals)
        raise UserError(_(
            "Les messages du bus ne se modifient pas : ils sont la trace de ce "
            "que les agents se sont dit. Seul leur etat peut changer."))

    def unlink(self):
        raise UserError(_(
            "Les messages du bus ne s'effacent pas : ils sont la trace de ce "
            "que les agents se sont dit."))

    def action_marquer_lu(self):
        self.ensure_one()
        self.write({"lu": True})
        return True

    # ------------------------------------------------------------------
    # Le broker
    # ------------------------------------------------------------------
    @api.model
    @api.model
    def _file_entrante_nom(self):
        """Le nom de la file d entree, par base de donnees."""
        base = self.env.cr.dbname or "tour"
        return "%s:%s:entrant" % (FILE_PREFIXE, base)

    def _param(self, cle, defaut=""):
        return self.env["ir.config_parameter"].sudo().get_param(cle, defaut)

    @api.model
    def _broker(self):
        """Un client vers le broker Redis, s'il est joignable. Sinon None."""
        adresse = self._param("tour_bus.redis_addr", "redis") or "redis"
        try:
            port = int(self._param("tour_bus.redis_port", "6379") or "6379")
        except (TypeError, ValueError):
            port = 6379
        mot_de_passe = self._param("tour_bus.redis_password", "") or ""
        try:
            return _Redis(adresse, port, mot_de_passe)
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------
    # L'API des agents
    # ------------------------------------------------------------------
    @api.model
    def _envoyer(self, expediteur, destinataire, sujet, corps=""):
        """Un agent écrit à un autre. Trace d'abord, broker ensuite."""
        msg = self.sudo().create({
            "expediteur": (expediteur or "?")[:40],
            "destinataire": (destinataire or "?")[:40],
            "sujet": (sujet or "sans objet")[:120],
            "corps": (corps or "")[:20000],
        })
        self._acheminer(msg)
        try:
            broker = self._broker()
            if broker is not None:
                try:
                    broker.commander(
                        "LPUSH", FILE_SORTANTE, json.dumps({
                            "expediteur": msg.expediteur,
                            "destinataire": msg.destinataire,
                            "sujet": msg.sujet,
                            "corps": msg.corps,
                            "date": fields.Datetime.now().isoformat(),
                        }))
                finally:
                    broker.fermer()
        except Exception:  # noqa: BLE001
            # Le journal est déjà écrit : le broker retombe sans rien perdre.
            _logger.warning("Bus : broker injoignable, message resté dans la tour.")
        return msg

    @api.model
    def _file_entrante(self):
        """Combien de messages de l'hôte attendent d'être ramassés."""
        broker = self._broker()
        if broker is None:
            return 0
        try:
            return int(broker.commander("LLEN", self._file_entrante_nom()) or 0)
        except Exception:  # noqa: BLE001
            return 0
        finally:
            broker.fermer()

    # ------------------------------------------------------------------
    # L'acheminement : comment un message atteint vraiment son destinataire.
    # ------------------------------------------------------------------
    @api.model
    def _acheminer(self, msg):
        """Fait arriver le message à son destinataire, pas seulement au journal.

        Le journal est la trace ; l'acheminement est la remise. Un message au
        bon destinataire qui dort dans un tableau n'est pas remis. Les règles
        d'acheminement sont écrites ICI, une seule fois, pour que n'importe
        quel agent sache comment faire demander quelque chose à quelqu'un :
        il écrit le bon nom dans « À » et le mécanisme fait le reste.

        - « Patrick »  : rien à faire — il voit tout dans le journal et le
          signal l'a déjà prévenu.
        - « Raphaël »  : une tâche [À CONFIRMER] naît dans le journal de la
          tour. C'est là que Raphaël (opencode) cherche le travail à sa
          connexion : la demande ne peut pas passer à côté.
        - Un membre de l'équipe avec un moteur : sa demande est confiée à
          l'atelier, pour qu'il la reçoive dans son prochain tour.
        - « Clone de Patrick » : PAS ENCORE BRANCHÉ. Le clone est une page
          sans réseau (la cage) ; il n'a pas encore de service qui lise le
          bus. Le message reste dans le journal, visible, en attendant que le
          vrai système existe. Le dire, plutôt que de prétendre l'avoir remis.
        """
        if "project.task" not in self.env:
            return
        vers = (msg.destinataire or "").strip().lower()
        if vers in ("raphael", "raphaël"):
            self._confier_a_raphael(msg)
        elif vers and "equipe.membre" in self.env:
            membre = self.env["equipe.membre"].sudo().search(
                # "=ilike" : egalite EXACTE mais insensible a la casse (aucun joker).
                # Avant "=" : un agent qui ecrivait "martha" au lieu de
                # "Martha" n etait JAMAIS route, sans la moindre alerte. Or la
                # doc de l outil parler donne les noms en minuscules.
                # Mesure du 13/08/2026 : message 1096 bloque a "nouveau".
                [("name", "=ilike", msg.destinataire.strip())], limit=1)
            if membre and membre.moteur and "atelier.mission" in self.env:
                self._confier_a_latelier(msg, membre)

    @api.model
    def _confier_a_raphael(self, msg):
        """La demande devient une tâche dans le journal que Raphaël lit."""
        Task = self.env["project.task"].sudo()
        projet = self.env["project.project"].sudo().search(
            [("name", "ilike", "ODOO")], limit=1)
        titre = _("[À CONFIRMER] Bus : %(de)s demande à Raphaël — %(sujet)s",
                  de=msg.expediteur, sujet=msg.sujet)[:120]
        if Task.search_count([("name", "=", titre)]):
            return
        Task.create({
            "name": titre,
            "project_id": projet.id or False,
            "description": _(
                "<p><b>%(de)s</b> → <b>Raphaël</b> (via le bus des agents) :</p>"
                "<pre style='white-space:pre-wrap'>%(corps)s</pre>",
                de=msg.expediteur, corps=msg.corps or ""),
        })

    @api.model
    def _confier_a_latelier(self, msg, membre):
        """La demande part à l'atelier pour le membre concerné."""
        Mission = self.env["atelier.mission"].sudo()
        # LA GARDE QUI NE PERD RIEN (07/08).
        # Avant : si l'atelier etait deja occupe pour ce moteur, on faisait
        # « return » et le message etait JETE, sans trace. Dix agents
        # partagent deepseek-agent, donc UNE mission coincee rendait les dix
        # muets. Mesure du 07/08 : deux missions bloquees depuis treize heures.
        # Maintenant : la mission est TOUJOURS creee. Si l'atelier travaille,
        # elle attend en brouillon et _cron_depiler_atelier l'enverra. Rien ne
        # disparait, et Patrick voit ce qui attend.
        occupe = self._atelier_occupe(membre.moteur)
        # QUI EXECUTE, ET PAS SEULEMENT AVEC QUOI (13/08/2026).
        # Avant : la mission ne portait que le MOTEUR. Or dix membres
        # partagent deepseek-agent : la mission "Pour Martha" est tombee
        # dans le bac de Wags, qui a poliment repondu que le droit du
        # travail n etait pas son metier. Une demande nominative arrivait
        # donc chez n importe qui, et l atelier chargeait la fiche
        # agents/deepseek-agent.md au lieu de agents/martha.md.
        # L atelier sait deja lire une directive "#!agent: <nom>" en
        # premiere ligne (atelier.sh, ligne 389). Le bus ne l ecrivait
        # jamais. Le slug ne garde que lettres et chiffres : la directive
        # n accepte que [a-z0-9_-] et les fiches s appellent martha.md,
        # chloe.md, jorel.md...
        brut = unicodedata.normalize("NFKD", membre.name or "")
        slug = "".join(c for c in brut.lower() if c.isascii() and c.isalnum())
        entete = ("#!agent: " + slug + chr(10)) if slug else ""
        mission = Mission.create({
            "name": _("Pour %(membre)s : %(sujet)s",
                      membre=membre.name, sujet=msg.sujet)[:120],
            "consigne": entete + _(
                "%(membre)s, voici un message du bus qui t'est adressé par "
                "%(de)s. Réponds-lui dans ton compte rendu.\n\n---\n%(corps)s",
                membre=membre.name, de=msg.expediteur, corps=msg.corps or ""),
            "moteur": membre.moteur,
        })
        # Un message du bus est une demande à faire, pas un brouillon à
        # attendre. Sans cet appel, la mission reste en `brouillon`, n'est
        # jamais déposée à l'atelier, et le destinataire ne la voit jamais —
        # une panne silencieuse : le message part (le journal le dit) mais on
        # n'a rien. On l'envoie donc tout de suite, comme la demande qu'on a
        # reçue. (Constats du 06/08 : la demande Breakout à Chloe dormait en
        # brouillon.)
        # Le message garde le lien vers la mission qu'il a fait naitre : sans
        # ce lien, on ne savait pas si une demande avait donne du travail.
        try:
            msg.sudo().write({"mission_id": mission.id})
        except Exception:  # noqa: BLE001
            _logger.warning("Bus : lien message->mission impossible", exc_info=True)
        if occupe:
            # L'atelier travaille deja pour ce moteur. La mission reste en
            # brouillon : elle partira toute seule des qu'il se libere.
            _logger.info(
                "Bus : atelier occupe pour %s, mission %s mise en attente",
                membre.moteur, mission.id)
            return mission
        try:
            mission.action_envoyer()
        except Exception as exc:  # noqa: BLE001
            # L'atelier inaccessible ne doit pas perdre la demande : on la
            # laisse en brouillon et on le signale, plutôt que de faire
            # croire qu'elle est partie.
            _logger.warning(
                "Bus : mission %s envoyée à l'atelier mais dépôt impossible "
                "(%s). Laissée en brouillon.", mission.id, exc)

    # ------------------------------------------------------------------
    # La ramasseuse
    # ------------------------------------------------------------------
    @api.model
    def _cron_drainer(self):
        """Ramène les messages posés par l'hôte dans le journal de la tour.

        Le broker est un tuyau sans mémoire : un message qui n'est pas ramassé
        est perdu. Cette ramasseuse tourne chaque minute, prend ce qui attend
        (dans la limite d'un lot), l'écrit dans le journal, et prévient Patrick
        — le bus lui appartient.
        """
        broker = self._broker()
        if broker is None:
            return 0
        ramasses = 0
        try:
            for _ in range(100):
                donnee = broker.commander("RPOP", self._file_entrante_nom())
                if not donnee:
                    break
                try:
                    d = json.loads(donnee)
                except (TypeError, ValueError):
                    continue
                jeton = (d.get("jeton") or "")[:64]
                if jeton and self.sudo().search_count([("jeton", "=", jeton)]):
                    continue
                msg = self.sudo().create({
                    "expediteur": (d.get("expediteur") or "?")[:40],
                    "destinataire": (d.get("destinataire") or "?")[:40],
                    "sujet": (d.get("sujet") or "sans objet")[:120],
                    "corps": (d.get("corps") or "")[:20000],
                    "jeton": jeton or False,
                })
                self._acheminer(msg)
                ramasses += 1
                if "tour.signal" in self.env:
                    try:
                        self.env["tour.signal"]._signaler(
                            agent="Bus",
                            titre=_("%(de)s → %(vers)s : %(sujet)s",
                                    de=(d.get("expediteur") or "?"),
                                    vers=(d.get("destinataire") or "?"),
                                    sujet=(d.get("sujet") or "sans objet")[:80]),
                            corps_html=_(
                                "<pre style='white-space:pre-wrap;font-size:13px'>"
                                "%(corps)s</pre>", corps=(d.get("corps") or "")[:2000]),
                            ton="attention")
                    except Exception:  # noqa: BLE001
                        pass
        except Exception:  # noqa: BLE001
            _logger.warning("Bus : ramassage interrompu", exc_info=True)
        finally:
            broker.fermer()
        if ramasses:
            _logger.info("Bus : %s message(s) ramassé(s) de l'hôte", ramasses)
        return ramasses

    # ------------------------------------------------------------------
    # LA FILE : qui prend quoi, et comment deux agents ne prennent jamais
    # le meme message.
    # ------------------------------------------------------------------
    # Les delais sont ecrits UNE fois, ici. Un nombre recopie a trois endroits
    # finit toujours par ne plus dire la meme chose aux trois endroits.
    MINUTES_AVANT_REPRISE = 15
    TENTATIVES_AVANT_BLOCAGE = 3

    @api.model
    def prendre(self, destinataire, agent=None, sujet=None):
        """Attrape UN message pour ce destinataire, et le marque « pris ».

        Le coeur tient en trois mots de SQL : FOR UPDATE SKIP LOCKED. La base
        pose un verrou sur la ligne choisie et fait SAUTER cette ligne a tout
        autre agent qui cherche au meme instant. Deux agents ne peuvent donc
        pas attraper le meme message — ce n'est pas une regle qu'on demande de
        respecter, c'est un mecanisme qui l'interdit.

        Rend le message, ou un enregistrement vide s'il n'y a rien a prendre.
        """
        conditions = ["etat = 'nouveau'", "destinataire = %s"]
        valeurs = [destinataire]
        if sujet:
            conditions.append("sujet ILIKE %s")
            valeurs.append("%" + sujet + "%")
        requete = ("SELECT id FROM tour_bus_message WHERE " +
                   " AND ".join(conditions) +
                   " ORDER BY id ASC FOR UPDATE SKIP LOCKED LIMIT 1")
        self.env.cr.execute(requete, valeurs)
        ligne = self.env.cr.fetchone()
        if not ligne:
            return self.browse()
        msg = self.sudo().browse(ligne[0])
        msg.write({
            "etat": "pris",
            "pris_le": fields.Datetime.now(),
            "pris_par": (agent or destinataire or "?")[:40],
            "tentative": msg.tentative + 1,
            "lu": True,
        })
        return msg

    def action_fait(self):
        """L'agent a fini. Le message ne reviendra pas."""
        for msg in self:
            msg.write({"etat": "fait"})
        return True

    def action_echoue(self):
        """L'agent a rendu les armes. La reprise le remettra dans la file."""
        for msg in self:
            msg.write({"etat": "echoue"})
        return True

    def action_rendre(self):
        """Remet un message dans la file, a la main, depuis l'ecran."""
        for msg in self:
            msg.write({"etat": "nouveau", "pris_le": False, "pris_par": False})
        return True

    @api.model
    def _cron_reprise(self):
        """Le filet : rien ne disparait en silence.

        Un agent peut mourir en plein travail — son conteneur s'eteint, le VPS
        manque de memoire, le moteur ne repond plus. Avant, son message restait
        « lu » pour l'eternite et le travail n'etait jamais fait, sans que
        personne ne s'en apercoive. Maintenant :

        - pris depuis plus de MINUTES_AVANT_REPRISE et jamais fini -> il
          retourne a « nouveau », quelqu'un d'autre le reprendra ;
        - au bout de TENTATIVES_AVANT_BLOCAGE essais -> « bloque », et une
          fiche Decision nait pour Patrick. Un message qui echoue trois fois
          n'est pas un incident, c'est une decision a prendre.
        """
        limite = fields.Datetime.now() - datetime.timedelta(
            minutes=self.MINUTES_AVANT_REPRISE)
        abandonnes = self.sudo().search([
            ("etat", "in", ("pris", "echoue")),
            "|", ("pris_le", "<", limite), ("pris_le", "=", False),
        ])
        repris = bloques = 0
        for msg in abandonnes:
            if msg.tentative >= self.TENTATIVES_AVANT_BLOCAGE:
                msg.write({"etat": "bloque"})
                bloques += 1
                self._alerter_blocage(msg)
            else:
                msg.write({"etat": "nouveau", "pris_le": False,
                           "pris_par": False})
                repris += 1
        if repris or bloques:
            _logger.info("Bus : %s message(s) remis dans la file, %s bloque(s)",
                         repris, bloques)
        return repris, bloques

    @api.model
    def _alerter_blocage(self, msg):
        """Un message bloque devient une Decision, pas une ligne de journal.

        Une trace dans un fichier de log, personne ne la lit. Une fiche dans le
        module Decisions, Patrick la voit.
        """
        if "decision.fiche" not in self.env:
            return
        titre = _("Bus bloque : %(de)s -> %(vers)s — %(sujet)s",
                  de=msg.expediteur, vers=msg.destinataire,
                  sujet=msg.sujet)[:120]
        Fiche = self.env["decision.fiche"].sudo()
        # On cree sur le nom EXACT ou on ne touche rien : jamais d'ilike qui
        # ecraserait la fiche de quelqu'un d'autre.
        if Fiche.search_count([("name", "=", titre)]):
            return
        corps = _(
            "<p>Ce message a echoue %(n)s fois de suite. Il ne repartira plus "
            "tout seul.</p><p><b>De</b> : %(de)s<br/><b>Pour</b> : %(vers)s"
            "<br/><b>Dernier agent</b> : %(qui)s</p>"
            "<pre style='white-space:pre-wrap'>%(corps)s</pre>",
            n=msg.tentative, de=msg.expediteur, vers=msg.destinataire,
            qui=msg.pris_par or "?", corps=(msg.corps or "")[:2000])
        valeurs = {"name": titre}
        for champ in ("decision", "contexte", "description"):
            if champ in Fiche._fields:
                valeurs[champ] = corps
                break
        try:
            Fiche.create(valeurs)
        except Exception:  # noqa: BLE001
            _logger.warning("Bus : fiche de blocage impossible", exc_info=True)

    # ------------------------------------------------------------------
    # LA FILE DE L'ATELIER : occupe ne veut pas dire perdu.
    # ------------------------------------------------------------------
    # Au-dela de ce delai, une mission « envoyee » cesse de bloquer la file.
    # On ne la tue pas : on arrete seulement de laisser un mort bloquer les
    # vivants. Sans cette borne, une mission coincee bloque POUR TOUJOURS —
    # c'est ce qui s'est passe les 6 et 7 aout.
    MINUTES_ATELIER_OCCUPE = 60

    @api.model
    def _atelier_occupe(self, moteur):
        """L'atelier travaille-t-il ENCORE pour ce moteur ?"""
        if not moteur or "atelier.mission" not in self.env:
            return False
        minutes = self.MINUTES_ATELIER_OCCUPE
        reglage = self.env["ir.config_parameter"].sudo().get_param(
            "tour_bus.minutes_atelier_occupe")
        if reglage:
            try:
                minutes = int(reglage)
            except (TypeError, ValueError):
                pass
        limite = fields.Datetime.now() - datetime.timedelta(minutes=minutes)
        return bool(self.env["atelier.mission"].sudo().search_count([
            ("moteur", "=", moteur),
            ("etat", "=", "envoyee"),
            ("create_date", ">=", limite),
        ]))

    @api.model
    def _cron_depiler_atelier(self):
        """Envoie les missions nees du bus qui attendent leur tour.

        Une mission creee pendant que l'atelier travaillait reste en brouillon.
        Sans ce cron, elle y resterait pour toujours — c'est deja arrive :
        vingt-six missions dormaient en brouillon au moment de la mesure, dont
        vingt sur le moteur claude depuis le 1er aout.
        """
        if "atelier.mission" not in self.env:
            return 0
        en_attente = self.sudo().search([
            ("mission_id", "!=", False),
            ("mission_id.etat", "=", "brouillon"),
        ], order="id asc")
        envoyees = 0
        for msg in en_attente:
            mission = msg.mission_id
            if self._atelier_occupe(mission.moteur):
                continue
            try:
                mission.action_envoyer()
                envoyees += 1
            except Exception:  # noqa: BLE001
                _logger.warning(
                    "Bus : impossible d'envoyer la mission %s qui attendait",
                    mission.id, exc_info=True)
        if envoyees:
            _logger.info("Bus : %s mission(s) en attente partie(s) a l'atelier",
                         envoyees)
        return envoyees
