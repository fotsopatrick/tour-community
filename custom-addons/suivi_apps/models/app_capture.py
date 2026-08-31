# -*- coding: utf-8 -*-
"""Aperçu visuel d'une app ou d'un site.

Les captures sont stockées dans la tour, pas liées à un hébergement externe :
une fiche projet doit rester montrable en rendez-vous même si le dépôt public
disparaît ou passe en privé.
"""
from odoo import fields, models


class AppCapture(models.Model):
    _name = "app.capture"
    _description = "Capture d'écran d'une app"
    _order = "sequence, id"

    name = fields.Char("Légende", help="Ce que montre l'écran, en trois mots.")
    image = fields.Image("Capture", required=True, max_width=1200, max_height=2400)
    app_id = fields.Many2one("app.suivi", string="App", required=True,
                             ondelete="cascade", index=True)
    sequence = fields.Integer("Ordre", default=10)


class AppSuivi(models.Model):
    _inherit = "app.suivi"

    capture_ids = fields.One2many("app.capture", "app_id", string="Captures")
    nb_captures = fields.Integer("Nb captures", compute="_compute_nb_captures")
    format_apercu = fields.Selection(
        [("mobile", "Téléphone"), ("desktop", "Écran d'ordinateur")],
        string="Cadre d'aperçu", default="mobile",
        help="Détermine le cadre dans lequel les captures sont présentées.")
    apk_url = fields.Char(
        "Lien de téléchargement (APK)",
        help="Adresse directe du fichier installable, quand il y en a un.")

    apercu_html = fields.Html("Aperçu", compute="_compute_apercu_html",
                              sanitize=False, readonly=True)

    def _compute_nb_captures(self):
        for rec in self:
            rec.nb_captures = len(rec.capture_ids)

    def _compute_apercu_html(self):
        """Un seul cadre, les captures défilent dedans.

        Volontairement sans JavaScript : styles en ligne et défilement natif
        avec accroche (scroll-snap). Une capture occupe toute la largeur du
        cadre et s'y cale d'elle-même ; les pastilles numérotées sautent d'une
        capture à l'autre. Rien à charger, rien qui puisse casser à une mise à
        jour du moteur.
        """
        cadre = {
            "mobile": ("width:270px;height:560px;border-radius:2rem;"
                       "border:10px solid #0f172a;"),
            "desktop": ("width:420px;height:265px;border-radius:.6rem;"
                        "border:8px solid #0f172a;"),
        }
        for rec in self:
            captures = rec.capture_ids.sorted("sequence")
            if not captures:
                rec.apercu_html = False
                continue
            style_cadre = cadre.get(rec.format_apercu or "mobile", cadre["mobile"])
            vues, pastilles = [], []
            for i, c in enumerate(captures, start=1):
                ancre = "cap-%s-%s" % (rec.id, i)
                vues.append(
                    '<div id="%s" style="flex:0 0 100%%;scroll-snap-align:center;'
                    'height:100%%;display:flex;align-items:center;'
                    'justify-content:center;background:#020817;">'
                    # width/height explicites plutôt que max-* : dans un
                    # conteneur flex, les max-* ne résolvent pas toujours et
                    # l'image déborde du cadre par le bas.
                    '<img src="/web/image/app.capture/%s/image" alt="%s" '
                    'style="width:100%%;height:100%%;object-fit:contain;"/>'
                    "</div>" % (ancre, c.id, (c.name or "").replace('"', ""))
                )
                pastilles.append(
                    '<a href="#%s" title="%s" style="display:inline-flex;'
                    "align-items:center;justify-content:center;width:26px;"
                    "height:26px;margin:0 3px;border-radius:50%%;"
                    "background:#1e293b;color:#94a3b8;text-decoration:none;"
                    'font-size:.75rem;">%s</a>'
                    % (ancre, (c.name or "").replace('"', ""), i)
                )
            legendes = " · ".join(c.name for c in captures if c.name)
            rec.apercu_html = (
                '<div style="display:inline-block;text-align:center;">'
                '<div style="%s overflow-x:auto;overflow-y:hidden;'
                'scroll-snap-type:x mandatory;display:flex;background:#020817;">'
                "%s</div>"
                '<div style="margin-top:.6rem;">%s</div>'
                '<div style="margin-top:.4rem;color:#94a3b8;font-size:.75rem;'
                'max-width:290px;">%s</div>'
                "</div>"
                % (style_cadre, "".join(vues), "".join(pastilles), legendes)
            )

    def action_ouvrir_site(self):
        """Ouvre le site ou la web app dans un nouvel onglet."""
        self.ensure_one()
        if not self.site_url:
            return False
        return {"type": "ir.actions.act_url", "url": self.site_url, "target": "new"}

    def action_telecharger_apk(self):
        self.ensure_one()
        if not self.apk_url:
            return False
        return {"type": "ir.actions.act_url", "url": self.apk_url, "target": "new"}
