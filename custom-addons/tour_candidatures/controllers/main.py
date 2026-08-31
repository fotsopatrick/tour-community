# -*- coding: utf-8 -*-
"""Page web « Mes candidatures » + import semi-automatique d'une offre collée.

Indeed n'a pas d'API publique gratuite et bloque le moissonnage (Cloudflare) :
on ne scape pas. La voie légale et stable (tâche 1152) : on COLLE le texte de
l'offre, la tour en extrait les champs (titre, entreprise, lieu, contrat,
salaire, description) et crée la fiche �?? l'humain confirme avant. Même principe
que la page Quêtes.
"""
import re

from odoo import fields, http
from odoo.http import request


def _extraire(texte):
    """Extrait les champs d'une offre collée, de façon déterministe."""
    lignes = [l.strip() for l in (texte or "").splitlines() if l.strip()]
    offre = {
        "titre": "",
        "entreprise": "",
        "lieu": "",
        "contrat": "",
        "salaire": "",
        "description": "",
    }
    if not lignes:
        return offre
    # Titre : la première ligne, sauf si elle est triviale
    titre = lignes[0]
    for mot in ("job", "offre", "poste", "description", "about", "à propos"):
        if titre.lower().startswith(mot):
            titre = lignes[1] if len(lignes) > 1 else titre
            break
    offre["titre"] = titre[:120]

    # Entreprise : un motif « chez X », « at X », ou la 2e/3e ligne courte
    m = re.search(r"(?:chez|at|@)\s+([A-Za-z�?-ÿ0-9&' .-]{2,40})", texte, re.I)
    if m:
        offre["entreprise"] = m.group(1).strip()
    else:
        for l in lignes[1:4]:
            if 2 <= len(l) <= 40 and not re.search(r"[�?�£$]|[0-9]{2,}", l):
                offre["entreprise"] = l
                break

    # Lieu : « à Paris », « Lieu : », ou un motif ville
    m = re.search(r"(?:à|a)\s+([A-Z�?-ÿ][a-zà-ÿéèêëîïôöùûüç-]+(?:\s*[A-Z�?-ÿ][a-zà-ÿ]+)*)\s*(?:,|\(|$)", texte)
    if m:
        offre["lieu"] = m.group(1).strip()
    m = re.search(r"(?:lieu|location|place)\s*[:\-]\s*([^\n]{2,50})", texte, re.I)
    if m:
        offre["lieu"] = m.group(1).strip()

    # Type de contrat
    m = re.search(r"\b(CDI|CDD|Stage|Alternance|Intérim|Freelance|Freelance|Contractuel)\b", texte, re.I)
    if m:
        offre["contrat"] = m.group(1).upper()

    # Salaire
    m = re.search(r"([0-9][0-9\s.,]*)\s*(?:EUR|�?�|CHF|USD)?\s*(?:/|par)?\s*(?:an|mois|jour|hour|h)?", texte, re.I)
    if m and re.search(r"�?�|EUR|CHF|USD|an|mois", texte, re.I):
        offre["salaire"] = m.group(0).strip()[:60]

    # Description : tout le reste, borné
    offre["description"] = (texte or "").strip()[:4000]
    return offre


class CandidatureWeb(http.Controller):

    @http.route("/tour/carriere", type="http", auth="user", website=False)
    def carriere(self, **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        fiches = request.env["candidature.fiche"].sudo().search(
            [], order="date_envoi desc, id desc")
        lignes = []
        for f in fiches:
            lignes.append(
                "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s �?�</td>"
                "<td><span class='etat %s'>%s</span></td></tr>"
                % (f.date_envoi or "", f.name or "", f.entreprise or "",
                   int(f.remuneration or 0), f.etat or "", f.etat or ""))
        corps = "\n".join(lignes) or "<tr><td colspan='5' class='vide'>Aucune candidature.</td></tr>"
        return request.make_response(
            _PAGE.replace("__CORPS__", corps),
            headers=[("Content-Type", "text/html; charset=utf-8")])

    @http.route("/tour/carriere/importer", type="http", auth="user",
                website=False, methods=["POST"], csrf=False)
    def importer(self, **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.forbidden()
        texte = (kw.get("offre") or "").strip()
        if not texte:
            return request.redirect("/tour/carriere?err=vide")
        o = _extraire(texte)
        vals = {
            "name": o["titre"] or "Offre collée",
            "entreprise": o["entreprise"] or "Inconnue",
            "porte": kw.get("porte") or "salariat",
            "canal": kw.get("canal") or "formulaire",
            "date_envoi": fields.Date.context_today(request.env.user),
            "lien": (kw.get("lien") or "").strip() or None,
            "offre": texte,
        }
        try:
            m = re.search(r"([0-9][0-9\s.,]*)\s*(?:EUR|�?�)", texte)
            if m:
                vals["remuneration"] = float(
                    re.sub(r"[^\d]", "", m.group(1))[:6] or 0)
                vals["unite"] = "annuel"
        except (ValueError, TypeError):
            pass
        try:
            f = request.env["candidature.fiche"].sudo().create(vals)
            return request.redirect("/tour/carriere?cree=%s" % f.id)
        except Exception as e:  # noqa: BLE001
            return request.redirect("/tour/carriere?err=%s" % str(e)[:80])


_PAGE = """<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Mes candidatures �?? Tour de contrôle</title>
<style>
:root{--fond:#020817;--surface:#0f172a;--surface2:#1e293b;--primaire:#3b82f6;
--texte:#e2e8f0;--doux:#94a3b8;--ok:#22c55e;--r:.5rem;}
:root[data-theme="light"]{--fond:#EAEEF2;--surface:#fff;--surface2:#DDE4EB;
--primaire:#2F6FB0;--texte:#14202B;--doux:#5C6B7A;--ok:#1F8A46;}
body{margin:0;background:var(--fond);color:var(--texte);font-family:system-ui,"Segoe UI",sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:26px 16px 60px}
a{color:var(--primaire);text-decoration:none;font-size:.88rem}
h1{font-size:1.6rem;margin:10px 0 4px}
.sub{color:var(--doux);margin-bottom:22px;line-height:1.6}
textarea,select,input[type=text]{background:var(--surface);border:1px solid var(--surface2);
color:var(--texte);border-radius:.6rem;padding:9px 12px;font:inherit;font-size:.9rem;width:100%}
textarea{min-height:150px}
.btn{background:var(--primaire);color:#fff;border:0;border-radius:.6rem;padding:10px 16px;
font-weight:700;cursor:pointer;font:inherit}
.carte{background:var(--surface);border:1px solid var(--surface2);border-radius:.8rem;padding:16px;margin-bottom:18px}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th{color:var(--doux);text-align:left;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;padding:8px}
td{padding:8px;border-top:1px solid var(--surface2)}
.etat{padding:2px 9px;border-radius:99px;font-size:.72rem;background:var(--surface2)}
.vide{color:var(--doux);font-style:italic;padding:30px;text-align:center}
.bandeau{background:rgba(245,158,11,.1);border-left:3px solid #f59e0b;border-radius:.5rem;
padding:10px 14px;color:#f7bf6b;font-size:.9rem;margin-bottom:16px}
</style></head><body><div class="wrap">
<a href="/tour/dashboard">�?� Retour à l'accueil</a>
<h1>Mes candidatures</h1>
<p class="sub">Chaque candidature envoyée, et où ça en est. On colle l'offre,
la tour en sort les champs �?? rien ne se scrape (Indeed bloque), tout se colle.</p>
<div id="msg"></div>
<div class="carte"><h2 style="margin-top:0">Coller une offre</h2>
<form method="post" action="/tour/carriere/importer">
<textarea name="offre" placeholder="Colle ici le texte complet de l'offre�?�"></textarea>
<div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">
<input type="text" name="lien" placeholder="Lien de l'offre (facultatif)"/>
<select name="porte"><option value="salariat">Salariat</option>
<option value="consulting">Consulting</option><option value="mission">Mission</option></select>
</div>
<button class="btn" type="submit" style="margin-top:10px">Importer la candidature</button>
</form></div>
<h2>Le registre</h2>
<table><thead><tr><th>Envoyée</th><th>Poste</th><th>Entreprise</th><th>Visé</th><th>�?tat</th></tr></thead>
<tbody>__CORPS__</tbody></table>
</div>
<script>
(function(){var k="tour-theme",r=document.documentElement;try{var s=localStorage.getItem(k);
if(s==="light"||s==="dark"){r.setAttribute("data-theme",s);}else{r.setAttribute("data-theme","light");}
}catch(e){}var m=document.getElementById("msg");
var q=new URLSearchParams(location.search);
if(q.get("cree")){m.innerHTML="<div class='bandeau'>Candidature importée.</div>";}
if(q.get("err")){m.innerHTML="<div class='bandeau'>Erreur : "+q.get("err")+"</div>";}
})();
</script></body></html>"""
