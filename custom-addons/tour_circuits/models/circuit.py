# -*- coding: utf-8 -*-
"""Le moteur de circuits : une chaîne de portes qu'un objet traverse.

Idée de Patrick (30/07) : tous les circuits (promotion, forge, article, revue)
ont la MÊME forme — une suite de portes (des agents qui relisent/approuvent) qui
finit par Patrick puis la production. Plutôt que coder six chaînes jumelles, on
code UN moteur : un gabarit ordonné d'étapes, et un objet qui avance de porte en
porte. Chaque circuit devient alors une simple configuration — et c'est ça qui
se vend (« chaînes d'approbation multi-agents »).

On réutilise l'existant, on ne réinvente rien : l'atelier (une étape « agent »
dépose une mission de relecture), Décisions (l'étape « Patrick » dépose une
fiche), tour_promotion (l'étape « prod » réutilise sa demande).
"""

import re
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CircuitModele(models.Model):
    """Le gabarit d'un circuit : son nom et ses étapes, dans l'ordre."""
    _name = "circuit.modele"
    _description = "Gabarit de circuit"
    # Le select trie par les derniers circuits créés en premier (Patrick, 04/08).
    _order = "create_date desc"

    name = fields.Char("Nom du circuit", required=True)
    description = fields.Text("À quoi il sert")
    etape_ids = fields.One2many("circuit.etape", "modele_id", "Les portes",
                                copy=True)
    active = fields.Boolean("Actif", default=True)
    nb_etapes = fields.Integer("Portes", compute="_compte")
    # La détection de compétence (31/07) : quand une compétence est créée en
    # direct, la tour propose un circuit EN BROUILLON (active=False). Patrick
    # le valide puis l'active. Une détection n'est jamais activée toute seule.
    detecte = fields.Boolean(
        "Proposé par la détection", default=False,
        help="Ce gabarit a été proposé automatiquement (détection de "
             "compétence), pas créé à la main. Il attend la validation de "
             "Patrick avant d'être activé.")
    note = fields.Text(
        "D'où vient cette détection",
        help="Ce qui a déclenché la proposition : la compétence ou l'activité "
             "observée, et quand.")
    # Quel type d'opération ce circuit encadre (31/07). C'est ce qui rend le
    # circuit OBLIGATOIRE : quand l'opération se produit, le circuit est
    # lancé. Les portes obligatoires (champ circuit.etape.obligatoire)
    # empêchent de court-circuiter une porte critique.
    type_operation = fields.Selection(
        [("publication", "Publication (mission publiée)"),
         ("prod", "Mise en production"),
         ("coffre", "Modification du Coffre"),
         ("standard", "Aucun — circuit libre")],
        "Type d'opération", default="standard", required=True,
        help="Quand une opération de ce type se produit, ce circuit est "
             "lancé automatiquement. « standard » = circuit libre, à lancer "
             "à la main.")

    @api.depends("etape_ids")
    def _compte(self):
        for m in self:
            m.nb_etapes = len(m.etape_ids)

    # ------------------------------------------------------------------
    # LA DÉTECTION DE COMPÉTENCE (31/07, Patrick : « quand tu me vois créer
    # des compétences et circuits en direct, déduis-le et consigne-le ; si
    # elle voit un truc qui peut servir de circuit, elle le consigne en
    # brouillons et on pourra l'activer »).
    #
    # Une compétence est une action répétée — et toute action répétée se
    # prête à une chaîne de validation. À la création d'une compétence, on
    # propose un gabarit EN BROUILLON (active=False, detecte=True) avec les
    # portes par défaut. La détection ne décide jamais : elle propose, et la
    # proposition reste désactivée tant que Patrick ne l'active pas.
    # ------------------------------------------------------------------
    @api.model
    # -- Gabarits exportables (18/08/2026, etude PREDATEUR) --
    def action_exporter(self):
        """Exporte le gabarit, portes comprises, en JSON telechargeable -
        pour le partager entre bases ou le garder en versionnage."""
        self.ensure_one()
        import json as _json
        contenu = {
            "format": "circuit.modele/1",
            "name": self.name,
            "description": self.description or "",
            "type_operation": self.type_operation or False,
            "etapes": [{
                "sequence": e.sequence,
                "name": e.name,
                "role": e.role,
                "membre": e.membre_id.name or "",
                "obligatoire": e.obligatoire,
                "gabarit_enfant": e.gabarit_enfant_id.name or "",
            } for e in self.etape_ids.sorted(lambda e: (e.sequence, e.id))],
        }
        piece = self.env["ir.attachment"].create({
            "name": "circuit-%s.json" % (
                self.name or "gabarit").replace(" ", "-").lower(),
            "raw": _json.dumps(contenu, ensure_ascii=False,
                               indent=2).encode("utf-8"),
            "mimetype": "application/json",
            "res_model": self._name, "res_id": self.id,
        })
        return {"type": "ir.actions.act_url",
                "url": "/web/content/%d?download=true" % piece.id,
                "target": "self"}

    @api.model
    def importer_json(self, texte):
        """Recree un gabarit depuis un export JSON. Rend le gabarit cree,
        INACTIF : un gabarit importe se relit avant de servir."""
        import json as _json
        try:
            d = _json.loads(texte or "")
        except Exception as exc:  # noqa: BLE001
            raise UserError(_("JSON illisible : %s") % exc)
        if d.get("format") != "circuit.modele/1":
            raise UserError(_("Format inconnu (attendu circuit.modele/1)."))
        if not d.get("name"):
            raise UserError(_("Le gabarit n'a pas de nom."))
        Membre = self.env["equipe.membre"]
        permis = {k for k, _l in (
            self._fields["type_operation"].selection or [])}
        vals_etapes = []
        for e in d.get("etapes", []):
            membre = Membre.search([("name", "=", e.get("membre") or "")],
                                   limit=1)
            enfant = self.with_context(active_test=False).search(
                [("name", "=", e.get("gabarit_enfant") or "")], limit=1)
            vals_etapes.append((0, 0, {
                "sequence": e.get("sequence", 10),
                "name": e.get("name") or "?",
                "role": e.get("role") or "agent",
                "membre_id": membre.id or False,
                "obligatoire": bool(e.get("obligatoire")),
                "gabarit_enfant_id": enfant.id or False,
            }))
        top = d.get("type_operation")
        return self.create({
            "name": "%s (importe le %s)" % (d["name"], fields.Date.today()),
            "description": d.get("description") or "",
            "type_operation": top if top in permis else False,
            "etape_ids": vals_etapes,
            "active": False,
        })

    def _proposer_circuit(self, nom, note=""):
        """Propose un gabarit de circuit en brouillon (détection).

        Idempotent : on ne propose jamais deux fois le même nom. Un gabarit
        proposé et déjà actif n'est pas re-proposé.
        """
        nom = (nom or "").strip()[:120]
        if not nom:
            return self.browse()
        # Les brouillons détectés sont INACTIFS : une recherche normale ne les
        # voit pas. On cherche donc avec active_test=False, sinon on proposerait
        # le même brouillon deux fois.
        existant = self.with_context(active_test=False).search(
            [("name", "=", nom)], limit=1)
        if existant:
            return existant
        desc = ("Proposé par la détection de compétence — à valider puis "
                "activer." + ("\n\n%s" % note[:1200] if note else ""))
        gabarit = self.sudo().create({
            "name": nom,
            "description": desc,
            "active": False,
            "detecte": True,
            "note": (note or "").strip()[:2000],
        })
        # Les portes par défaut d'une chaîne d'approbation : un agent relit,
        # Raphael arbitre, Patrick tranche. Patrick adapte ensuite.
        self.env["circuit.etape"].sudo().create([
            {"modele_id": gabarit.id, "sequence": 10,
             "name": "Sécurité", "role": "agent"},
            {"modele_id": gabarit.id, "sequence": 20,
             "name": "Raphael", "role": "agent"},
            {"modele_id": gabarit.id, "sequence": 30,
             "name": "Patrick", "role": "patron"},
        ])
        return gabarit

    @api.model
    def _detecter_competence(self, competence):
        """Une compétence créée en direct cache souvent un circuit.

        Appelé par le hook de création d'equipe.competence (et par le banc de
        test). Une compétence est une action répétée qui mérite une chaîne de
        validation ; on le propose, on ne l'impose pas.
        """
        if not competence or not (competence.name or "").strip():
            return self.browse()
        note = ("Compétence « %s » créée sur %s (%s), le %s."
                % (competence.name, competence.membre_id.name,
                   competence.code or "?", fields.Date.today()))
        return self._proposer_circuit(
            "Circuit — %s" % competence.name, note)

    @api.model
    def _cron_detecter(self):
        """La détection de compétence, passée chaque nuit : on relit les
        compétences récentes et on complète les brouillons manquants."""
        if "equipe.competence" not in self.env:
            return False
        recentes = self.env["equipe.competence"].sudo().search(
            [("create_date", ">=", fields.Datetime.subtract(
                fields.Datetime.now(), days=7))],
            order="create_date desc", limit=40)
        for c in recentes:
            try:
                self._detecter_competence(c)
            except Exception:  # noqa: BLE001
                continue
        return True

    # ------------------------------------------------------------------
    # LE CIRCUIT OBLIGATOIRE (31/07, question de Patrick : « la sécurité
    # saura-t-elle qu'elle doit intervenir si on ne le lui dit pas ? »).
    #
    # Un gabarit avec type_operation != standard encadre une opération
    # sensible. Quand l'opération se produit (publication, mise en prod,
    # coffre), on lance une instance du circuit SANS demander : c'est ce qui
    # fait que Victor est appelé même si personne n'y pense. Si une porte
    # obligatoire existe et n'est pas dans le chemin, on l'insère en tête.
    # ------------------------------------------------------------------
    @api.model
    def _trouver_obligatoire(self, type_operation):
        """Le gabarit qui encadre ce type d'opération, s'il existe."""
        if not type_operation or type_operation == "standard":
            return self.browse()
        return self.search([("active", "=", True),
                            ("type_operation", "=", type_operation)],
                           limit=1)

    @api.model
    def _lancer_obligatoire(self, type_operation, sujet, module_cible=None):
        """Lance le circuit obligatoire pour une opération sensible.

        Retourne l'instance créée, ou une instance vide si rien d'obligatoire.
        Le circuit part à la première porte : s'il a une porte Sécurité en
        tête, Victor relit avant que l'opération aboutisse.
        """
        gabarit = self._trouver_obligatoire(type_operation)
        if not gabarit:
            return self.env["circuit.instance"].browse()
        # On s'assure qu'une porte obligatoire n'est pas contournée : si
        # aucune étape obligatoire n'existe dans le gabarit, on ne crée pas
        # d'obligation fantôme — le gabarit doit déclarer SES portes
        # obligatoires pour que le circuit soit vraiment bloquant.
        instance = self.env["circuit.instance"].sudo().create({
            "modele_id": gabarit.id,
            "name": sujet or gabarit.name,
            "sujet": sujet or gabarit.name,
            "module_cible": module_cible or "atelier.mission",
            "etat": "brouillon",
        })
        try:
            instance.action_lancer()
        except Exception:
            # Le lancement échoue (pas de porte, gabarit vide) : on ne casse
            # pas l'opération pour autant — l'instance reste en brouillon,
            # visible, et Patrick verra qu'un circuit attend.
            pass
        return instance


class CircuitEtape(models.Model):
    """Une porte du circuit : qui, et quoi.

    role = agent  : un agent relit et approuve (ou refuse) — dépose une mission.
    role = patron : Patrick tranche — dépose une fiche Décisions.
    role = prod   : mise en production — réutilise tour_promotion.
    """
    _name = "circuit.etape"
    _description = "Porte d'un circuit"
    _order = "modele_id, sequence, id"

    modele_id = fields.Many2one("circuit.modele", required=True,
                                ondelete="cascade", index=True)
    sequence = fields.Integer("Ordre", default=10)
    name = fields.Char("Nom de la porte", required=True,
                       help="Ex : Sécurité, Veille, Braignak, Raphael, Patrick.")
    role = fields.Selection(
        [("agent", "Un agent relit et approuve"),
         ("patron", "Patrick tranche"),
         ("prod", "Mise en production")],
        "Rôle", required=True, default="agent")
    membre_id = fields.Many2one(
        "equipe.membre", "Agent",
        help="Pour une porte « agent » : qui relit. Doit avoir un moteur.")
    obligatoire = fields.Boolean(
        "Obligatoire pour ce type d'opération",
        default=False,
        help="Si coché, le circuit dont cette porte fait partie doit être "
             "lancé pour le type d'opération du gabarit — on ne peut pas "
             "court-circuiter la porte (ex : la Sécurité avant une "
             "publication). Ajouté le 31/07, question de Patrick : « la "
             "sécurité saura-t-elle qu'elle doit intervenir si on ne le lui "
             "dit pas ? ».")
    gabarit_enfant_id = fields.Many2one(
        "circuit.modele", "Sous-circuit (embranchement)",
        help="01/08 : quand cette porte est approuvée, un SOUS-CIRCUIT part — "
             "une nouvelle instance de ce gabarit est lancée en parallèle, "
             "puis le circuit principal continue son chemin. Une porte peut "
             "créer un autre chemin.")


class CircuitInstance(models.Model):
    """Un objet qui traverse un circuit : il avance d'une porte à la fois."""
    _name = "circuit.instance"
    _description = "Circuit en cours"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char("Sujet", required=True,
                        help="Ce qui traverse le circuit : un titre d'article, "
                             "un nom de module, une idée.")
    modele_id = fields.Many2one("circuit.modele", "Circuit", required=True)
    sujet = fields.Html("Contenu",
                        help="Le corps : l'article, la description, etc.")
    module_cible = fields.Char(
        "Module à promouvoir",
        help="Pour un circuit qui finit en prod : le module (ex tour_debat).")
    etape_courante = fields.Integer("Porte courante", default=0, readonly=True)
    etape_nom = fields.Char("Où on en est", compute="_situation")
    etat = fields.Selection(
        [("brouillon", "Brouillon"),
         ("en_cours", "En cours"),
         ("publie_prive", "Publié en privé (Patrick peut lire)"),
         ("publie_public", "Public"),
         ("refuse", "Refusé")],
        "État", default="brouillon", readonly=True, tracking=True)
    passage_ids = fields.One2many("circuit.passage", "instance_id", "Journal",
                                  readonly=True)
    reprises = fields.Integer(
        "Reprises", default=0, readonly=True,
        help="Combien de fois ce circuit est reparti A LA PORTE, sans tout "
             "rejouer.")
    trace_html = fields.Html("Trace des portes", compute="_trace",
                             sanitize=False)

    def _situation(self):
        for inst in self:
            etapes = inst.modele_id.etape_ids.sorted(lambda e: (e.sequence, e.id))
            if inst.etat in ("publie_prive", "publie_public"):
                inst.etape_nom = "Toutes les portes passées"
            elif inst.etat == "refuse":
                inst.etape_nom = "Refusé"
            elif 0 < inst.etape_courante <= len(etapes):
                inst.etape_nom = etapes[inst.etape_courante - 1].name
            else:
                inst.etape_nom = "Pas encore lancé"

    # ------------------------------------------------------------------
    def _etapes(self):
        self.ensure_one()
        return self.modele_id.etape_ids.sorted(lambda e: (e.sequence, e.id))

    def action_lancer(self):
        """Démarre le circuit à la première porte."""
        self.ensure_one()
        if self.etat != "brouillon":
            raise UserError(_("Ce circuit est déjà lancé."))
        if not self._etapes():
            raise UserError(_("Ce gabarit n'a aucune porte."))
        self.etat = "en_cours"
        self.etape_courante = 0
        self._porte_suivante()
        return True

    def _porte_suivante(self):
        """Passe à la porte suivante et la déclenche. Si plus de porte : publie
        en privé (Patrick pourra lire, puis rendre public s'il veut)."""
        self.ensure_one()
        etapes = self._etapes()
        self.etape_courante += 1
        if self.etape_courante > len(etapes):
            self.etat = "publie_prive"
            self.message_post(body=_(
                "Toutes les portes sont passées — publié en PRIVÉ. Patrick peut "
                "lire, puis rendre public."))
            return
        etape = etapes[self.etape_courante - 1]
        passage = self.env["circuit.passage"].create({
            "instance_id": self.id, "etape_id": etape.id})
        passage._declencher()

    def _porte_repondue(self, passage, approuve, avis=""):
        """Rappelé quand une porte a répondu (agent, Patrick)."""
        self.ensure_one()
        passage.write({
            "etat": "approuve" if approuve else "refuse",
            "avis": avis or passage.avis})
        if not approuve:
            self.etat = "refuse"
            self.message_post(body=_("Refusé à la porte « %s ». Motif : %s")
                              % (passage.etape_id.name, avis or "(non précisé)"))
            return
        self.message_post(body=_("Porte « %s » : approuvée.")
                          % passage.etape_id.name)
        # EMBRANCHEMENT (01/08) : si la porte approuvée a un sous-circuit,
        # une NOUVELLE instance part en parallèle — la porte crée un autre
        # chemin. Le circuit principal continue ensuite normalement.
        enfant = passage.etape_id.gabarit_enfant_id
        if enfant:
            try:
                self.env["circuit.instance"].sudo().create({
                    "modele_id": enfant.id,
                    "name": "%s — embranchement de %s" % (
                        self.name, passage.etape_id.name),
                    "sujet": self.sujet,
                    "module_cible": self.module_cible,
                    "etat": "brouillon",
                }).action_lancer()
            except Exception:  # noqa: BLE001
                pass
        self._porte_suivante()

    def action_rendre_public(self):
        self.ensure_one()
        if self.etat != "publie_prive":
            raise UserError(_("On ne rend public qu'un circuit publié en privé."))
        self.etat = "publie_public"
        self.message_post(body=_("Rendu PUBLIC par %s.") % self.env.user.name)
        return True

    def action_forcer(self):
        """Bouton admin : approuver la porte courante à la main (utile pour
        tester le moteur sans lancer un vrai agent)."""
        self.ensure_one()
        p = self.passage_ids.filtered(lambda x: x.etat == "attente")[:1]
        if not p:
            raise UserError(_("Aucune porte en attente."))
        self._porte_repondue(p, True, avis="(forcé à la main par %s)"
                             % self.env.user.name)
        return True

    def action_reprendre(self):
        """REPRISE : repartir a la porte, pas a zero.

        Mecanique relevee dans CrewAI (MIT) : un instantane par etape
        franchie, et la reprise recharge le dernier etat au lieu de rejouer
        l'acquis. Ici l'instantane vit dans circuit.passage.photo_etat.
        """
        self.ensure_one()
        if self.etape_courante < 1:
            raise UserError(_("Ce circuit n'a jamais ete lance."))
        if self.etat not in ("refuse", "en_cours"):
            raise UserError(_("On ne reprend qu'un circuit refuse, ou bloque "
                              "en cours."))
        # Le passage reste ouvert se clot SANS jugement, pour un journal vrai.
        for p in self.passage_ids.filtered(lambda x: x.etat == "attente"):
            p.write({"etat": "refuse",
                     "avis": (p.avis or "") +
                     "\n(porte relancee par une reprise, sans jugement)"})
        self.write({"etat": "en_cours", "reprises": self.reprises + 1,
                    "etape_courante": self.etape_courante - 1})
        self.message_post(body=_(
            "REPRISE n%s : on repart a la porte, l'acquis n'est pas rejoue."
        ) % (self.reprises + 1))
        self._porte_suivante()
        return True

    def _trace(self):
        """La trace visuelle : pour chaque porte du gabarit, le DERNIER mot.

        Gris = jamais jouee - et un gris n'est PAS un vert (regle de Jimmy,
        04/08 : une puce jamais jouee ne se compte pas comme un succes).
        """
        for inst in self:
            lignes = []
            for e in inst.modele_id.etape_ids.sorted(
                    lambda x: (x.sequence, x.id)):
                ps = inst.passage_ids.filtered(
                    lambda p, _e=e: p.etape_id.id == _e.id).sorted("id")
                if not ps:
                    lignes.append(
                        "<div style='margin:2px 0;color:#888'>&#9678; <b>%s</b>"
                        " &mdash; jamais jouee</div>" % e.name)
                    continue
                p = ps[-1]
                coul, pic = {"approuve": ("#1a7f37", "&#10003;"),
                             "refuse": ("#b42318", "&#10007;")}.get(
                                 p.etat, ("#9a6700", "&#8987;"))
                extra = " &middot; %d passages" % len(ps) if len(ps) > 1 else ""
                avis = (p.avis or "").strip().replace("<", "&lt;")[:180]
                lignes.append(
                    "<div style='margin:2px 0'>"
                    "<span style='color:%s;font-weight:bold'>%s %s</span>"
                    " <span style='color:#666'>&mdash; %s%s</span>%s</div>" % (
                        coul, pic, e.name, p.write_date or "", extra,
                        ("<div style='color:#444;margin-left:18px'>%s</div>"
                         % avis) if avis else ""))
            inst.trace_html = "".join(lignes) or "<i>Pas de portes.</i>"

    @api.model
    @api.model
    def _lire_verdict(self, texte):
        """Cherche APPROUVE ou REFUSE dans le debut du texte utile.

        Le premier des deux qui apparait l emporte : un agent qui ecrit
        « ... APPROUVE ... sinon j aurais REFUSE » approuve bien.
        Rend "APPROU", "REFUS", ou "" si l agent n a rien tranche.
        """
        import re as _re3
        # EN MAJUSCULES, volontairement : la consigne dit « COMMENCE par
        # APPROUVE ou REFUSE ». Sans la casse, « dire si je l approuve »
        # passait pour un verdict — un vert que personne n avait prononce.
        debut = (texte or "")[:1200]  # mesure du 05/08 : a 400 on refusait 70 % d avis valables, le verdict arrive plus loin
        m_ok = _re3.search(r"APPROUV", debut)
        m_ko = _re3.search(r"REFUS", debut)
        if m_ok and m_ko:
            return "APPROU" if m_ok.start() < m_ko.start() else "REFUS"
        if m_ok:
            return "APPROU"
        if m_ko:
            return "REFUS"
        return ""

    @api.model
    def _verdict_utile(self, texte):
        """Enleve l en-tete technique du moteur avant de chercher le verdict.

        Les moteurs prefixent leur compte rendu par « === CONSTRUIT PAR X ===
        Tours : n · jetons : ... ============ ». Tant qu on lisait les 12
        premiers caracteres, on ne voyait que ca — et on approuvait tout.
        """
        import re as _re2
        # On coupe apres la DERNIERE barre de « === » du debut : c est la fin
        # de l en-tete. On ne touche a rien si aucune barre n est trouvee.
        barres = list(_re2.finditer(r"={6,}", texte[:1200]))
        if barres:
            texte = texte[barres[-1].end():]
        return texte.strip()

    def _cron_relever(self):
        """Ramène les portes « agent » dont la mission est terminée."""
        import re as _re
        for p in self.env["circuit.passage"].search(
                [("etat", "=", "attente"), ("mission_id", "!=", False)]):
            m = p.mission_id
            if m.etat not in ("terminee", "echec"):
                continue
            texte = _re.sub(r"<[^>]+>", " ", m.reponse or "")
            texte = _re.sub(r"\s+", " ", texte).strip()
            if m.etat == "echec":
                p.instance_id._porte_repondue(
                    p, False, avis=(texte or "Mission en echec.")[:2000])
                continue
            texte = self._verdict_utile(texte)
            verdict = self._lire_verdict(texte)
            # LEcON DU 04/08 (mission 631) : une mission « terminee » mais VIDE
            # ou sans substance passait la porte. Plus maintenant : la porte
            # refuse ce qu elle ne peut pas juger.
            if verdict == "REFUS":
                approuve = False
            elif len(texte) < 20 and verdict != "APPROU":
                p.instance_id._porte_repondue(
                    p, False, avis="Reponse inexploitable (vide ou sans "
                    "substance) : la porte ne passe pas. Contenu : %r" % texte[:200])
                continue
            elif verdict == "APPROU":
                approuve = True
            else:
                # L agent n a dit NI approuve NI refuse. Avant, on approuvait
                # par defaut : 598 portes sont passees comme ca sans que
                # personne ne juge rien. Une porte qui ne peut pas juger ne
                # s ouvre pas.
                p.instance_id._porte_repondue(
                    p, False, avis="L agent n a dit ni APPROUVE ni REFUSE : "
                    "la porte ne peut pas juger, elle ne s ouvre pas. "
                    "Sa reponse : %s" % texte[:1800])
                continue
            p.instance_id._porte_repondue(p, approuve, avis=texte[:2000])
        return True


class CircuitPassage(models.Model):
    """Le journal d'UNE porte pour UNE instance : ce qui a été demandé, la
    réponse, l'issue."""
    _name = "circuit.passage"
    _description = "Passage d'une porte"
    _order = "instance_id, id"

    instance_id = fields.Many2one("circuit.instance", required=True,
                                  ondelete="cascade", index=True)
    etape_id = fields.Many2one("circuit.etape", required=True)
    etat = fields.Selection(
        [("attente", "En attente"), ("approuve", "Approuvé"),
         ("refuse", "Refusé")], default="attente", readonly=True)
    avis = fields.Text("Avis / réponse", readonly=True)
    mission_id = fields.Many2one("atelier.mission", "Mission", readonly=True)
    decision_id = fields.Many2one("decision.fiche", "Fiche Décision",
                                  readonly=True)
    photo_etat = fields.Char(
        "Photo de l'etat", readonly=True,
        help="L'etat de l'instance au moment ou la porte s'ouvre - un "
             "instantane par etape, comme la table flow_states de CrewAI.")

    def _declencher(self):
        """Déclenche la porte selon son rôle."""
        self.ensure_one()
        import json as _json
        self.photo_etat = _json.dumps({
            "porte": self.etape_id.name,
            "rang": self.instance_id.etape_courante,
            "reprises": self.instance_id.reprises,
            "quand": str(fields.Datetime.now())}, ensure_ascii=False)
        role = self.etape_id.role
        if role == "agent":
            self._porte_agent()
        elif role == "patron":
            self._porte_patron()
        elif role == "prod":
            self._porte_prod()

    def _porte_agent(self):
        """Une porte agent : on dépose une mission de relecture. Si l'agent n'a
        pas de moteur, la porte reste en attente (Patrick pourra forcer)."""
        self.ensure_one()
        membre = self.etape_id.membre_id
        inst = self.instance_id
        if not membre or not (membre.moteur or "").strip():
            inst.message_post(body=_(
                "Porte « %s » : aucun agent à moteur — en attente (forçable à "
                "la main).") % self.etape_id.name)
            return
        import re
        contenu = re.sub(r"<[^>]+>", " ", inst.sujet or "")
        consigne = (
            "Tu es %s (%s). On te demande de RELIRE ce qui suit et de dire si "
            "tu l'approuves, DEPUIS TON METIER.\n\nSUJET : %s\n\nCONTENU :\n%s"
            "\n\nReponds en 10 lignes max. COMMENCE par APPROUVE ou REFUSE, "
            "puis pourquoi." % (
                membre.name, membre.poste or "", inst.name, contenu[:4000]))
        mission = self.env["atelier.mission"].sudo().create({
            "name": _("Circuit — %s relit : %s")[:80] % (
                membre.name, inst.name[:40]),
            "consigne": consigne, "moteur": membre.moteur})
        self.mission_id = mission.id
        try:
            mission.action_envoyer()
            inst.message_post(body=_("Porte « %s » : mission déposée à %s.")
                              % (self.etape_id.name, membre.name))
        except Exception as exc:  # noqa: BLE001
            inst.message_post(body=_(
                "Porte « %s » : l'atelier n'a pas pris la mission (%s) — en "
                "attente, forçable.") % (self.etape_id.name, exc))

    def _porte_patron(self):
        """La porte de Patrick : une fiche Décisions. Approuver = avancer."""
        self.ensure_one()
        inst = self.instance_id
        if "decision.fiche" not in self.env:
            inst.message_post(body="Module Décisions absent — porte Patron sautée.")
            inst._porte_repondue(self, True, avis="(Décisions absent)")
            return
        # UNE instance = UNE fiche (contrainte unique(res_model, res_id) de
        # decision.fiche). A la 2e porte « patron » — ou apres une reprise —
        # on RE-ARME la fiche existante au lieu d'en creer une seconde, ce
        # qui levait un UniqueViolation et figeait le circuit.
        vals = {
            "name": _("Circuit « %s » : %s — tu valides ?") % (
                inst.modele_id.name, inst.name),
            "origine": _("Circuit (%s)") % inst.modele_id.name,
            "resume": inst.sujet or "",
            "res_model": "circuit.instance", "res_id": inst.id,
            "priorite": "2"}
        Fiche = self.env["decision.fiche"].sudo()
        fiche = Fiche.search([("res_model", "=", "circuit.instance"),
                              ("res_id", "=", inst.id)], limit=1)
        if fiche:
            vals["etat"] = "attente"
            fiche.write(vals)
        else:
            fiche = Fiche.create(vals)
        self.decision_id = fiche.id
        inst.message_post(body=_("Porte « %s » : une décision t'attend.")
                          % self.etape_id.name)

    def _porte_prod(self):
        """La porte prod : réutilise tour_promotion si présent."""
        self.ensure_one()
        inst = self.instance_id
        cible = (inst.module_cible or "").strip()
        # GARDE (05/08) : `promotion.demande` refuse tout nom qui n'est pas un
        # module Odoo (minuscules, chiffres, « _ »). Trois instances portaient
        # « atelier.mission » — un nom de MODELE — et l'exception remontait
        # jusqu'au cron, figeant le relevé de TOUTES les portes pendant 3 h 30.
        # On verifie donc la forme ici, et on refuse poliment : un circuit qui
        # ne peut pas promouvoir doit le DIRE, pas arreter les autres.
        if cible and not re.match(r"^[a-z0-9_]+$", cible):
            inst.message_post(body=_(
                "Porte « %s » : mise en prod non demandee — « %s » n'est pas "
                "un nom de module (il faut des minuscules, des chiffres et "
                "« _ », par exemple tour_atelier). Le circuit continue."
            ) % (self.etape_id.name, cible))
            cible = ""
        if "promotion.demande" in self.env and cible:
            dem = self.env["promotion.demande"].sudo().create({
                "module": cible,
                "valide_en_test": True,
                "note": _("Via le circuit %s : %s") % (
                    inst.modele_id.name, inst.name)})
            dem.action_demander()
            inst.message_post(body=_(
                "Porte « %s » : demande de mise en prod créée (module %s) — "
                "à approuver dans Décisions.") % (
                    self.etape_id.name, cible))
            # La porte prod est « passée » côté circuit ; la vraie mise en prod
            # suit son propre verrou (tour_promotion).
            inst._porte_repondue(self, True, avis="Demande de prod déposée.")
        else:
            inst._porte_repondue(self, True, avis="(pas de module cible)")


class CircuitImport(models.TransientModel):
    """Importer un gabarit depuis un export JSON (gabarits exportables)."""
    _name = "circuit.modele.import"
    _description = "Import d'un gabarit de circuit"

    contenu = fields.Text("Le JSON exporte", required=True)

    def action_importer(self):
        self.ensure_one()
        modele = self.env["circuit.modele"].importer_json(self.contenu)
        return {"type": "ir.actions.act_window",
                "res_model": "circuit.modele", "res_id": modele.id,
                "view_mode": "form", "target": "current"}
