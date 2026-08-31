# -*- coding: utf-8 -*-
"""La place archive (tâche 1371, Patrick 08/08) : l'endroit où tout ce qui
s'archive va, visible et trouvable. Règle : archiver = marquer + rendre
trouvable, pas faire disparaître. On ne supprime jamais les tâches archivées."""
import html as _h

from odoo import http
from odoo.http import request

_PAGE = """<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Place archive — Tour de contrôle</title>
<style>
:root{--fond:#0a0f1a;--surface:#111a2b;--surface2:#1c2740;--bord:#243149;
--texte:#e8eef7;--doux:#93a3bb;--accent:#4f8ef7;--r:14px}
@media (prefers-color-scheme: light){:root{--fond:#f7f9fc;--surface:#fff;
--surface2:#eef2f8;--bord:#dde4ee;--texte:#0f172a;--doux:#5b6b83}}
*{box-sizing:border-box}body{margin:0;background:var(--fond);color:var(--texte);
font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.55}
.wrap{max-width:62rem;margin:0 auto;padding:0 1.15rem 3rem}
header{padding:2rem 0 1rem;border-bottom:1px solid var(--bord)}
h1{font-size:clamp(1.5rem,5vw,2.1rem);margin:0 0 .3rem}
.sous{color:var(--doux);margin:0}
a.retour{color:var(--accent);text-decoration:none;font-size:.85rem}
.barre{display:flex;gap:.6rem;margin:1.25rem 0}
.barre input{flex:1;font:inherit;padding:.6rem .9rem;background:var(--surface);
border:1px solid var(--bord);border-radius:999px;color:var(--texte)}
.compte{color:var(--doux);font-size:.8rem;margin:0 0 .8rem}
.carte{background:var(--surface);border:1px solid var(--bord);border-radius:var(--r);
padding:1rem 1.2rem;margin-bottom:.7rem}
.carte b{font-size:.95rem}
.carte .meta{color:var(--doux);font-size:.78rem;margin-top:.3rem}
.etiq{font-size:.68rem;color:var(--doux);border:1px solid var(--bord);
border-radius:999px;padding:.08rem .5rem;margin-left:.4rem}
.vide{color:var(--doux);font-style:italic;padding:2rem;text-align:center}
</style></head><body><div class="wrap">
<header>
<a class="retour" href="/tour/dashboard">← Retour à l'accueil</a>
<h1>Place archive</h1>
<p class="sous">Tout ce qui a été archivé, ici — trouvable, lisible, jamais
supprimé. La règle : archiver = marquer + rendre trouvable.</p>
</header>
<div class="barre"><input id="f" placeholder="Chercher dans les archives…"/></div>
<p class="compte" id="compte"></p>
<div id="liste"></div>
</div>
<script>
(function(){var donnees=__DONNEES__;
function rend(mot){mot=(mot||"").toLowerCase();
var d=donnees.filter(function(t){return !mot||(t.titre||"").toLowerCase().indexOf(mot)>=0||
(t.projet||"").toLowerCase().indexOf(mot)>=0||(t.tags||"").toLowerCase().indexOf(mot)>=0;});
document.getElementById("compte").textContent=d.length+" tâche(s) archivée(s)";
var l=document.getElementById("liste");l.innerHTML="";
if(!d.length){l.innerHTML='<div class="vide">Rien dans les archives'+(mot?' pour « '+mot+' »':'')+'.</div>';return;}
d.forEach(function(t){var c=document.createElement("div");c.className="carte";
c.innerHTML='<b>'+t.titre+'</b>'+(t.etiq?'<span class="etiq">'+t.etiq+'</span>':'')+
'<div class="meta">'+(t.projet||"")+(t.date?" · "+t.date:"")+(t.tags?" · "+t.tags:"")+'</div>';
l.appendChild(c);});}
document.getElementById("f").addEventListener("input",function(){rend(this.value);});
rend("");})();
</script></body></html>"""


class PlaceArchive(http.Controller):

    @http.route("/tour/archives", type="http", auth="user", website=False)
    def archives(self, **kw):
        if not request.env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        T = request.env["project.task"].sudo().search(
            [("active", "=", False)], order="write_date desc", limit=400)
        donnees = []
        for t in T:
            donnees.append({
                "titre": (t.name or "")[:120],
                "projet": t.project_id.display_name or "",
                "date": (str(t.write_date or t.create_date or "")[:10]),
                "tags": ", ".join((t.tag_ids.mapped("name"))[:3]),
                "etiq": "archivée",
            })
        import json as _json
        import markupsafe as _m
        js = _json.dumps(donnees, ensure_ascii=False).replace("</", "<\\/")
        page = _PAGE.replace("__DONNEES__", js)
        return request.make_response(_m.Markup(page),
                                     headers=[("Content-Type", "text/html; charset=utf-8")])
