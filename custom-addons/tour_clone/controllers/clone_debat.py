# -*- coding: utf-8 -*-
"""L'atelier de débat du clone — l'écran, et le moteur qui répond."""
import json
import logging
import random

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Le clone DEBAT. Il n'accompagne pas, il ne fait pas preciser : il a un avis
# et il le tient. Cette consigne est la difference entre apprendre et acquiescer.
SOCLE = """Tu es le clone de Patrick. Tu débats avec lui, d'égal à égal.

CE QUE TU FAIS
- Tu as un avis sur le sujet, et tu le donnes en premier, sans tourner autour.
- Si Patrick se trompe, tu le dis. Franchement, avec ton raisonnement.
- Tu tiens ta position tant qu'il ne t'a pas convaincu. Un argument te fait
  changer d'avis ; l'insistance, non.
- Quand il te convainc, tu le dis clairement : « tu as raison, et voilà ce que
  je n'avais pas vu ».

CE QUE TU NE FAIS JAMAIS
- Approuver pour faire plaisir. Un clone qui acquiesce n'apprend rien.
- Répondre par une question quand tu as un avis. Les questions viennent après
  l'avis, pas à la place.
- Faire un exposé. Trois ou quatre phrases, denses. C'est un échange, pas une
  conférence.
- Prétendre savoir. Si tu ne sais pas, tu dis ce que tu supposes ET que c'est
  une supposition.

TA FAÇON DE PARLER
Comme Patrick : direct, concret, sans jargon inutile. Tu dis « je pense que »
et pas « il semblerait que ». Tu donnes un exemple plutôt qu'une définition."""


class CloneDebatController(http.Controller):

    @http.route("/tour/clone", type="http", auth="user", website=False)
    def atelier(self, **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        Article = request.env["actus.article"].sudo()
        themes = [t for t in set(Article.search([]).mapped("categorie")) if t]
        Debat = request.env["clone.debat"].sudo()
        return request.render("tour_clone.page_atelier", {
            "themes": sorted(themes),
            "debats": Debat.search([("user_id", "=", request.env.user.id)],
                                   order="id desc", limit=8),
            "csrf_token": request.csrf_token(),
        })

    @http.route("/tour/clone/sujet", type="json", auth="user")
    def sujet(self, theme=None, **kw):
        """Tire un sujet des actus du jour. On ne fabrique pas un sujet."""
        Article = request.env["actus.article"].sudo()
        domaine = [("categorie", "=", theme)] if theme else []
        # Les 60 plus recents, puis un au hasard : le meme theme ne doit pas
        # ramener le meme article deux jours de suite.
        recents = Article.search(domaine, order="date_pub desc, id desc", limit=60)
        if not recents:
            return {"erreur": "Aucun article dans cette thématique."}
        a = random.choice(recents)
        d = request.env["clone.debat"].sudo().create({
            "name": (a.name or "Sans titre")[:180],
            "theme": theme or (a.categorie or ""),
            "article_id": a.id,
            "lien": a.lien or "",
        })
        return {
            "debat_id": d.id,
            "titre": a.name or "",
            "resume": (a.resume or "")[:600],
            "lien": a.lien or "",
            "source": a.flux_id.name if a.flux_id else "",
        }

    @http.route("/tour/clone/parler", type="json", auth="user")
    def parler(self, debat_id=None, message=None, **kw):
        D = request.env["clone.debat"].sudo()
        T = request.env["clone.debat.tour"].sudo()
        d = D.browse(int(debat_id or 0))
        if not d.exists():
            return {"erreur": "Débat introuvable."}

        texte = (message or "").strip()
        if texte:
            T.create({"debat_id": d.id, "qui": "patrick", "texte": texte})

        # On rejoue l'echange complet : le clone doit se souvenir de ce qu'il
        # a soutenu, sinon il change d'avis a chaque tour et ce n'est plus un
        # debat.
        historique = []
        for t in d.tour_ids:
            historique.append({
                "role": "user" if t.qui == "patrick" else "assistant",
                "content": t.texte or "",
            })

        contexte = (
            "%s\n\n=== LE SUJET DU JOUR ===\n%s\n\n%s\n\nSource : %s"
            % (SOCLE, d.name or "",
               (d.article_id.resume or "") if d.article_id else "",
               d.lien or "—"))

        if not historique:
            historique = [{"role": "user", "content":
                           "Donne-moi ton avis sur ce sujet, en premier."}]

        try:
            from odoo.addons.tour_copilote.controllers.main import executer_chat
            reponse = executer_chat(
                request.env,
                [{"role": "system", "content": contexte}] + historique)
        except Exception as e:  # noqa: BLE001
            _logger.exception("Clone : le moteur n'a pas repondu")
            return {"erreur": "Le moteur n'a pas répondu : %s" % str(e)[:120]}

        if "error" in reponse:
            return {"erreur": reponse["error"]}
        dit = reponse.get("reply") or ""
        # Un desaccord assume se compte.
        marques = ("je ne suis pas d'accord", "tu te trompes", "je pense que non",
                   "là je ne te suis pas", "je ne crois pas")
        desaccord = any(m in dit.lower() for m in marques)
        T.create({"debat_id": d.id, "qui": "clone", "texte": dit,
                  "desaccord": desaccord})
        return {"reponse": dit, "desaccord": desaccord,
                "tours": len(d.tour_ids)}

    @http.route("/tour/clone/clore", type="json", auth="user")
    def clore(self, debat_id=None, **kw):
        """On ferme, et le clone ecrit ce qu'il a retenu DE PATRICK."""
        d = request.env["clone.debat"].sudo().browse(int(debat_id or 0))
        if not d.exists():
            return {"erreur": "Débat introuvable."}
        dits = [t.texte for t in d.tour_ids if t.qui == "patrick"]
        if not dits:
            d.write({"etat": "clos"})
            return {"lecon": "Rien à retenir : Patrick n'a rien dit."}
        try:
            from odoo.addons.tour_copilote.controllers.main import executer_chat
            r = executer_chat(request.env, [
                {"role": "system", "content":
                 "Tu relis ce que PATRICK a dit dans un débat. Écris en trois "
                 "phrases maximum ce que tu retiens de SA FAÇON DE RAISONNER "
                 "— pas de son opinion, de sa méthode. Ce qui t'a fait changer "
                 "d'avis, s'il y a lieu. Rien d'autre."},
                {"role": "user", "content": "\n\n".join(dits)[:4000]},
            ])
            lecon = r.get("reply") or ""
        except Exception:  # noqa: BLE001
            lecon = ""
        d.write({"etat": "clos", "lecon": lecon})
        return {"lecon": lecon}
