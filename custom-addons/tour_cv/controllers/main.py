# -*- coding: utf-8 -*-
"""La page publique du CV.

Autonome : aucun asset Odoo, tout est dans la page. Un CV doit s'ouvrir vite
sur un téléphone, depuis n'importe quel réseau, sans qu'un fichier manquant
casse la mise en page devant un recruteur.
"""
from odoo import http
from odoo.http import request

PAGE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(nom)s — %(metier)s</title>
<meta name="robots" content="%(robots)s">
<style>
 :root{--fond:#0a0f1a;--surface:#111a2b;--surface2:#1c2740;--bord:#243149;
       --texte:#e8eef7;--doux:#93a3bb;--accent:#4f8ef7;--r:14px}
 @media (prefers-color-scheme: light){
   :root{--fond:#f7f9fc;--surface:#fff;--surface2:#eef2f8;--bord:#dde4ee;
         --texte:#0f172a;--doux:#5b6b83}}
 *{box-sizing:border-box}
 html{scroll-behavior:smooth}
 body{margin:0;background:var(--fond);color:var(--texte);line-height:1.65;
      font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
      -webkit-font-smoothing:antialiased}
 a{color:var(--accent);text-decoration:none}
 a:hover{text-decoration:underline}
 .wrap{max-width:60rem;margin:0 auto;padding:0 1.15rem}
 nav{position:sticky;top:0;z-index:20;border-bottom:1px solid var(--bord);
     background:color-mix(in srgb,var(--fond) 88%%,transparent);
     backdrop-filter:blur(10px)}
 nav .wrap{display:flex;gap:.35rem;overflow-x:auto;padding:.6rem 1.15rem;
           scrollbar-width:none}
 nav .wrap::-webkit-scrollbar{display:none}
 nav a{white-space:nowrap;font-size:.85rem;color:var(--doux);
       padding:.35rem .7rem;border-radius:999px}
 nav a:hover{background:var(--surface2);color:var(--texte);text-decoration:none}
 header.hero{padding:3rem 0 2.25rem}
 .metier{display:inline-block;font-size:.72rem;letter-spacing:.14em;
         text-transform:uppercase;color:var(--accent);border:1px solid var(--bord);
         border-radius:999px;padding:.3rem .8rem;margin-bottom:1rem}
 h1{font-size:clamp(1.9rem,6vw,3rem);line-height:1.08;margin:0 0 .6rem;
    letter-spacing:-.02em}
 .sous{font-size:clamp(1rem,2.6vw,1.2rem);color:var(--doux);margin:0 0 1.5rem}
 .contact{display:flex;flex-wrap:wrap;gap:.5rem}
 .contact a,.contact span{font-size:.88rem;background:var(--surface);
   border:1px solid var(--bord);border-radius:999px;padding:.4rem .85rem;
   color:var(--texte)}
 section{padding:2.25rem 0;border-top:1px solid var(--bord)}
 h2{font-size:.75rem;letter-spacing:.16em;text-transform:uppercase;
    color:var(--doux);margin:0 0 1.25rem;font-weight:600}
 h3{font-size:1.05rem;margin:0 0 .2rem}
 .accroche{font-size:1.05rem;max-width:46rem}
 .carte{background:var(--surface);border:1px solid var(--bord);
        border-radius:var(--r);padding:1.35rem;margin-bottom:1rem}
 .carte-tete{display:flex;flex-wrap:wrap;gap:.5rem 1rem;align-items:baseline;
             justify-content:space-between}
 .quand{font-size:.82rem;color:var(--doux);white-space:nowrap}
 .lieu{font-size:.9rem;color:var(--doux);margin:.1rem 0 .9rem}
 ul{margin:.6rem 0 0;padding-left:1.1rem}
 li{margin-bottom:.45rem}
 li::marker{color:var(--accent)}
 .puces{display:flex;flex-wrap:wrap;gap:.4rem;margin:.9rem 0 0}
 .puce{font-size:.78rem;background:var(--surface2);border:1px solid var(--bord);
       border-radius:999px;padding:.25rem .65rem;color:var(--doux)}
 .chiffres{display:grid;gap:.7rem;grid-template-columns:repeat(2,1fr);margin:1.2rem 0 0}
 @media(min-width:640px){.chiffres{grid-template-columns:repeat(4,1fr)}}
 .chiffre{background:var(--surface2);border-radius:10px;padding:.8rem}
 .chiffre b{display:block;font-size:1.35rem;line-height:1.1}
 .chiffre span{font-size:.75rem;color:var(--doux)}
 details{border-top:1px solid var(--bord);margin-top:1rem;padding-top:.85rem}
 summary{cursor:pointer;font-size:.88rem;color:var(--accent);list-style:none;
         display:inline-flex;align-items:center;gap:.4rem}
 summary::-webkit-details-marker{display:none}
 summary::after{content:"+";font-size:1.05rem;line-height:1}
 details[open] summary::after{content:"\\2212"}
 .comp{display:grid;gap:.9rem}
 @media(min-width:760px){.comp{grid-template-columns:1fr 1fr}}
 .comp-bloc b{display:block;font-size:.78rem;letter-spacing:.1em;
              text-transform:uppercase;color:var(--accent);margin-bottom:.5rem}
 footer{border-top:1px solid var(--bord);padding:2rem 0 3rem;color:var(--doux);
        font-size:.85rem}
</style>
</head>
<body>
<nav><div class="wrap">%(menu)s</div></nav>
<header class="hero"><div class="wrap">
  <div class="metier">%(metier)s</div>
  <h1>%(nom)s</h1>
  <p class="sous">%(phrase)s</p>
  <div class="contact">%(contacts)s</div>
</div></header>
%(corps)s
<footer><div class="wrap">%(nom)s%(ville)s</div></footer>
</body></html>"""


def _e(v):
    return (v or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class TourCv(http.Controller):

    @http.route("/cv/<string:slug>", type="http", auth="public", website=False)
    def cv(self, slug, **kw):
        p = request.env["cv.profil"].sudo().search(
            [("slug", "=", slug), ("publie", "=", True)], limit=1)
        if not p:
            # Volontairement identique a une adresse inconnue : on ne dit
            # jamais qu'un CV existe mais n'est pas publie.
            return request.not_found()

        menu = []
        corps = []

        if p.accroche:
            menu.append('<a href="#profil">Profil</a>')
            corps.append('<section id="profil"><div class="wrap"><h2>Profil</h2>'
                         '<div class="accroche">%s</div></div></section>' % p.accroche)

        if p.realisation_ids:
            menu.append('<a href="#real">Réalisations</a>')
            blocs = []
            for r in p.realisation_ids:
                chiffres = "".join(
                    '<div class="chiffre"><b>%s</b><span>%s</span></div>'
                    % (_e(v), _e(l)) for v, l in r._chiffres_lus())
                outils = "".join('<span class="puce">%s</span>' % _e(o)
                                 for o in r._outils_lus())
                replies = "".join(
                    "<details><summary>%s</summary>%s</details>"
                    % (_e(b.name), b.contenu or "") for b in r.bloc_ids)
                blocs.append(
                    '<div class="carte"><div class="carte-tete"><h3>%s</h3>'
                    '<span class="quand">%s</span></div>'
                    '<div class="lieu">%s</div>'
                    '%s%s%s%s</div>'
                    % (_e(r.name), _e(r.periode), _e(r.contexte),
                       ('<div class="chiffres">%s</div>' % chiffres) if chiffres else "",
                       ('<div class="puces">%s</div>' % outils) if outils else "",
                       r.points or "", replies))
            corps.append('<section id="real"><div class="wrap">'
                         '<h2>Réalisations</h2>%s</div></section>' % "".join(blocs))

        if p.experience_ids:
            menu.append('<a href="#exp">Expérience</a>')
            blocs = []
            for e in p.experience_ids:
                replie = ""
                if e.detail_titre and e.detail:
                    replie = ("<details><summary>%s</summary>%s</details>"
                              % (_e(e.detail_titre), e.detail))
                lieu = " — ".join(x for x in (e.organisation, e.precision) if x)
                blocs.append(
                    '<div class="carte"><div class="carte-tete"><h3>%s</h3>'
                    '<span class="quand">%s</span></div>'
                    '<div class="lieu">%s</div>%s%s</div>'
                    % (_e(e.name), _e(e.periode), _e(lieu), e.points or "", replie))
            corps.append('<section id="exp"><div class="wrap">'
                         '<h2>Expérience</h2>%s</div></section>' % "".join(blocs))

        if p.competence_ids:
            menu.append('<a href="#comp">Compétences</a>')
            blocs = "".join(
                '<div class="carte comp-bloc"><b>%s</b>%s</div>'
                % (_e(c.name), _e(c.contenu)) for c in p.competence_ids)
            corps.append('<section id="comp"><div class="wrap"><h2>Compétences</h2>'
                         '<div class="comp">%s</div></div></section>' % blocs)

        if p.formation_ids or p.langues:
            menu.append('<a href="#form">Formation</a>')
            blocs = "".join(
                '<div class="carte"><div class="carte-tete"><h3>%s</h3>'
                '<span class="quand">%s</span></div><div class="lieu">%s</div></div>'
                % (_e(f.name), _e(f.periode), _e(f.ecole)) for f in p.formation_ids)
            if p.langues:
                blocs += '<p class="lieu">%s</p>' % _e(p.langues)
            corps.append('<section id="form"><div class="wrap">'
                         '<h2>Formation</h2>%s</div></section>' % blocs)

        contacts = []
        if p.ville:
            contacts.append("<span>%s</span>" % _e(p.ville))
        if p.telephone:
            contacts.append('<a href="tel:%s">%s</a>'
                            % (_e(p.telephone).replace(" ", ""), _e(p.telephone)))
        if p.email:
            contacts.append('<a href="mailto:%s">%s</a>' % (_e(p.email), _e(p.email)))
        if p.linkedin:
            contacts.append('<a href="%s" rel="noopener">LinkedIn</a>' % _e(p.linkedin))
        if contacts:
            menu.append('<a href="#contact">Contact</a>')
            corps.append('<section id="contact"><div class="wrap"><h2>Me joindre</h2>'
                         '<div class="contact">%s</div></div></section>'
                         % "".join(contacts))

        html = PAGE % {
            "nom": _e(p.name),
            "metier": _e(p.metier),
            "phrase": p.phrase_forte or "",
            "robots": "index,follow" if p.indexable else "noindex,nofollow",
            "menu": "".join(menu),
            "contacts": "".join(contacts),
            "corps": "".join(corps),
            "ville": (" — " + _e(p.ville)) if p.ville else "",
        }
        return request.make_response(
            html, headers=[("Content-Type", "text/html; charset=utf-8")])
