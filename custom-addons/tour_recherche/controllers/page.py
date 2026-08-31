# -*- coding: utf-8 -*-
"""L'écran, en un seul fichier.

Aucun asset Odoo : la page ne dépend d'aucun fichier qui pourrait manquer, et
elle s'ouvre aussi vite sur un téléphone que sur le PC. C'est la même règle
que la page du CV — elle a déjà servi.
"""

PAGE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Où chercher</title>
<style>
 :root{--fond:#0a0f1a;--surface:#111a2b;--surface2:#1c2740;--bord:#243149;
       --texte:#e8eef7;--doux:#93a3bb;--accent:#4f8ef7;--rouge:#f2545b;
       --vert:#3ecf8e;--r:14px}
 @media (prefers-color-scheme: light){
   :root{--fond:#f7f9fc;--surface:#fff;--surface2:#eef2f8;--bord:#dde4ee;
         --texte:#0f172a;--doux:#5b6b83}}
 *{box-sizing:border-box}
 body{margin:0;background:var(--fond);color:var(--texte);line-height:1.6;
      font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
      -webkit-font-smoothing:antialiased}
 .wrap{max-width:62rem;margin:0 auto;padding:0 1.15rem}
 header{padding:2.25rem 0 1.25rem;border-bottom:1px solid var(--bord)}
 h1{font-size:clamp(1.6rem,5vw,2.4rem);margin:0 0 .35rem;letter-spacing:-.02em}
 .sous{color:var(--doux);margin:0}
 .moi{display:inline-block;margin-top:.9rem;font-size:.8rem;background:var(--surface);
      border:1px solid var(--bord);border-radius:999px;padding:.35rem .85rem}
 nav{display:flex;gap:.35rem;margin:1.25rem 0;flex-wrap:wrap}
 nav button{font:inherit;font-size:.85rem;cursor:pointer;color:var(--doux);
   background:transparent;border:1px solid var(--bord);border-radius:999px;
   padding:.4rem .9rem}
 nav button[aria-selected="true"]{background:var(--accent);border-color:var(--accent);
   color:#fff}
 .barre{display:flex;gap:.6rem;flex-wrap:wrap;margin-bottom:1.25rem}
 .barre input{flex:1;min-width:12rem;font:inherit;padding:.6rem .9rem;
   background:var(--surface);border:1px solid var(--bord);border-radius:999px;
   color:var(--texte)}
 .groupe{margin:1.75rem 0 .75rem;display:flex;align-items:baseline;gap:.6rem}
 .groupe h2{font-size:.75rem;letter-spacing:.16em;text-transform:uppercase;
   color:var(--doux);margin:0;font-weight:600}
 .groupe span{font-size:.8rem;color:var(--doux)}
 .carte{background:var(--surface);border:1px solid var(--bord);
   border-radius:var(--r);padding:1.1rem 1.25rem;margin-bottom:.75rem;
   display:flex;gap:1rem;align-items:flex-start}
 .carte.eteint{opacity:.5}
 .puce{flex:0 0 auto;width:2.4rem;height:2.4rem;border-radius:10px;
   background:var(--surface2);display:grid;place-items:center;font-size:1.2rem}
 .corps{flex:1;min-width:0}
 .titre{display:flex;flex-wrap:wrap;gap:.5rem;align-items:baseline}
 .titre b{font-size:1rem}
 .etiq{font-size:.7rem;color:var(--doux);border:1px solid var(--bord);
   border-radius:999px;padding:.1rem .55rem}
 .resume{color:var(--doux);font-size:.9rem;margin:.15rem 0 .35rem}
 .adresse{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.8rem;
   color:var(--doux);word-break:break-all}
 .comment{font-size:.85rem;color:var(--doux);margin-top:.5rem;
   padding-top:.5rem;border-top:1px dashed var(--bord);white-space:pre-wrap}
 .inter{flex:0 0 auto;display:flex;flex-direction:column;align-items:center;gap:.3rem}
 .inter button{cursor:pointer;font:inherit;font-size:.78rem;border-radius:999px;
   padding:.3rem .8rem;border:1px solid var(--bord);background:var(--surface2);
   color:var(--texte)}
 .inter button.on{background:var(--vert);border-color:var(--vert);color:#04231a}
 .inter button:disabled{cursor:not-allowed;opacity:.55}
 .inter small{color:var(--doux);font-size:.7rem}
 table{width:100%;border-collapse:collapse;font-size:.85rem}
 th{text-align:left;color:var(--doux);font-weight:600;font-size:.72rem;
   letter-spacing:.1em;text-transform:uppercase;padding:.5rem .6rem;
   border-bottom:1px solid var(--bord)}
 td{padding:.55rem .6rem;border-bottom:1px solid var(--bord)}
 tr.refus td{color:var(--rouge)}
 .vide{color:var(--doux);padding:2rem 0;text-align:center}
 .msg{margin:.75rem 0;padding:.7rem 1rem;border-radius:var(--r);
   border:1px solid var(--bord);background:var(--surface);font-size:.88rem}
 .msg.mal{border-color:var(--rouge);color:var(--rouge)}
 footer{color:var(--doux);font-size:.8rem;padding:2.5rem 0 3rem;
   border-top:1px solid var(--bord);margin-top:2.5rem}
 footer a{color:var(--accent)}
 [hidden]{display:none!important}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Où chercher</h1>
    <p class="sous">Les endroits où la tour a le droit de fouiller, et qui a le droit d'y aller.</p>
    <span class="moi" id="moi">…</span>
  </header>

  <nav>
    <button id="o-endroits" aria-selected="true">Les endroits</button>
    <button id="o-journal" aria-selected="false">Qui est passé</button>
  </nav>

  <div id="message" class="msg" hidden></div>

  <section id="vue-endroits">
    <div class="barre">
      <input id="q" type="search" placeholder="Chercher un endroit, une adresse, « candidatures »…">
    </div>
    <div id="liste"></div>
  </section>

  <section id="vue-journal" hidden>
    <table>
      <thead><tr><th>Quand</th><th>Qui</th><th>Endroit</th><th>Cherchait</th><th>Trouvé</th></tr></thead>
      <tbody id="journal"></tbody>
    </table>
    <p class="vide" id="journal-vide" hidden>Personne n'est encore passé.</p>
  </section>

  <footer>
    Cette page ne garde rien : elle demande à la tour et affiche.
    La liste, elle, vit dans <a href="/odoo/action-791">Où chercher</a>.
  </footer>
</div>

<script>
const PUCES = {mail:"✉", fichier:"🗂", web:"🌐", service:"⚙", base:"🗄", depot:"⌥", autre:"•"};
const CERCLES = {"1":"Cercle 1 — Patrick, Raphaël, opencode",
                 "2":"Cercle 2 — les agents",
                 "3":"Cercle 3 — réservé",
                 "4":"Cercle 4 — les invités en démonstration"};
let ETAT = {cercle:"4", endroits:[]};

const $ = (s) => document.querySelector(s);
const txt = (s) => String(s == null ? "" : s).replace(/[&<>"']/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

function dire(m, mal) {
  const b = $("#message");
  b.textContent = m; b.hidden = !m;
  b.classList.toggle("mal", !!mal);
}

async function charger() {
  try {
    const r = await fetch("/api/recherche/endroits", {headers:{"Accept":"application/json"}});
    if (!r.ok) throw new Error("La tour a répondu " + r.status);
    const d = await r.json();
    ETAT.cercle = d.cercle; ETAT.endroits = d.endroits;
    $("#moi").textContent = d.moi + " — " + CERCLES[d.cercle];
    dessiner();
  } catch (e) { dire("Je n'ai pas pu lire la liste : " + e.message, true); }
}

function dessiner() {
  const q = ($("#q").value || "").toLowerCase().trim();
  const gardees = ETAT.endroits.filter(s => !q ||
    (s.nom + " " + s.resume + " " + s.adresse + " " + s.pour_quoi).toLowerCase().includes(q));
  const liste = $("#liste");
  if (!gardees.length) { liste.innerHTML = '<p class="vide">Aucun endroit ne correspond.</p>'; return; }

  let html = "";
  for (const c of ["1","2","3","4"]) {
    const lot = gardees.filter(s => s.cercle === c);
    if (!lot.length) continue;
    const allumes = lot.filter(s => s.actif).length;
    html += '<div class="groupe"><h2>' + txt(CERCLES[c]) + "</h2><span>"
          + allumes + " allumé" + (allumes > 1 ? "s" : "") + " sur " + lot.length + "</span></div>";
    for (const s of lot) html += carte(s);
  }
  liste.innerHTML = html;
  liste.querySelectorAll("button[data-id]").forEach(b =>
    b.addEventListener("click", () => basculer(+b.dataset.id)));
}

function carte(s) {
  const peut = ETAT.cercle === "1";
  return '<article class="carte' + (s.actif ? "" : " eteint") + '">'
    + '<div class="puce">' + (PUCES[s.genre] || PUCES.autre) + "</div>"
    + '<div class="corps"><div class="titre"><b>' + txt(s.nom) + "</b>"
    + '<span class="etiq">' + txt(s.genre_libelle) + "</span>"
    + (s.pour_quoi ? '<span class="etiq">' + txt(s.pour_quoi) + "</span>" : "")
    + "</div>"
    + (s.resume ? '<p class="resume">' + txt(s.resume) + "</p>" : "")
    + (s.adresse ? '<div class="adresse">' + txt(s.adresse) + "</div>" : "")
    + (s.comment ? '<div class="comment">' + txt(s.comment) + "</div>" : "")
    + "</div>"
    + '<div class="inter"><button data-id="' + s.id + '" class="' + (s.actif ? "on" : "")
    + '"' + (peut ? "" : " disabled") + ">" + (s.actif ? "On cherche" : "Éteint") + "</button>"
    + "<small>" + s.passages + " passage" + (s.passages > 1 ? "s" : "") + "</small></div>"
    + "</article>";
}

async function basculer(id) {
  dire("");
  try {
    const r = await fetch("/api/recherche/basculer", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({id})});
    const d = await r.json();
    if (!r.ok) throw new Error(d.erreur || ("réponse " + r.status));
    const s = ETAT.endroits.find(x => x.id === id);
    if (s) s.actif = d.actif;
    dessiner();
  } catch (e) { dire("Je n'ai pas pu changer l'interrupteur : " + e.message, true); }
}

async function chargerJournal() {
  try {
    const r = await fetch("/api/recherche/journal");
    if (!r.ok) throw new Error("réponse " + r.status);
    const d = await r.json();
    $("#journal-vide").hidden = d.passages.length > 0;
    $("#journal").innerHTML = d.passages.map(p =>
      '<tr class="' + (p.refuse ? "refus" : "") + '"><td>' + txt(p.quand) + "</td><td>"
      + txt(p.qui) + "</td><td>" + txt(p.endroit) + "</td><td>" + txt(p.cherche)
      + "</td><td>" + (p.refuse ? "refusé" : p.trouve) + "</td></tr>").join("");
  } catch (e) { dire("Je n'ai pas pu lire le journal : " + e.message, true); }
}

function onglet(quoi) {
  const e = quoi === "endroits";
  $("#o-endroits").setAttribute("aria-selected", e);
  $("#o-journal").setAttribute("aria-selected", !e);
  $("#vue-endroits").hidden = !e;
  $("#vue-journal").hidden = e;
  if (!e) chargerJournal();
}

$("#o-endroits").addEventListener("click", () => onglet("endroits"));
$("#o-journal").addEventListener("click", () => onglet("journal"));
$("#q").addEventListener("input", dessiner);
charger();
</script>
</body>
</html>
"""
