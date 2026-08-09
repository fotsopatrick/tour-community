# © 2026 Patrick Orel Kamdem Fotso — Code Nomi Nomi
# -*- coding: utf-8 -*-
"""La carte vivante, facon GNS3 / Packet Tracer (07/08, Patrick).

Patrick : « je voyais plusieurs onglets EN BAS et au milieu une infra style
packet tracer, on peut cliquer sur le serveur, sur le conteneur, et voir ce
qu'il contient, ses caracteristiques ». Puis : « on pouvait utiliser un moteur
2D ou 3D leger pour ca, pour vraiment avoir l'effet gns3 ».

CE QUI EXISTAIT DEJA, ET QU'ON NE REFAIT PAS
Le releve (pose par un script de l'hote) : 6 zones,
319 noeuds, 145 liens, remis a jour tout seul. Les noeuds portent deja un
type et un detail, les liens portent deja ce qui passe dessus. C'est la
partie ingrate, elle est faite et elle tient.

CE QU'ON CHANGE : LE DESSIN
L'ancienne page /tour/cockpit/cartes affiche une liste eparpillee. GNS3 et
Packet Tracer marchent pour trois raisons, aucune n'est une couleur :
  1. un appareil est une ICONE qu'on reconnait sans lire ;
  2. les liens sont des TRAITS etiquetes : on voit qui parle a qui ;
  3. on CLIQUE et un panneau donne les caracteristiques.

POURQUOI 2D ET PAS 3D
Parce que GNS3 et Packet Tracer SONT en 2D, et que leur effet vient des trois
points ci-dessus, pas de la profondeur. Un moteur 3D impressionne dix secondes
puis gene la lecture. Le canvas 2D du navigateur suffit : aucune bibliotheque
a charger, rien a installer sur le serveur, ca demarre instantanement.
La profondeur meritera d'exister le jour ou elle voudra dire quelque chose —
par exemple empiler serveur / conteneurs / volumes pour montrer ce qui est
DANS quoi. Pas avant.

LE VRAI OBSTACLE ETAIT AILLEURS
319 elements ne rentrent pas dans une image, et une seule zone en contient
jusqu'a 75. Packet Tracer est lisible parce qu'on voit dix a vingt appareils.
D'ou les onglets EN BAS : une zone a la fois, comme la barre d'appareils de
Packet Tracer, et le milieu libre pour la carte.

Meme verrou que le reste du cockpit : base.group_system.
"""
import json
import os

from markupsafe import Markup

from odoo import http
from odoo.http import request


def _cartes_path():
    """Chemin du relevé de cartes. Paramétrable (tour_dashboard.cartes_path) ;
    par défaut vide — en édition Community, la carte vivante affiche
    « fichier absent » au lieu d'un chemin interne du serveur."""
    return request.env["ir.config_parameter"].sudo().get_param(
        "tour_dashboard.cartes_path", "")


PAGE = u"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>La carte vivante</title>
<style>
:root{--ground:#0d1116;--surface:#151b22;--surface2:#1b232b;--line:#27313b;
--line2:#3a4855;--ink:#e8eef4;--ink2:#b3c0cc;--muted:#7d8b99;--accent:#4fb3c0;
--accent2:#0f6f7a;--vert:#5cc27f;--ambre:#d7a13e;--rouge:#e8776d;--violet:#9d8df1;
--mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
--sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--sans);
font-size:14px;overflow:hidden}
.app{display:flex;flex-direction:column;height:100vh}

/* ---- barre du haut ---- */
.haut{display:flex;align-items:center;gap:14px;padding:10px 16px;
border-bottom:1px solid var(--line);background:var(--surface);flex:0 0 auto}
.haut h1{margin:0;font-size:16px;font-weight:620;letter-spacing:-.01em}
.haut .meta{font-family:var(--mono);font-size:11px;color:var(--muted)}
.haut .grandir{flex:1}
.lien{font-family:var(--mono);font-size:12px;color:var(--accent);
text-decoration:none;border:1px solid var(--line2);padding:5px 11px;border-radius:3px}
.lien:hover,.lien:focus{background:var(--surface2);outline:2px solid var(--accent);outline-offset:1px}
button.lien{background:transparent;cursor:pointer;color:var(--accent)}
button.lien:hover,.lien:focus{background:var(--surface2);outline:2px solid var(--accent);outline-offset:1px}

/* ---- scene ---- */
.scene{flex:1;position:relative;min-height:0;display:flex}
canvas{flex:1;display:block;cursor:grab;background:
radial-gradient(circle at 50% 40%, #131a21 0%, #0d1116 70%)}
canvas.attrape{cursor:grabbing}

/* ---- panneau lateral ---- */
.panneau{width:330px;flex:0 0 auto;border-left:1px solid var(--line);
background:var(--surface);overflow-y:auto;padding:16px 18px;display:none}
.panneau.ouvert{display:block}
.panneau .type{font-family:var(--mono);font-size:11px;letter-spacing:.1em;
text-transform:uppercase;color:var(--accent)}
.panneau h2{margin:5px 0 3px;font-size:18px;line-height:1.25;word-break:break-word}
.panneau .id{font-family:var(--mono);font-size:11px;color:var(--muted);word-break:break-all}
.panneau .detail{margin:12px 0 0;color:var(--ink2);line-height:1.55}
.panneau h3{font-family:var(--mono);font-size:11px;letter-spacing:.1em;
text-transform:uppercase;color:var(--muted);margin:20px 0 8px;
padding-bottom:6px;border-bottom:1px solid var(--line)}
.panneau ul{list-style:none;margin:0;padding:0}
.panneau li{padding:7px 0;border-bottom:1px solid var(--line);font-size:13px;line-height:1.45}
.panneau li:last-child{border-bottom:none}
.panneau li .fleche{color:var(--accent);font-family:var(--mono)}
.panneau li .quoi{color:var(--muted);font-family:var(--mono);font-size:11px;display:block}
.panneau li b{cursor:pointer;color:var(--ink);border-bottom:1px dotted var(--line2)}
.panneau li b:hover{color:var(--accent)}
/* ---- onglets du panneau (09/08, Merline) : fiche decoupee quand elle deborde */
.ptabs{display:flex;gap:6px;margin:12px 0 2px;border-bottom:1px solid var(--line)}
.ptab{background:none;border:1px solid transparent;border-bottom:none;color:var(--muted);
font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;
padding:7px 12px;cursor:pointer;border-radius:4px 4px 0 0}
.ptab:hover{color:var(--ink)}
.ptab.actif{color:var(--accent);border-color:var(--line);background:var(--surface2)}
.pcorps{margin-top:2px}
.ptitre{font-family:var(--mono);font-size:11px;letter-spacing:.08em;text-transform:uppercase;
color:var(--accent);margin:14px 0 2px}
.pcorps .detail{margin:10px 0 0}
.fermer{float:right;background:none;border:1px solid var(--line2);color:var(--muted);
font-family:var(--mono);font-size:12px;padding:3px 9px;border-radius:3px;cursor:pointer}
.fermer:hover{color:var(--ink);border-color:var(--accent)}

/* ---- barre du bas : les zones, comme la barre d appareils ---- */
.bas{flex:0 0 auto;border-top:1px solid var(--line);background:var(--surface);
padding:9px 14px;display:flex;gap:8px;align-items:center;overflow-x:auto}
.onglet{display:flex;align-items:center;gap:8px;background:var(--surface2);
border:1px solid var(--line);color:var(--ink2);font-family:var(--mono);
font-size:12px;padding:7px 13px;border-radius:3px;cursor:pointer;white-space:nowrap}
.onglet:hover{border-color:var(--line2);color:var(--ink)}
.onglet.actif{border-color:var(--accent);color:var(--accent);background:#10333a}
.onglet .compte{font-size:11px;color:var(--muted)}
.onglet.actif .compte{color:var(--accent)}
.aide{margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--muted);
white-space:nowrap;padding-left:14px}
/* ---- recherche dans la zone (09/08, Merline) : 195 outils d'un coup, c'est
   illisible. On ne retire rien — on filtre ce qu'on dessine par texte. */
.rech{margin-left:auto;background:var(--surface2);border:1px solid var(--line);
color:var(--ink);font-family:var(--mono);font-size:12px;padding:6px 10px;
border-radius:3px;width:170px}
.rech:focus{outline:none;border-color:var(--accent)}
.rech.vide{border-color:var(--line)}
.bas .rech + .aide{padding-left:10px;margin-left:0}
@media (max-width:760px){.panneau{position:absolute;right:0;top:0;bottom:0;z-index:5}
.aide{display:none}}
</style></head><body>
<div class="app">
  <div class="haut">
    <h1>La carte vivante</h1>
    <span class="meta" id="meta"></span>
    <span class="grandir"></span>
    <button class="lien" id="filsdroits" type="button">fils droits</button>
    <a class="lien" href="/tour/cockpit/cartes-guide">guide</a>
    <a class="lien" href="/tour/dashboard">accueil</a>
  </div>
  <div class="scene">
    <canvas id="toile"></canvas>
    <aside class="panneau" id="panneau"></aside>
  </div>
  <div class="bas" id="onglets"></div>
</div>
<script>
const DONNEES = __DONNEES__;

/* Une couleur et une forme par type : on reconnait un appareil sans lire son
   nom. C'est la premiere des trois raisons pour lesquelles Packet Tracer
   marche. */
const TYPES = {
  serveur:   {c:"#4fb3c0", f:"tour"},
  conteneur: {c:"#5cc27f", f:"boite"},
  volume:    {c:"#d7a13e", f:"disque"},
  base:      {c:"#d7a13e", f:"disque"},
  site:      {c:"#9d8df1", f:"page"},
  webapp:    {c:"#9d8df1", f:"page"},
  page:      {c:"#9d8df1", f:"page"},
  agent:     {c:"#e8776d", f:"rond"},
  outil:     {c:"#7d8b99", f:"losange"},
  internet:  {c:"#e8eef4", f:"nuage"},
  humain:    {c:"#e8776d", f:"rond"},
  defaut:    {c:"#7d8b99", f:"boite"}
};
const typeDe = t => TYPES[(t||"").toLowerCase()] || TYPES.defaut;

const toile = document.getElementById("toile");
const ctx = toile.getContext("2d");
const panneau = document.getElementById("panneau");
let zone = null, noeuds = [], liens = [], choisi = null, survole = null;
let vue = {x:0, y:0, k:1}, glisse = null, bouge = false;
let sauve = {};
try { sauve = JSON.parse(localStorage.getItem("carte-vivante-disposition")) || {}; } catch (e) {}

/* Placement DETERMINISTE : la carte doit etre la meme a chaque ouverture.
   Un placement qui saute a chaque fois empeche de se faire une carte mentale.
   On range par type en colonnes, puis on desserre un peu.
   L'ESPACEMENT S'ADAPTE (09/08, Merline) : avant, le pas etait fixe (130x92),
   donc 195 outils debordaient du canvas et leurs textes se chevauchaient.
   On calcule le pas pour que la grille tienne TOUJOURS dans la toile, avec un
   minimum de 74px en X (forme 30 + texte) et 56px en Y. Plus la zone est
   peuplee, plus le pas se resserre — mais jamais en dessous du minimum. */
function placer(zn){
  const parType = {};
  zn.noeuds.forEach(n => { (parType[n.type] = parType[n.type] || []).push(n); });
  const types = Object.keys(parType).sort();
  const largeur = Math.max(300, toile.width), hauteur = Math.max(300, toile.height);
  const pos = {};
  const grilles = {};

  // D'abord : la grille de chaque type (colonnes, lignes, pas), SANS position.
  // On borne le nombre de colonnes pour que la grille tienne dans le canvas :
  // chaque type a droit à une tranche = largeur / nombreDeTypes. Le pas peut
  // descendre sous 76px si le type est très peuplé — des nœuds serrés mais
  // visibles valent mieux que des nœuds sortis du canvas (non cliquables).
  const trancheMax = (largeur - 20) / Math.max(1, types.length);
  types.forEach(t => {
    const nb = parType[t].length;
    let parCol = Math.max(1, Math.round(Math.sqrt(nb * largeur / Math.max(1, hauteur))));
    // Le nombre de colonnes doit être suffisant pour tenir dans la tranche.
    parCol = Math.max(parCol, Math.ceil(nb / Math.max(1, Math.floor((trancheMax - 10) / 50))));
    const parLigne = Math.ceil(nb / parCol) || 1;
    const pasXg = Math.min(Math.max(50, (trancheMax - 10) / (parCol + 1)), 190);
    const pasYg = Math.min(Math.max(50, (hauteur - 30) / (parLigne + 1)), 120);
    const largeurType = (parCol - 1) * pasXg + 60;
    grilles[t] = {parCol, parLigne, pasXg, pasYg, largeurType};
  });

  // La largeur totale de toutes les colonnes de types (après ajustement).
  const totalL = types.reduce((acc, t) => acc + grilles[t].largeurType, 0);

  // On recentre le tout dans le canvas : le facteur ne peut que DIMINUER
  // légèrement (on ne réduit jamais en dessous du pas minimal, déjà borné).
  let facteur = 1;
  if (totalL > largeur - 20 && types.length > 1) {
    facteur = (largeur - 20) / totalL;
  }

  // Placement : chaque type est centré sur sa tranche, les tranches empilées
  // de gauche à droite dans l'espace disponible. Le facteur réduit AUSSI la
  // largeur des tranches (pas seulement le pas) pour que les centres restent
  // dans le canvas.
  let acc = -(totalL * facteur) / 2;
  types.forEach((t, i) => {
    const g = grilles[t];
    const largeurTranche = g.largeurType * facteur;
    const xCentre = largeur / 2 + acc + largeurTranche / 2;
    const pasXreel = g.pasXg * facteur;
    g.groupe = parType[t];
    g.groupe.forEach((n, j) => {
      const col = j % g.parCol, rang = Math.floor(j / g.parCol);
      pos[n.id] = {
        x: xCentre + (col - (g.parCol - 1) / 2) * pasXreel,
        y: hauteur / 2 + (rang - (g.parLigne - 1) / 2) * g.pasYg
      };
    });
    acc += largeurTranche;
  });
  const res = zn.noeuds.map(n => Object.assign({}, n, pos[n.id] || {x:largeur/2, y:hauteur/2}));
  const sv = (sauve[zn.id] || {}).noeuds;
  if (sv) res.forEach(n => { if (sv[n.id]) { n.x = sv[n.id][0]*largeur; n.y = sv[n.id][1]*hauteur; n.fixe = true; } });
  return res;
}

function dessinerForme(n, x, y, r, couleur, fort){
  ctx.save();
  ctx.lineWidth = fort ? 2.5 : 1.5;
  ctx.strokeStyle = couleur;
  ctx.fillStyle = fort ? couleur + "33" : "#151b22";
  const f = typeDe(n.type).f;
  ctx.beginPath();
  if (f === "rond" || f === "nuage") { ctx.arc(x, y, r, 0, Math.PI*2); }
  else if (f === "losange") { ctx.moveTo(x, y-r); ctx.lineTo(x+r, y); ctx.lineTo(x, y+r); ctx.lineTo(x-r, y); ctx.closePath(); }
  else if (f === "disque") { ctx.ellipse(x, y, r*1.15, r*0.72, 0, 0, Math.PI*2); }
  else if (f === "tour") { ctx.rect(x-r*0.78, y-r, r*1.56, r*2); }
  else if (f === "page") { ctx.rect(x-r*0.72, y-r*0.9, r*1.44, r*1.8); }
  else { ctx.rect(x-r, y-r*0.8, r*2, r*1.6); }
  ctx.fill(); ctx.stroke();
  if (f === "tour"){ ctx.beginPath(); ctx.moveTo(x-r*0.78, y-r*0.35); ctx.lineTo(x+r*0.78, y-r*0.35);
                     ctx.moveTo(x-r*0.78, y+r*0.3); ctx.lineTo(x+r*0.78, y+r*0.3); ctx.stroke(); }
  if (f === "disque"){ ctx.beginPath(); ctx.ellipse(x, y-r*0.28, r*1.15, r*0.72, 0, 0, Math.PI*2); ctx.stroke(); }
  ctx.restore();
}

function dessiner(){
  const L = toile.width, H = toile.height;
  ctx.setTransform(1,0,0,1,0,0);
  ctx.clearRect(0,0,L,H);
  ctx.save();
  ctx.translate(vue.x, vue.y); ctx.scale(vue.k, vue.k);

  const par = {}; noeuds.forEach(n => par[n.id] = n);
  // les traits d'abord, pour qu'ils passent derriere les appareils
  liens.forEach(l => {
    const a = par[l.de], b = par[l.vers];
    if (!a || !b) return;
    const relie = choisi && (l.de === choisi.id || l.vers === choisi.id);
    const wp = (l.w || []).map(w => ({x: w[0]*L, y: w[1]*H}));
    const pts = wp.length ? [a].concat(wp, [b]) : routeOrtho(a, b);
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    for (let k = 1; k < pts.length; k++) ctx.lineTo(pts[k].x, pts[k].y);
    ctx.strokeStyle = relie ? "#4fb3c0" : "#27313b";
    ctx.lineWidth = relie ? 2 : 1;
    ctx.stroke();
    if (relie && l.quoi){
      const m = milieu(pts);
      ctx.fillStyle = "#7d8b99"; ctx.font = "10px ui-monospace,monospace";
      ctx.textAlign = "center";
      ctx.fillText(l.quoi, m.x, m.y - 5);
    }
    // les plis : visibles pour qu'on puisse les attraper et les retirer
    wp.forEach(w => {
      ctx.beginPath();
      ctx.arc(w.x, w.y, 3.5, 0, Math.PI*2);
      ctx.fillStyle = relie ? "#4fb3c0" : "#3a4855";
      ctx.fill();
    });
  });

  noeuds.forEach(n => {
    const t = typeDe(n.type);
    const fort = (choisi && n.id === choisi.id) || (survole && n.id === survole.id);
    dessinerForme(n, n.x, n.y, 15, t.c, fort);
    ctx.fillStyle = fort ? "#e8eef4" : "#b3c0cc";
    ctx.font = (fort ? "600 " : "") + "11px ui-sans-serif,system-ui,sans-serif";
    ctx.textAlign = "center";
    // Nom sur DEUX lignes, calibré sur la place (09/08, Merline) : 171
    // collisions mesurées parce qu'un nom tronqué à 22 caractères (≈143px)
    // débordait du pas de grille (76px). On découpe en deux lignes dont la
    // largeur est bornée par la colonne réelle, jamais au-delà.
    const nom = (n.nom || n.id);
    // La largeur de colonne effective : le plus petit écart horizontal entre
    // ce nœud et un voisin (ou 76px par défaut). On ne dépasse jamais.
    let espace = 76;
    for (const autre of noeuds) {
      if (autre === n) continue;
      const dx = Math.abs(autre.x - n.x);
      if (dx > 4 && dx < espace) espace = dx;
    }
    const maxParLigne = Math.max(5, Math.floor((espace - 4) / 6.3));
    let l1 = nom, l2 = "";
    if (nom.length > maxParLigne) {
      const coupure = nom.lastIndexOf("-", maxParLigne);
      const cut = coupure > 5 ? coupure : maxParLigne;
      l1 = nom.slice(0, cut);
      l2 = nom.slice(cut);
    }
    if (l1.length > maxParLigne) l1 = l1.slice(0, maxParLigne - 1) + "…";
    if (l2.length > maxParLigne) l2 = l2.slice(0, maxParLigne - 1) + "…";
    ctx.fillText(l1, n.x, n.y + 29);
    if (l2) ctx.fillText(l2, n.x, n.y + 43);
  });
  ctx.restore();
}

function versMonde(ev){
  const r = toile.getBoundingClientRect();
  return {x: (ev.clientX - r.left - vue.x)/vue.k, y: (ev.clientY - r.top - vue.y)/vue.k};
}
function sous(p){
  for (let i = noeuds.length-1; i >= 0; i--){
    const n = noeuds[i];
    if (Math.abs(p.x-n.x) < 20 && Math.abs(p.y-n.y) < 20) return n;
  }
  return null;
}

/* ---- les fils pliables ---- */

function milieu(pts){
  let tot = 0, i;
  for (i = 1; i < pts.length; i++) tot += Math.hypot(pts[i].x-pts[i-1].x, pts[i].y-pts[i-1].y);
  if (!tot) return pts[0];
  const cible = tot/2; let acc = 0;
  for (i = 1; i < pts.length; i++){
    const dx = pts[i].x-pts[i-1].x, dy = pts[i].y-pts[i-1].y;
    const d = Math.hypot(dx, dy);
    if (acc + d >= cible){ const t = (cible-acc)/d; return {x: pts[i-1].x+dx*t, y: pts[i-1].y+dy*t}; }
    acc += d;
  }
  return pts[pts.length-1];
}

function distSeg(p, a, b){
  const dx = b.x-a.x, dy = b.y-a.y;
  const l2 = dx*dx + dy*dy;
  if (!l2) return Math.hypot(p.x-a.x, p.y-a.y);
  let t = ((p.x-a.x)*dx + (p.y-a.y)*dy) / l2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p.x-(a.x+dx*t), p.y-(a.y+dy*t));
}

function polyLien(l){
  const a = parDe(l.de), b = parDe(l.vers);
  if (!a || !b) return null;
  const wp = (l.w || []).map(w => ({x: w[0]*toile.width, y: w[1]*toile.height}));
  return wp.length ? [a].concat(wp, [b]) : routeOrtho(a, b);
}

function parDe(id){
  for (const n of noeuds) if (n.id === id) return n;
  return null;
}

function lienSous(p){
  for (let i = liens.length-1; i >= 0; i--){
    const pts = polyLien(liens[i]);
    if (!pts) continue;
    for (let k = 1; k < pts.length; k++){
      if (distSeg(p, pts[k-1], pts[k]) < 10) return {lien: liens[i], seg: k-1};
    }
  }
  return null;
}

function waypointSous(p){
  for (const l of liens){
    const pts = polyLien(l);
    if (!pts) continue;
    for (let k = 1; k <= pts.length-2; k++){
      if (Math.hypot(p.x-pts[k].x, p.y-pts[k].y) < 8) return {lien: l, i: k-1};
    }
  }
  return null;
}

function cleLien(l){ return l.de + "\u2192" + l.vers; }

/* Tracé automatique : des traits DROITS et PERPENDICULAIRES, comme un
   schéma de câblage. La diagonale ne sert que quand les deux appareils
   sont quasi alignés (on garde alors le trait droit). */
function routeOrtho(a, b){
  const dx = b.x - a.x, dy = b.y - a.y;
  if (Math.abs(dx) < 30 || Math.abs(dy) < 30) return [a, b];
  const mx = (a.x + b.x) / 2;
  return [a, {x: mx, y: a.y}, {x: mx, y: b.y}, b];
}

function stocker(){
  if (!zone) return;
  const sv = (sauve[zone.id] = sauve[zone.id] || {});
  sv.noeuds = {};
  noeuds.forEach(n => { if (n.fixe) sv.noeuds[n.id] = [n.x/toile.width, n.y/toile.height]; });
  sv.liens = {};
  liens.forEach(l => { if (l.w && l.w.length) sv.liens[cleLien(l)] = l.w.map(c => c.slice()); });
  try { localStorage.setItem("carte-vivante-disposition", JSON.stringify(sauve)); } catch (e) {}
}

function ouvrir(n){
  choisi = n;
  const t = typeDe(n.type);
  const mes = liens.filter(l => l.de === n.id || l.vers === n.id);
  const par = {}; noeuds.forEach(x => par[x.id] = x);
  const aTour = (n.tour || []).length > 0;

  let h = '<button class="fermer" id="btf">fermer</button>';
  h += '<div class="type" style="color:' + t.c + '">' + (n.type || "?") + '</div>';
  h += '<h2>' + (n.nom || n.id) + '</h2>';
  h += '<div class="id">' + n.id + '</div>';

  // LES ONGLETS (09/08, Merline) : une fiche qui déborde ne se lit plus.
  // On découpe le panneau — « À propos » pour ce qu'est l'item et ce qui le
  // relie, « Dans la tour » pour ce qu'en dit la recherche unifiée.
  h += '<div class="ptabs">';
  h += '<button class="ptab actif" data-tab="a">À propos</button>';
  if (aTour) h += '<button class="ptab" data-tab="tour">Dans la tour</button>';
  h += '</div>';

  h += '<div class="pcorps" data-corp="a">';
  if (n.detail) h += '<p class="detail">' + n.detail + '</p>';
  h += '<h3>Ce qui y est relie &middot; ' + mes.length + '</h3>';
  if (!mes.length) h += '<ul><li>Rien ne le relie dans cette zone.</li></ul>';
  else {
    h += '<ul>';
    mes.forEach(l => {
      const sortant = l.de === n.id;
      const autre = par[sortant ? l.vers : l.de];
      const nom = autre ? (autre.nom || autre.id) : (sortant ? l.vers : l.de);
      h += '<li><span class="fleche">' + (sortant ? "&rarr;" : "&larr;") + '</span> ' +
           (autre ? '<b data-id="' + autre.id + '">' + nom + '</b>' : nom) +
           (l.quoi ? '<span class="quoi">' + l.quoi + '</span>' : '') + '</li>';
    });
    h += '</ul>';
  }
  h += '</div>';

  if (aTour) {
    const NOMS = {taches:"Tâches", guides:"Guides", decisions:"Décisions",
                  missions:"Missions", reponses:"Réponses", discussions:"Discussions"};
    h += '<div class="pcorps" data-corp="tour" style="display:none">';
    h += '<h3>Ce que dit la tour</h3>';
    (n.tour || []).forEach(src => {
      const lib = NOMS[src.source] || src.source;
      h += '<div class="ptitre">' + lib + ' &middot; ' + src.items.length + '</div>';
      h += '<ul>';
      src.items.forEach(it => {
        h += '<li>' + it.nom + '</li>';
      });
      h += '</ul>';
    });
    h += '</div>';
  }

  panneau.innerHTML = h;
  panneau.classList.add("ouvert");

  // Bascule d'onglet : on ne réaffiche que le corps demandé.
  panneau.querySelectorAll(".ptab").forEach(b => {
    b.onclick = () => {
      panneau.querySelectorAll(".ptab").forEach(x => x.classList.remove("actif"));
      panneau.querySelectorAll(".pcorps").forEach(x => x.style.display = "none");
      b.classList.add("actif");
      const corps = panneau.querySelector('[data-corp="' + b.dataset.tab + '"]');
      if (corps) corps.style.display = "block";
    };
  });

  document.getElementById("btf").onclick = () => {
    panneau.classList.remove("ouvert"); choisi = null; redim(); dessiner();
  };
  panneau.querySelectorAll("b[data-id]").forEach(b => {
    b.onclick = () => { const c = noeuds.find(x => x.id === b.dataset.id); if (c) ouvrir(c); };
  });
  redim(); dessiner();
}

function charger(i){
  zone = DONNEES.zones[i];
  document.querySelectorAll(".onglet").forEach((o, j) =>
    o.classList.toggle("actif", j === i));
  liens = zone.liens || [];
  const sv = (sauve[zone.id] || {}).liens;
  liens.forEach(l => { l.w = sv && sv[cleLien(l)] ? sv[cleLien(l)].map(c => c.slice()) : []; });
  noeuds = placer(zone);
  choisi = null; panneau.classList.remove("ouvert");
  vue = {x:0, y:0, k:1};
  const filtre = document.getElementById("rech");
  if (filtre) { filtre.value = ""; filtre.classList.remove("vide"); }
  metaZone();
  dessiner();
}

function metaZone(){
  const filtre = document.getElementById("rech");
  const mot = filtre && filtre.value ? filtre.value.trim().toLowerCase() : "";
  const affiches = mot ? noeuds.filter(n =>
    (n.nom||"").toLowerCase().indexOf(mot) >= 0 ||
    (n.detail||"").toLowerCase().indexOf(mot) >= 0 ||
    (n.type||"").toLowerCase().indexOf(mot) >= 0 ||
    (n.refs||"").toLowerCase().indexOf(mot) >= 0) : noeuds;
  document.getElementById("meta").textContent =
    zone.nom + " — " + affiches.length + " sur " + noeuds.length + " elements, " +
    liens.length + " liens · releve " + DONNEES.releve_le +
    (mot ? " · filtre: «" + mot + "»" : "");
  return affiches;
}

// Le dessin ne montre QUE les noeuds qui passent le filtre : les autres
// restent dans les donnees (rien n'est retire), ils ne sont juste pas
// dessines. Les liens entre noeuds visibles restent visibles.
// RECENTRAGE (09/08, Merline) : un filtre qui isole 1 noeud sur 203 le
// laissait a sa position dans la grille complete — perdu dans le canvas,
// l'ecran semblait ne pas reagir. On rejoue le placement sur les visibles
// pour les ramener au centre.
function dessinerFiltre(){
  const visibles = metaZone();
  const ids = {}; visibles.forEach(n => ids[n.id] = true);
  const tous = noeuds;
  const tousLiens = liens;
  noeuds = visibles;
  liens = liens.filter(l => ids[l.de] && ids[l.vers]);
  // On repose la grille sur les seuls visibles (positions recentrees).
  const zoneFiltree = Object.assign({}, zone, {noeuds: visibles});
  const places = placer(zoneFiltree);
  noeuds = places;
  // un seul resultat : on l'ouvre directement pour montrer ce que c'est ;
  // zero resultat : on ferme le panneau (l'ancien item n'a plus de sens).
  if (visibles.length === 1) ouvrir(places[0]);
  else {
    if (visibles.length === 0) { panneau.classList.remove("ouvert"); choisi = null; }
    dessiner();
  }
  noeuds = tous;
  liens = tousLiens;
}

function redim(){
  const r = toile.parentElement.getBoundingClientRect();
  const p = panneau.classList.contains("ouvert") ? panneau.offsetWidth : 0;
  toile.width = Math.max(200, r.width - p);
  toile.height = Math.max(200, r.height);
  if (zone) noeuds = placer(zone).map(n => {
    const a = noeuds.find(x => x.id === n.id);
    return a && a.fixe ? a : n;
  });
}

toile.addEventListener("mousedown", ev => {
  const p = versMonde(ev); const n = sous(p);
  if (n){ glisse = {noeud:n, dx:p.x-n.x, dy:p.y-n.y}; bouge = false; }
  else {
    const w = waypointSous(p);
    if (w){ glisse = {fil:w.lien, k:w.i}; bouge = false; }
    else {
      const f = lienSous(p);
      if (f){
        const l = f.lien;
        if (!l.w) l.w = [];
        l.w.splice(f.seg, 0, [p.x/toile.width, p.y/toile.height]);
        glisse = {fil:l, k:f.seg}; bouge = false;
        dessiner();
      }
      else { glisse = {vue:true, x:ev.clientX-vue.x, y:ev.clientY-vue.y}; bouge = false; toile.classList.add("attrape"); }
    }
  }
});
toile.addEventListener("mousemove", ev => {
  if (glisse && glisse.vue){ vue.x = ev.clientX-glisse.x; vue.y = ev.clientY-glisse.y; bouge = true; dessiner(); return; }
  if (glisse && glisse.fil){
    const p = versMonde(ev);
    glisse.fil.w[glisse.k] = [p.x/toile.width, p.y/toile.height];
    bouge = true; dessiner(); return;
  }
  if (glisse){ const p = versMonde(ev); glisse.noeud.x = p.x-glisse.dx; glisse.noeud.y = p.y-glisse.dy;
               glisse.noeud.fixe = true; bouge = true; dessiner(); return; }
  const n = sous(versMonde(ev));
  if (n !== survole){ survole = n; toile.style.cursor = n ? "pointer" : "grab"; dessiner(); }
});
window.addEventListener("mouseup", ev => {
  if (glisse && (glisse.noeud || glisse.fil)) stocker();
  glisse = null; toile.classList.remove("attrape");
});
toile.addEventListener("click", ev => {
  if (bouge) return;
  const n = sous(versMonde(ev));
  if (n) ouvrir(n);
});
toile.addEventListener("dblclick", ev => {
  const p = versMonde(ev); const w = waypointSous(p);
  if (w && w.lien.w && w.lien.w.length){
    w.lien.w.splice(w.i, 1);
    stocker(); dessiner();
  }
});
toile.addEventListener("wheel", ev => {
  ev.preventDefault();
  const f = ev.deltaY < 0 ? 1.12 : 1/1.12;
  const r = toile.getBoundingClientRect();
  const mx = ev.clientX-r.left, my = ev.clientY-r.top;
  vue.x = mx - (mx - vue.x)*f; vue.y = my - (my - vue.y)*f;
  vue.k = Math.max(0.25, Math.min(4, vue.k*f));
  dessiner();
}, {passive:false});
window.addEventListener("resize", () => { redim(); dessiner(); });

const barre = document.getElementById("onglets");
DONNEES.zones.forEach((z, i) => {
  const b = document.createElement("button");
  b.className = "onglet";
  b.innerHTML = z.nom + ' <span class="compte">' + (z.noeuds||[]).length + '</span>';
  b.onclick = () => charger(i);
  barre.appendChild(b);
});
const aide = document.createElement("span");
aide.className = "aide";
aide.textContent = "clic : ouvrir · tirer un fil : le plier · double-clic sur un pli : l'enlever · molette : zoomer";
barre.appendChild(aide);

// LA RECHERCHE DANS LA ZONE (09/08, Merline) : taper un mot ne retire rien,
// cela reduit ce qui est dessine aux noeuds qui le contiennent (nom, detail,
// type, refs). Pour 195 outils ou 76 webapps, c'est la difference entre une
// tache et une pelote.
const rech = document.createElement("input");
rech.id = "rech";
rech.className = "rech";
rech.type = "search";
rech.placeholder = "filtrer la zone…";
// RECHERCHE MULTI-ONGLET (09/08, Merline) : la saisie cherche dans la zone
// affichée ET, si rien n'y correspond, bascule automatiquement sur l'onglet
// où se trouve la première occurrence (nom, détail, type, refs). On ne
// perd jamais une occurrence parce qu'on n'est pas sur le bon onglet.
rech.addEventListener("input", () => {
  const mot = rech.value.trim().toLowerCase();
  if (!mot) { dessinerFiltre(); return; }
  // (09/08, Patrick) : taper recentre la carte sur le noeud, le marque
  // (orange + liens) et ouvre son panneau à droite. On cherche le nom et
  // l'id d'abord, puis le détail/type.
  const trouv = noeuds.find(n =>
    (n.nom || "").toLowerCase() === mot ||
    (n.id || "").toLowerCase() === mot) ||
    noeuds.find(n =>
      (n.nom || "").toLowerCase().indexOf(mot) >= 0 ||
      (n.id || "").toLowerCase().indexOf(mot) >= 0 ||
      (n.detail || "").toLowerCase().indexOf(mot) >= 0 ||
      (n.type || "").toLowerCase().indexOf(mot) >= 0);
  if (trouv) { centrerSur(trouv); ouvrir(trouv); return; }
  const dansZone = metaZone().length;
  if (dansZone > 0) { dessinerFiltre(); return; }
  // rien dans la zone active : on cherche dans les autres zones
  for (let i = 0; i < DONNEES.zones.length; i++) {
    const z = DONNEES.zones[i];
    if (z === zone) continue;
    const trouv = (z.noeuds || []).find(n =>
      (n.nom || "").toLowerCase().indexOf(mot) >= 0 ||
      (n.detail || "").toLowerCase().indexOf(mot) >= 0 ||
      (n.type || "").toLowerCase().indexOf(mot) >= 0 ||
      (n.refs || "").toLowerCase().indexOf(mot) >= 0);
    if (trouv) {
      const idx = DONNEES.zones.indexOf(z);
      charger(idx);
      rech.value = mot;
      dessinerFiltre();
      return;
    }
  }
  // aucune zone ne contient le mot : on filtre la zone active (0 résultat)
  dessinerFiltre();
});
// Recentre la vue sur un noeud (09/08, Patrick) : l'item trouvé par la
// recherche passe au centre, avec un zoom minimal lisible.
function centrerSur(n){
  const L = toile.width, H = toile.height;
  if (vue.k < 0.9) vue.k = 0.9;
  vue.x = L/2 - n.x*vue.k;
  vue.y = H/2 - n.y*vue.k;
}

barre.insertBefore(rech, barre.firstChild);

document.getElementById("filsdroits").onclick = () => {
  liens.forEach(l => { l.w = []; });
  stocker(); dessiner();
};

redim();
charger(DONNEES.depart);
</script></body></html>
"""

MANQUE = u"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"/>
<title>La carte vivante</title></head>
<body style="background:#0d1116;color:#e8eef4;font-family:system-ui;padding:40px">
<h1>La carte n'a pas encore ete relevee</h1>
<p>Le fichier <code>__CHEMIN__</code> est absent ou illisible.</p>
<p>Ce qui le fabrique : <code>bash ~/tour/deploy/carte-zones.sh</code></p>
<p style="color:#7d8b99">__ERREUR__</p>
<p><a style="color:#4fb3c0" href="/tour/dashboard">retour a l'accueil</a></p>
</body></html>"""


GUIDE_PAGE = u"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Guide de la carte vivante — Tour de contrôle</title>
<style>
:root{--fond:#0c1219;--surface:#131c26;--panel:#17222e;--line:#253340;
--ink:#dce6f0;--muted:#8598a8;--faint:#5e7183;--accent:#e0a44c;
--good:#35b36a;--crit:#e06055;--mono:ui-monospace,Consolas,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--fond);color:var(--ink);
font-family:system-ui,"Segoe UI",Roboto,sans-serif;line-height:1.65}
.wrap{max-width:860px;margin:0 auto;padding:2rem 1.2rem 4rem}
header{display:flex;align-items:center;gap:1rem;border-bottom:1px solid var(--line);
padding-bottom:1rem;margin-bottom:1.6rem}
h1{font-size:1.5rem;margin:0}
h2{font-size:1.15rem;margin:1.8rem 0 .4rem;color:var(--accent)}
h3{font-size:1rem;margin:1.2rem 0 .3rem}
p,li{color:var(--muted)}
code{background:var(--panel);border:1px solid var(--line);border-radius:5px;
padding:.05rem .35rem;font-family:var(--mono);font-size:.9em;color:var(--ink)}
.zones{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:.8rem}
.zone{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.9rem 1rem}
.zone b{color:var(--ink)}
.zone .n{font-family:var(--mono);font-size:.8rem;color:var(--accent)}
.gestes{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:1rem 1.2rem}
a.lien{color:var(--accent);text-decoration:none;font-size:.9rem}
a.lien:hover{text-decoration:underline}
.puce{display:inline-block;width:.7rem;height:.7rem;border-radius:2px;margin-right:.35rem}
table{border-collapse:collapse;width:100%;font-size:.9rem}
td,th{text-align:left;padding:.45rem .6rem;border-bottom:1px solid var(--line)}
th{color:var(--faint);font-size:.78rem;text-transform:uppercase;letter-spacing:.5px}
</style></head><body><div class="wrap">
<header>
  <h1>La carte vivante — guide</h1>
  <span class="grandir"></span>
  <a class="lien" href="/tour/cockpit/carte-vivante">← la carte</a>
  <a class="lien" href="/tour/dashboard">accueil</a>
</header>

<p>La carte vivante est la <b>photo de l'infrastructure</b> : ce qui tourne, sur
quelle machine, relié à quoi. Elle est <b>relevée</b> — pas dessinée à la main.
Un script lit docker, la base, les crons et le Caddyfile, et fabrique un JSON
que la page dessine. Ce qui n'est pas lisible n'apparaît pas.</p>

<h2>Les zones</h2>
<p>Six zones, chacune une carte. Le nombre entre parenthèses = le nombre
d'éléments relevés dans la zone.</p>
<div class="zones">
  <div class="zone"><b>Les serveurs</b> <span class="n">(4)</span>
    <p>Internet, VPS1 (la tour), VPS2 (le second), le Raspberry Pi de la
    maison. Les liens : HTTPS vers le VPS1, SSH vers le VPS2, sauvegarde
    VPS1→VPS2, tunnel inversé VPS1→Pi (Ollama).</p></div>
  <div class="zone"><b>Les conteneurs</b> <span class="n">(13+8)</span>
    <p>Ce qui tourne. Les <code>c_</code> sont sur le VPS1, les <code>c2_</code>
    sur le VPS2 (depuis le 09/08). Détail : l'image, l'état, et le nombre de
    fichiers écrits dans sa couche.</p></div>
  <div class="zone"><b>Les volumes</b> <span class="n">(22+5)</span>
    <p>Les espaces de travail qui survivent au conteneur. Les <code>v_</code>
    sont sur le VPS1, les <code>v2_</code> sur le VPS2. Un conteneur sans son
    volume perd son espace de travail.</p></div>
  <div class="zone"><b>Les webapps</b> <span class="n">(76)</span>
    <p>Les pages qu'on ouvre : les applications de la tour et les sites
    publics. Le lien « servi par » va vers le conteneur Caddy.</p></div>
  <div class="zone"><b>L'équipe</b> <span class="n">(26)</span>
    <p>Les agents, leur rôle, leur moteur. Le lien « le bus » montre qu'ils
    parlent à redis.</p></div>
  <div class="zone"><b>Les outils</b> <span class="n">(202)</span>
    <p>Les scripts de <code>deploy/</code> et les crons. Les outils de
    sécurité y sont : <code>defense-reseau.sh</code>,
    <code>verrouillage-urgence.sh</code>, <code>veille-intrusion.sh</code>,
    <code>pare-feu.sh</code>.</p></div>
</div>

<h2>Comment lire la carte</h2>
<div class="gestes">
<table>
<tr><th>Geste</th><th>Effet</th></tr>
<tr><td>Cliquer sur un élément</td><td>Ouvre son détail (image, état, machine)</td></tr>
<tr><td>Tirer un fil (lien)</td><td>Le plier — replie cette connexion pour alléger la vue</td></tr>
<tr><td>Double-clic sur un pli</td><td>L'enlever</td></tr>
<tr><td>Molette</td><td>Zoomer</td></tr>
<tr><td>« fils droits » (en haut)</td><td>Replier tous les liens d'un coup — la carte remet les fils « droits » (rectilignes) au lieu des courbes</td></tr>
<tr><td>« filtrer la zone… »</td><td>Chercher par nom dans la zone affichée</td></tr>
</table>
</div>

<h2>Les couleurs des types</h2>
<table>
<tr><th>Type</th><th>Couleur</th><th>Ce que c'est</th></tr>
<tr><td>serveur</td><td><span class="puce" style="background:#4fb3c0"></span>turquoise</td><td>une machine</td></tr>
<tr><td>conteneur</td><td><span class="puce" style="background:#5cc27f"></span>vert</td><td>un conteneur docker</td></tr>
<tr><td>volume</td><td><span class="puce" style="background:#d7a13e"></span>ocre</td><td>un volume docker</td></tr>
<tr><td>webapp</td><td><span class="puce" style="background:#9d8df1"></span>violet</td><td>une page qu'on ouvre</td></tr>
<tr><td>outil</td><td><span class="puce" style="background:#7d8b99"></span>gris</td><td>un script ou un cron</td></tr>
</table>

<h2>Ce que la carte sait et ce qu'elle ignore</h2>
<p>La carte montre ce qui est <b>relevé</b> au moment du scan (le JSON est
régénéré toutes les 10 minutes). Un conteneur arrêté, un volume nommé par un
hash, un outil hors de <code>deploy/</code> n'apparaissent pas. Si tu cherches
quelque chose qui manque : le relevé vit dans
<code>deploy/carte-zones.sh</code>, et le JSON dans
<code>~/atelier/cartes.json</code>.</p>

<p><a class="lien" href="/tour/cockpit/carte-vivante">← revenir à la carte</a></p>
</div></body></html>"""


class TourCarteVivante(http.Controller):

    @http.route("/tour/cockpit/carte-vivante", type="http", auth="user",
                website=False, csrf=False)
    def carte(self, **kw):
        env = request.env
        if not env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")

        donnees, erreur = None, ""
        JSON_PATH = _cartes_path()
        try:
            if os.path.exists(JSON_PATH):
                with open(JSON_PATH, "r", encoding="utf-8") as f:
                    # strict=False : un caractere de controle egare dans un
                    # detail rendait TOUT le releve illisible et la carte
                    # disparaissait (vu le 07/08). Mieux vaut une carte avec
                    # un detail bizarre qu aucune carte.
                    donnees = json.loads(f.read(), strict=False)
            else:
                erreur = "fichier absent"
        except Exception as e:  # noqa: BLE001 — on montre l'erreur, jamais un blanc
            erreur = str(e)

        zones = (donnees or {}).get("zones") or []
        if not zones:
            html = MANQUE.replace("__CHEMIN__", JSON_PATH).replace("__ERREUR__", erreur)
            return request.make_response(
                Markup(html),
                headers=[("Content-Type", "text/html; charset=utf-8")])

        # ENRICHIR CHAQUE NOEUD AVEC LA RECHERCHE DE LA TOUR (09/08, Merline).
        # Quand on clique sur un item (agent, serveur, conteneur, outil), le
        # panneau de droite affiche ce qu'en dit la tour : tâches, guides,
        # décisions, missions, réponses, discussions qui portent son nom.
        # Même moteur que la recherche unifiée (/tour/recherche) : une requête
        # ILIKE par source, les 6 premiers résultats, rien d'inventé.
        sources = [
            ("taches", "project_task", "name"),
            ("guides", "tour_guide", "name"),
            ("decisions", "decision_fiche", "name"),
            ("missions", "atelier_mission", "name"),
            ("reponses", "reponse_fiche", "name"),
            ("discussions", "discussion_fil", "name"),
        ]
        for zone in zones:
            for noeud in zone.get("noeuds") or []:
                nom = (noeud.get("nom") or "").strip()
                # On ne cherche pas sur des noms d'appareil (c_tour-odoo-1)
                # ni sur Internet : la recherche porterait sur des acronymes
                # internes que la tour ne connaît pas. On enrichit les nœuds
                # nommés (agents, serveurs, outils, sites).
                if not nom or len(nom) < 2:
                    continue
                mot = "%" + nom.replace("%", "") + "%"
                tour = []
                for cle, table, colonne in sources:
                    try:
                        env.cr.execute(
                            "SELECT id, %s AS nom FROM %s WHERE %s ILIKE %%s "
                            "ORDER BY id DESC LIMIT 6" % (colonne, table, colonne),
                            (mot,))
                        lignes = [{"id": r[0], "nom": (r[1] or "")[:80]}
                                  for r in env.cr.fetchall()]
                        if lignes:
                            tour.append({"source": cle, "items": lignes})
                    except Exception:  # noqa: BLE001 — table absente = source absente
                        continue
                if tour:
                    noeud["tour"] = tour

        # On ENTRE PAR LES SERVEURS, pas par les 319 elements. Packet Tracer
        # est lisible parce qu'on voit dix appareils, pas trois cents : la
        # zone la plus petite est la meilleure porte d'entree.
        depart = 0
        petite = None
        for i, z in enumerate(zones):
            n = len(z.get("noeuds") or [])
            if n and (petite is None or n < petite):
                petite, depart = n, i

        charge = {
            "releve_le": (donnees or {}).get("releve_le") or "?",
            "depart": depart,
            "zones": [{
                "id": z.get("id"),
                "nom": z.get("nom") or z.get("id") or "?",
                "noeuds": z.get("noeuds") or [],
                "liens": z.get("liens") or [],
            } for z in zones],
        }

        # On n'utilise PAS le formatage % : la feuille de style contient des
        # pourcentages (50%, 100%) et Python essaierait de les lire comme des
        # codes. C'est l'erreur 500 du 07/08 sur la page smolagents.
        html = PAGE.replace(
            "__DONNEES__",
            json.dumps(charge, ensure_ascii=False).replace("</", "<\\/"))
        return request.make_response(
            Markup(html), headers=[("Content-Type", "text/html; charset=utf-8")])

    @http.route("/tour/cockpit/cartes-guide", type="http", auth="user",
                website=False, csrf=False)
    def guide(self, **kw):
        """Le guide de la carte vivante : ce que chaque zone montre, comment
        la lire, ce que les couleurs et les fils veulent dire."""
        env = request.env
        if not env.user.has_group("base.group_system"):
            return request.redirect("/tour/dashboard")
        html = GUIDE_PAGE
        return request.make_response(
            Markup(html), headers=[("Content-Type", "text/html; charset=utf-8")])
