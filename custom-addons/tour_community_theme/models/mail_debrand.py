# -*- coding: utf-8 -*-
"""Réécrire les courriels que l'édition Community envoie réellement.

Pourquoi du code plutôt qu'un simple fichier de données : les gabarits de
courriel d'Odoo sont déclarés `noupdate="1"`. Un module tiers qui tente de les
redéfinir par un `<record>` est **silencieusement ignoré** — le fichier passe,
aucune erreur n'apparaît, et le courriel part quand même avec la marque
d'origine. C'est le pire cas : on croit avoir corrigé.

Appelé par `<function>` dans data/mail_debrand.xml, donc rejoué à chaque mise à
jour du module. Écrire deux fois la même chose ne coûte rien ; ne pas le
rejouer après une montée de version d'Odoo, si.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# « user » = la personne qui ENVOIE l'invitation ; « object.create_uid » = celle
# qui a cree la fiche.
SUJET_INVITATION = "{{ user.name }} vous invite sur {{ object.company_id.name }}"

CORPS_INVITATION = """
<table border="0" cellpadding="0" cellspacing="0" style="padding-top:16px; background-color:#FFFFFF; font-family:Verdana,Arial,sans-serif; color:#454748; width:100%; border-collapse:separate;"><tr><td align="center">
<table border="0" cellpadding="0" cellspacing="0" width="590" style="padding:16px; background-color:#FFFFFF; color:#454748; border-collapse:separate;">
<tbody>
    <tr><td align="center" style="min-width:590px;">
        <table border="0" cellpadding="0" cellspacing="0" width="590" style="min-width:590px; background-color:white; padding:0px 8px; border-collapse:separate;">
            <tr><td valign="middle">
                <span style="font-size:20px; font-weight:bold;" t-out="object.company_id.name or ''">Tour de contr&#244;le</span>
            </td><td valign="middle" align="right" t-if="not object.company_id.uses_default_logo">
                <img t-attf-src="/logo.png?company={{ object.company_id.id }}" style="padding:0; margin:0; height:auto; width:80px;" t-att-alt="object.company_id.name"/>
            </td></tr>
            <tr><td colspan="2" style="text-align:center;">
                <hr width="100%" style="background-color:rgb(204,204,204); border:medium none; clear:both; display:block; font-size:0px; min-height:1px; line-height:0; margin:16px 0px;"/>
            </td></tr>
        </table>
    </td></tr>
    <tr><td align="center" style="min-width:590px;">
        <table border="0" cellpadding="0" cellspacing="0" width="590" style="min-width:590px; background-color:white; padding:0px 8px; border-collapse:separate;">
            <tr><td valign="top" style="font-size:13px;">
                Bonjour <t t-out="object.name or ''">Pr&#233;nom</t>,<br/><br/>
                <t t-out="user.name or ''">Quelqu'un</t> vous ouvre un acc&#232;s &#224;
                <b t-out="object.company_id.name or ''">la tour</b>.<br/><br/>
                C'est un espace pour suivre des projets, des t&#226;ches et des documents au
                m&#234;me endroit. Choisissez votre mot de passe en cliquant ci-dessous&#160;:
                personne d'autre ne le conna&#238;tra.
                <div style="margin:16px 0px;">
                    <a t-att-href="object.partner_id._get_signup_url()"
                       style="background-color:#3b82f6; padding:10px 18px; text-decoration:none; color:#ffffff; border-radius:5px; font-size:13px; font-weight:bold;">
                        Choisir mon mot de passe
                    </a>
                </div>
                Ce lien reste valable quelques jours. Si vous ne savez pas pourquoi vous
                recevez ce message, ignorez-le&#160;: aucun compte ne sera activ&#233; sans
                cette &#233;tape.<br/><br/>
                &#192; la premi&#232;re connexion, r&#233;pondez &#224; ce courriel en disant ce dont
                vous avez besoin &#8212; vos projets, vos t&#226;ches, vos documents&#160;:
                quelqu'un s'occupe du reste.<br/><br/>
                &#192; bient&#244;t.
            </td></tr>
            <tr><td style="text-align:center;">
                <hr width="100%" style="background-color:rgb(204,204,204); border:medium none; clear:both; display:block; font-size:0px; min-height:1px; line-height:0; margin:16px 0px;"/>
            </td></tr>
        </table>
    </td></tr>
    <tr><td align="center" style="min-width:590px;">
        <table border="0" cellpadding="0" cellspacing="0" width="590" style="min-width:590px; background-color:white; padding:0px 8px; border-collapse:separate;">
            <tr><td valign="middle" align="left" style="color:#999999; font-size:11px;">
                <t t-out="object.company_id.name or ''"/><t t-if="object.company_id.email"> &#8212; <t t-out="object.company_id.email"/></t>
            </td></tr>
        </table>
    </td></tr>
</tbody>
</table>
</td></tr></table>
"""


class MailDebrand(models.AbstractModel):
    _name = "tour.mail.debrand"
    _description = "Débranding des courriels sortants"

    @api.model
    def appliquer(self):
        gabarit = self.env.ref("auth_signup.set_password_email",
                               raise_if_not_found=False)
        if not gabarit:
            _logger.info("Debranding courriel : gabarit d'invitation absent")
            return False
        valeurs = {
            "name": "Invitation à rejoindre la tour",
            "subject": SUJET_INVITATION,
            "body_html": CORPS_INVITATION,
            "description": "Envoyé à une personne que l'on vient d'inviter",
            "lang": "{{ object.lang }}",
        }
        gabarit.sudo().write(valeurs)
        gabarit.sudo().with_context(lang="fr_FR").write(valeurs)
        _logger.info("Debranding courriel : invitation reecrite (fr et defaut)")
        return True
