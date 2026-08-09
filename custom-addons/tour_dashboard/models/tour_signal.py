# -*- coding: utf-8 -*-
"""Le signal commun : un seul endroit qui decide comment un agent previent.

Le probleme, constate le 27/07 : chaque agent prevenait a sa facon, ou ne
prevenait pas du tout. Victor envoyait un courriel avec des boutons, Braignak
n'envoyait rien avant ce matin, Clark deposait son compte rendu dans un fil
que personne ne regarde, l'atelier relevait ses resultats en silence.

Consequence : on cesse de lancer un agent. Pas parce qu'il est mauvais — parce
qu'on a pris l'habitude de ne rien attendre de lui.

**Un seul endroit decide** du destinataire, de la forme, et du canal. Un agent
appelle `_signaler(...)` et ne se preoccupe de rien d'autre.

Trois regles, heritees de ce qui a marche ailleurs :

- **On signale un evenement, jamais un etat.** Un agent qui dit « j'ai fini » a
  chaque passage alors que rien n'a change devient un bruit qu'on apprend a
  ignorer — et on ignore ensuite celui qui avait quelque chose a dire.
- **Le destinataire est celui de l'INSTANCE**, pas une adresse en dur. Chez un
  client, c'est le client qui doit etre prevenu de ce que font ses agents, pas
  nous. Un outil qui rend compte a son constructeur plutot qu'a son
  proprietaire n'est pas un outil, c'est une sonde.
- **Tout signal laisse une trace dans le journal**, meme si le courriel echoue.
  Le courriel est un confort ; le journal est la preuve.
"""
import datetime
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Le ton du bandeau, selon ce qui s'est passe. Pas plus de trois : au-dela on
# ne les distingue plus, et une gradation qu'on ne lit pas ne sert a rien.
TONS = {
    "fait": ("#22c55e", "✓"),
    "attention": ("#f59e0b", "!"),
    "echec": ("#ef4444", "×"),
}


class TourSignal(models.AbstractModel):
    _name = "tour.signal"
    _description = "Signal commun des agents"

    @api.model
    def _destinataire(self):
        """Qui doit etre prevenu SUR CETTE INSTANCE.

        Ordre : le parametre explicite, puis le courriel de la societe, puis
        celui de l'administrateur. Jamais d'adresse en dur — chez un client,
        c'est lui qui recoit ce que font ses agents.
        """
        icp = self.env["ir.config_parameter"].sudo()
        return (icp.get_param("tour.signal_destinataire")
                or icp.get_param("securite.destinataire")
                or self.env.company.email
                or self.env.ref("base.user_admin").email
                or False)

    @api.model
    def _expediteur(self):
        icp = self.env["ir.config_parameter"].sudo()
        depuis = icp.get_param("mail.default.from") or "contact"
        domaine = icp.get_param("mail.catchall.domain") or "matourdecontrole.fr"
        if "@" not in depuis:
            depuis = "%s@%s" % (depuis, domaine)
        return self.env.company.email or depuis

    @api.model
    def _signaler(self, agent, titre, corps_html, lien=None, ton="fait",
                  enregistrement=None, destinataire=None):
        """Un agent a quelque chose a dire. C'est le seul chemin.

        agent          : « Braignak », « Victor », « Jimmy »… le nom affiche
        titre          : une ligne, ce qui s'est passe
        corps_html     : le detail, deja en HTML
        lien           : chemin relatif vers la fiche, si elle existe
        ton            : fait / attention / echec
        enregistrement : la fiche a annoter, pour la trace
        destinataire   : une adresse PRECISE, quand le message ne s'adresse pas
                         au proprietaire de l'instance mais a la personne qui a
                         demande le travail.

        POURQUOI CE DERNIER PARAMETRE (29/07, mesure faite ce jour-la).
        La tour avait envoye 26 courriels depuis sa creation : les 26 a Patrick.
        Sankara etait proprietaire de ses deux missions, abonne aux deux fiches,
        son compte reglait bien « recevoir par courriel » — il n'a jamais rien
        recu. La destination etait fixe, donc le demandeur n'existait pas.
        Un client qui paie vivra la meme chose : son app sort, il l'ignore.
        La forme reste decidee ICI, une seule fois ; seule la destination
        devient explicite.
        """
        couleur, signe = TONS.get(ton, TONS["fait"])
        base = (self.env["ir.config_parameter"].sudo()
                .get_param("web.base.url") or "").rstrip("/")
        bouton = ""
        if lien:
            bouton = (
                '<p style="margin-top:18px">'
                '<a href="%s%s" style="background:#3b82f6;color:#fff;'
                'padding:10px 18px;border-radius:8px;text-decoration:none;'
                'font-weight:600;display:inline-block">Voir</a></p>'
            ) % (base, lien if lien.startswith("/") else "/" + lien)

        html = """
<div style="font-family:system-ui,-apple-system,'Segoe UI',sans-serif;
            background:#020817;color:#e2e8f0;padding:22px">
  <div style="max-width:600px;margin:0 auto">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
      <span style="display:inline-flex;width:26px;height:26px;border-radius:50%%;
                   background:%(couleur)s;color:#04140a;align-items:center;
                   justify-content:center;font-weight:700">%(signe)s</span>
      <span style="font-size:11px;text-transform:uppercase;letter-spacing:.1em;
                   color:#94a3b8">%(agent)s</span>
    </div>
    <div style="font-size:19px;font-weight:650;margin:6px 0 14px">%(titre)s</div>
    <div style="color:#cbd5e1;line-height:1.6">%(corps)s</div>
    %(bouton)s
    <div style="color:#64748b;font-size:12px;margin-top:22px;
                border-top:1px solid #1e293b;padding-top:12px">
      Message envoye par un agent de votre tour de controle. Il n'a rien
      decide seul : ce qu'il propose reste a trancher.
    </div>
  </div>
</div>""" % {"couleur": couleur, "signe": signe, "agent": agent,
             "titre": titre, "corps": corps_html, "bouton": bouton}

        # La trace d'abord : le courriel est un confort, le journal est la
        # preuve. Si l'envoi echoue, on doit quand meme savoir que ca s'est
        # passe.
        if enregistrement is not None and hasattr(enregistrement, "message_post"):
            try:
                enregistrement.sudo().message_post(
                    body=_("<b>%(agent)s</b> — %(titre)s",
                           agent=agent, titre=titre))
            except Exception:  # noqa: BLE001
                _logger.warning("Signal : trace impossible sur %s", enregistrement)

        # L'ANTI-REPETITION (07/08, mesure faite ce jour-la).
        # En trois jours : 867 fois « L atelier a termine », 614 fois
        # « Connexion SSH », 215 fois le meme passage de securite de Victor.
        # 1 772 courriels le 4 aout. La boite de Patrick se remplissait.
        # Un signal repete deux cents fois ne signale plus rien : le bruit
        # fait taire le signal — c'est ecrit en tete de ce fichier depuis le
        # 27 juillet. C'etait une regle ecrite ; elle devient une regle codee.
        # La TRACE est deja posee juste au-dessus : on ne perd rien, on retient
        # seulement le courriel en double.
        if self._deja_signale(agent, titre):
            _logger.info(
                "Signal de %s : meme titre deja envoye recemment, courriel "
                "retenu — %s", agent, titre)
            return False

        dest = destinataire or self._destinataire()
        if not dest:
            _logger.info("Signal de %s : aucun destinataire, courriel ignore.", agent)
            return False
        self.env["mail.mail"].sudo().create({
            "subject": "[%s] %s" % (agent, titre),
            "body_html": html,
            "email_from": self._expediteur(),
            "email_to": dest,
            "auto_delete": False,
        }).send()
        _logger.info("Signal de %s envoye a %s", agent, dest)
        return True

    # ------------------------------------------------------------------
    # L'ANTI-REPETITION
    # ------------------------------------------------------------------
    # Pendant cette duree, un meme titre du meme agent ne repart pas. Reglable
    # sans toucher au code : tour_dashboard.minutes_anti_repetition.
    # Mettre 0 remet le comportement d'avant, sans redemarrage.
    MINUTES_ANTI_REPETITION = 120

    @api.model
    def _deja_signale(self, agent, titre):
        """Ce meme titre est-il deja parti dans la fenetre ?"""
        minutes = self.MINUTES_ANTI_REPETITION
        reglage = self.env["ir.config_parameter"].sudo().get_param(
            "tour_dashboard.minutes_anti_repetition")
        if reglage not in (None, False, ""):
            try:
                minutes = int(reglage)
            except (TypeError, ValueError):
                pass
        if minutes <= 0:
            return False
        sujet = "[%s] %s" % (agent, titre)
        limite = fields.Datetime.now() - datetime.timedelta(minutes=minutes)
        try:
            return bool(self.env["mail.mail"].sudo().search_count([
                ("subject", "=", sujet),
                ("create_date", ">=", limite),
            ]))
        except Exception:  # noqa: BLE001
            # Un doute ne doit jamais faire TAIRE un signal : en cas de
            # probleme, on laisse partir le courriel.
            _logger.warning("Anti-repetition : verification impossible",
                            exc_info=True)
            return False
