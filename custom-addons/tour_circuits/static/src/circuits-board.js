/* La carte des circuits — v2 « simulateur Arduino » (04/08, retour Patrick :
 * « un petit carre comme les vraies cartes, les circuits a l'interieur,
 * pas entrecoupes »).
 *
 * Le principe change : on ne dessine plus les 70 gabarits d'un coup (le plat
 * de spaghettis), on regarde UNE piste a la fois, comme sur un simulateur.
 *  - une petite plaque rectangulaire, trous de montage, connecteur de bord ;
 *  - les agents en puces, ranges en grille DANS la plaque ;
 *  - un selecteur au-dessus : par defaut les circuits EN COURS ; choisir un
 *    circuit dessine SA piste, seule, a angles droits — zero croisement ;
 *  - une piste de gabarit reste cliquable : clic = relancer le circuit.
 * Les donnees arrivent en JSON (#board-data). */
(function () {
  var data;
  try { data = JSON.parse(document.getElementById("board-data").textContent); }
  catch (e) { return; }
  var agents = data.agents || [], circuits = data.circuits || [];
  var svg = document.getElementById("board");
  if (!svg) return;
  var NS = "http://www.w3.org/2000/svg";
  var W = 1040, H = 620;
  var COULEURS = {
    "standard": "#d4a24c", "prod": "#e26d5a", "coffre": "#7fb2e5",
    "relecture": "#9fd07a", "revision": "#9fd07a",
    "publication": "#c3a6e8", "detection": "#c3a6e8"
  };
  function coul(t) { return COULEURS[t] || "#d4a24c"; }
  function el(n, a, p) {
    var e = document.createElementNS(NS, n);
    for (var k in a) e.setAttribute(k, a[k]);
    if (p) p.appendChild(e);
    return e;
  }
  function lancer(mid) {
    if (!mid) return;
    var fd = new FormData();
    fd.append("csrf_token", window.TDC_CSRF || "");
    fd.append("modele_id", mid);
    fetch("/tour/cockpit/circuits/lancer",
          { method: "POST", body: fd, credentials: "same-origin" })
      .then(function () { window.location.reload(); })
      .catch(function () { window.location.reload(); });
  }

  // ---- Les noms d'agents (Patrick en dernier : c'est la sortie) ----------
  var noms = [];
  agents.forEach(function (a) { if (noms.indexOf(a.name) < 0) noms.push(a.name); });
  circuits.forEach(function (c) { (c.portes || []).forEach(function (p) {
    if (noms.indexOf(p.agent) < 0) noms.push(p.agent); }); });
  var patron = null;
  for (var i = 0; i < noms.length; i++) {
    if (/patrick/i.test(noms[i])) { patron = noms.splice(i, 1)[0]; break; }
  }
  noms.sort();
  if (patron) noms.push(patron);

  // ---- La plaque : un petit rectangle, comme une vraie carte -------------
  var PAD = 60;
  var BX = PAD, BY = 46, BW = W - 2 * PAD, BH = H - BY - 30;
  el("rect", { x: 0, y: 0, width: W, height: H, fill: "#0b1210" }, svg);
  var plaque = el("g", {}, svg);
  el("rect", { x: BX, y: BY, width: BW, height: BH, rx: 14,
    fill: "#0a3320", stroke: "#155c38", "stroke-width": 2.5 }, plaque);
  var grid = el("pattern", { id: "pcb-grid", width: 26, height: 26,
                             patternUnits: "userSpaceOnUse" }, svg);
  el("path", { d: "M 26 0 L 0 0 0 26", fill: "none",
               stroke: "#0e4429", "stroke-width": 1 }, grid);
  el("rect", { x: BX, y: BY, width: BW, height: BH, rx: 14,
    fill: "url(#pcb-grid)" }, plaque);
  // trous de montage aux quatre coins de LA PLAQUE
  [[BX + 22, BY + 22], [BX + BW - 22, BY + 22],
   [BX + 22, BY + BH - 22], [BX + BW - 22, BY + BH - 22]].forEach(function (t) {
    el("circle", { cx: t[0], cy: t[1], r: 10, fill: "#0b1210",
      stroke: "#c9a24c", "stroke-width": 3 }, plaque);
  });
  // connecteur de bord (les pattes dorees, comme un Arduino)
  for (var pi = 0; pi < 14; pi++) {
    el("rect", { x: BX + 60 + pi * ((BW - 120) / 13) - 5, y: BY - 9,
      width: 10, height: 16, rx: 2, fill: "#e8c169" }, plaque);
  }
  // serigraphie : le nom de la carte
  el("text", { x: BX + 26, y: BY + BH - 34, "font-size": 11,
    fill: "#7fae93", "font-family": "ui-monospace,monospace",
    "letter-spacing": "2" }, plaque).textContent = "TOUR DE CONTROLE — REV 2026.08";

  // ---- Les puces : une grille propre a l'interieur -----------------------
  var CW = 150, CH = 44;
  var COLS = Math.min(4, Math.max(2, Math.ceil(Math.sqrt(noms.length))));
  var ROWS = Math.ceil(noms.length / COLS);
  var gx = (BW - 90 - CW) / Math.max(1, COLS - 1);
  var gy = (BH - 130 - CH) / Math.max(1, ROWS - 1);
  var pos = {};
  noms.forEach(function (nom, idx) {
    var r = Math.floor(idx / COLS), c = idx % COLS;
    // la derniere ligne se centre si elle n'est pas pleine
    var dansLigne = (r === ROWS - 1) ? (noms.length - r * COLS) : COLS;
    var offset = (COLS - dansLigne) * gx / 2;
    pos[nom] = {
      x: BX + 45 + CW / 2 + offset + c * gx,
      y: BY + 58 + CH / 2 + r * gy,
      patron: nom === patron
    };
  });
  function puce(nom) {
    var p = pos[nom];
    var g = el("g", { transform: "translate(" + (p.x - CW / 2) + "," +
                      (p.y - CH / 2) + ")", "data-nom": nom }, plaque);
    // lueur d'agent sélectionné (posée par le filtre ci-dessous)
    el("rect", { x: -4, y: -4, width: CW + 8, height: CH + 8, rx: 9,
      fill: "none", stroke: "none", "stroke-width": 2 }, g).setAttribute("data-lueur", "1");
    for (var k = 0; k < 6; k++) {
      var px = 18 + k * (CW - 36) / 5;
      el("rect", { x: px - 3, y: -6, width: 6, height: 10, rx: 1,
        fill: "#e8c169" }, g);
      el("rect", { x: px - 3, y: CH - 4, width: 6, height: 10, rx: 1,
        fill: "#e8c169" }, g);
    }
    el("rect", { x: 0, y: 0, width: CW, height: CH, rx: 6,
      fill: p.patron ? "#1c2a3a" : "#101c16",
      stroke: p.patron ? "#e8c169" : "#2e5a40", "stroke-width": 1.5 }, g);
    el("circle", { cx: 12, cy: 12, r: 3, fill: "#0b1210",
      stroke: "#3f6b52", "stroke-width": 1 }, g);
    var t1 = el("text", { x: CW / 2, y: 19, "text-anchor": "middle",
      "font-size": 12.5, "font-weight": 700, fill: "#e8edc0",
      "font-family": "ui-monospace,monospace" }, g);
    t1.textContent = nom;
    var t2 = el("text", { x: CW / 2, y: 32, "text-anchor": "middle",
      "font-size": 8, fill: "#8fae9a",
      "font-family": "ui-monospace,monospace" }, g);
    t2.textContent = p.patron ? "SORTIE — TRANCHE" : "AGENT";
  }
  noms.forEach(puce);

  // ---- Le calque des pistes (efface et redessine a chaque choix) ---------
  var calque = el("g", {}, plaque);
  // 10/08 (Merline) : les points lumineux des circuits EN COURS, au-dessus
  // des pistes. Position = porte courante de l'instance, rechargée toutes
  // les ~20 s depuis /tour/cockpit/circuits/positions (même idée que la
  // carte des appels API : la donnée qui avance le long de sa piste).
  var pointsG = el("g", {}, plaque);
  var pistesEnCours = [];
  var pointsActifs = [];
  var rafAnim = null;
  var titre = el("text", { x: W / 2, y: 26, "text-anchor": "middle",
    "font-size": 13, "font-weight": 600, fill: "#d4e6da",
    "font-family": "ui-monospace,monospace" }, svg);

  // routage a angles droits : sortie par le bas de A, couloir horizontal,
  // remontee vers B. Chaque saut prend son propre couloir : pas de croisement.
  function tracer(c, seule) {
    var portes = c.portes || [];
    var chemin = [];
    portes.forEach(function (p) {
      if (pos[p.agent]) chemin.push(p.agent);
    });
    if (chemin.length < 2) return;
    var col = coul(c.type_operation);
    var g = el("g", {}, calque);
    var d = "";
    var sauts = [];   // longueur de chaque saut (pour la position des portes)
    for (var i = 0; i + 1 < chemin.length; i++) {
      var A = pos[chemin[i]], B = pos[chemin[i + 1]];
      var lane = (A.y + B.y) / 2 + (i % 2 === 0 ? 1 : -1) * (10 + 8 * i);
      lane = Math.max(BY + 40, Math.min(BY + BH - 40, lane));
      var x0 = A.x, y0 = A.y + CH / 2 + 6;
      var x1 = B.x, y1 = B.y - CH / 2 - 6;
      if (A.y > B.y) { y0 = A.y - CH / 2 - 6; y1 = B.y + CH / 2 + 6; }
      d += (d ? " " : "") + "M " + x0 + " " + y0 +
           " L " + x0 + " " + lane +
           " L " + x1 + " " + lane +
           " L " + x1 + " " + y1;
      sauts.push(Math.abs(y0 - lane) + Math.abs(x1 - x0) + Math.abs(lane - y1));
      // une via a chaque coude
      el("circle", { cx: x0, cy: lane, r: 3.5, fill: "#0b1210",
        stroke: col, "stroke-width": 1.6 }, g);
      el("circle", { cx: x1, cy: lane, r: 3.5, fill: "#0b1210",
        stroke: col, "stroke-width": 1.6 }, g);
      // le sens : une pastille numerotee au depart du saut
      el("circle", { cx: x0, cy: y0, r: 8, fill: col }, g);
      el("text", { x: x0, y: y0 + 3.4, "text-anchor": "middle",
        "font-size": 9, "font-weight": 700, fill: "#0b1210",
        "font-family": "ui-monospace,monospace" }, g).textContent = String(i + 1);
    }
    var path = el("path", { d: d, fill: "none", stroke: col,
      "stroke-width": 3.2, "stroke-linecap": "round",
      "stroke-linejoin": "round" }, g);
    g.insertBefore(path, g.firstChild);
    if (c.etat === "gabarit") {
      path.setAttribute("stroke-dasharray", "8 6");
      path.setAttribute("class", "trace rejouable");
      path.setAttribute("title", "Relancer : " + (c.name || ""));
      path.addEventListener("click", function () { lancer(c.modele_id); });
    }
    // 10/08 : un circuit EN COURS garde sa piste + la géométrie de ses portes
    // (positions cumulées le long du chemin) pour placer un point lumineux à
    // la porte courante.
    if (c.etat === "en_cours") {
      var cumul = [0];
      for (var si = 0; si < sauts.length; si++) cumul.push(cumul[si] + sauts[si]);
      pistesEnCours.push({
        path: path, cumul: cumul, instance_id: c.instance_id,
        etape_courante: c.etape_courante || 0, etape_nom: c.etape_nom || "",
        col: col, name: c.name || "",
      });
    }
    if (seule) {
      titre.textContent = (c.name || "").substring(0, 80) +
        (c.etat === "gabarit" ? "  — pointilles : clic sur la piste = relancer" : "");
    }
  }

  function dessiner(choix) {
    while (calque.firstChild) calque.removeChild(calque.firstChild);
    while (pointsG.firstChild) pointsG.removeChild(pointsG.firstChild);
    pistesEnCours = [];
    pointsActifs = [];
    titre.textContent = "";
    if (choix === "encours") {
      var enCours = circuits.filter(function (c) { return c.etat === "en_cours"; });
      enCours.slice(0, 4).forEach(function (c) { tracer(c, enCours.length === 1); });
      titre.textContent = enCours.length
        ? enCours.length + " circuit(s) en cours — choisis-en un dans la liste pour suivre sa piste"
        : "Aucun circuit en cours — choisis un gabarit dans la liste pour voir sa piste";
    } else {
      var c = circuits.filter(function (x) {
        return String(x.modele_id || x.id) === String(choix); })[0];
      if (c) tracer(c, true);
    }
    dessinerPoints();
  }

  // ---- Les points lumineux des circuits EN COURS (10/08, Merline) --------
  // Un point par circuit en cours : il avance le long de sa piste, sa cible
  // est la porte courante de l'instance (etape_courante). Les positions sont
  // relues depuis la base toutes les ~20 s (route /tour/cockpit/circuits/
  // positions) : quand une porte est franchie, le point avance tout seul.
  function dessinerPoints() {
    pistesEnCours.forEach(function (p) {
      var etape = Math.max(0, Math.min(p.etape_courante, p.cumul.length - 1));
      var g = el("g", {}, pointsG);
      var halo = el("circle", { r: 13, fill: "none", stroke: p.col,
        "stroke-width": 2.5, opacity: 0 }, g);
      var noyau = el("circle", { r: 5, fill: p.col, stroke: "#0b1210",
        "stroke-width": 1.5 }, g);
      var inf = el("title", {}, g);
      inf.textContent = (p.name || "") + " — " + (p.etape_nom || "porte courante");
      pointsActifs.push({
        path: p.path, cible: p.cumul[etape] || 0, t: p.cumul[etape] || 0,
        col: p.col, halo: halo, noyau: noyau, instance_id: p.instance_id,
      });
      poserPoint(pointsActifs[pointsActifs.length - 1]);
    });
    if (!rafAnim && pointsActifs.length) lancerAnimation();
  }

  function poserPoint(p) {
    var pl = p.path.getTotalLength();
    var tt = Math.max(0, Math.min(pl, p.t));
    var pt = p.path.getPointAtLength(tt);
    p.halo.setAttribute("cx", pt.x); p.halo.setAttribute("cy", pt.y);
    p.noyau.setAttribute("cx", pt.x); p.noyau.setAttribute("cy", pt.y);
  }

  function lancerAnimation() {
    var debut = null;
    function frame(ts) {
      if (!debut) debut = ts;
      var dt = Math.min(0.05, (ts - debut) / 1000);
      debut = ts;
      pointsActifs.forEach(function (p) {
        var dist = p.cible - p.t;
        var pas = 55 * dt;   // px/s le long du chemin
        if (Math.abs(dist) > 1) {
          p.t += (dist > 0 ? 1 : -1) * Math.min(pas, Math.abs(dist));
        }
        poserPoint(p);
        var s = (Math.sin(performance.now() / 280) + 1) / 2;
        p.halo.setAttribute("opacity", (0.3 + 0.55 * s).toFixed(2));
        p.halo.setAttribute("r", (12 + 7 * s).toFixed(1));
      });
      rafAnim = requestAnimationFrame(frame);
    }
    rafAnim = requestAnimationFrame(frame);
  }

  // ---- Recharge des positions toutes les ~20 s ---------------------------
  function rechargerPositions() {
    fetch("/tour/cockpit/circuits/positions", { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || !d.positions) return;
        var par = {};
        d.positions.forEach(function (x) { par[x.id] = x; });
        circuits.forEach(function (c) {
          if (c.etat !== "en_cours" || !par[c.instance_id]) return;
          c.etape_courante = par[c.instance_id].etape_courante;
          c.etape_nom = par[c.instance_id].etape_nom;
        });
        pointsActifs.forEach(function (p) {
          var info = par[p.instance_id];
          if (!info) return;
          var cumul = null;
          pistesEnCours.forEach(function (pp) {
            if (pp.instance_id === p.instance_id) cumul = pp.cumul;
          });
          if (!cumul) return;
          var etape = Math.max(0, Math.min(info.etape_courante, cumul.length - 1));
          p.cible = cumul[etape] || 0;
        });
      })
      .catch(function () {});
  }
  setInterval(rechargerPositions, 20000);

  // ---- Filtre par agent (06/08, Patrick) : chaque agent voit SES circuits.
  // Un agent choisi -> le selecteur de circuits ne propose que ceux ou il a
  // une porte, et sa puce s'illumine sur la plaque.
  var selAg = document.createElement("select");
  selAg.id = "board-agent";
  selAg.style.cssText = "margin:0 8px 10px 0;padding:7px 10px;background:#101c16;" +
    "color:#d4e6da;border:1px solid #2e5a40;border-radius:8px;" +
    "font-family:ui-monospace,monospace;font-size:12.5px;max-width:100%";
  var oTous = document.createElement("option");
  oTous.value = "";
  oTous.textContent = "— tous les agents —";
  selAg.appendChild(oTous);
  var agentsAvecPortes = [];
  circuits.forEach(function (c) { (c.portes || []).forEach(function (p) {
    if (p.agent && p.agent !== "Patrick" && agentsAvecPortes.indexOf(p.agent) < 0)
      agentsAvecPortes.push(p.agent); }); });
  agentsAvecPortes.sort();
  agentsAvecPortes.forEach(function (nom) {
    var o = document.createElement("option");
    o.value = nom;
    o.textContent = nom;
    selAg.appendChild(o);
  });
  selAg.addEventListener("change", function () {
    var nom = selAg.value;
    // illumine la puce de l'agent choisi (anneau autour)
    plaque.querySelectorAll("[data-nom]").forEach(function (g) {
      var lueur = g.querySelector("[data-lueur]");
      var actif = g.getAttribute("data-nom") === nom;
      if (lueur) {
        lueur.setAttribute("stroke", actif ? "#e8c169" : "none");
        if (actif) lueur.setAttribute("stroke-width", "2.5");
      }
    });
    if (!nom) {
      // retour au defaut : tous les circuits
      remplirCircuit(null);
      dessiner(sel.value);
      return;
    }
    var lesSiens = circuits.filter(function (c) {
      return (c.portes || []).some(function (p) { return p.agent === nom; }); });
    remplirCircuit(lesSiens);
    if (lesSiens.length) dessiner(String(lesSiens[0].modele_id || lesSiens[0].id));
    else { dessiner("encours"); }
  });
  svg.parentNode.insertBefore(selAg, svg);

  // ---- Le selecteur de circuits, insere au-dessus de la carte -------------
  function remplirCircuit(liste) {
    while (sel.firstChild) sel.removeChild(sel.firstChild);
    var o0 = document.createElement("option");
    o0.value = "encours";
    o0.textContent = "— les circuits en cours (defaut) —";
    sel.appendChild(o0);
    (liste || circuits).slice().sort(function (a, b) {
      return (a.name || "").localeCompare(b.name || ""); })
      .forEach(function (c) {
        var o = document.createElement("option");
        o.value = String(c.modele_id || c.id);
        o.textContent = (c.etat === "en_cours" ? "▶ " : "") + (c.name || "");
        sel.appendChild(o);
      });
    sel.value = "encours";
  }
  var sel = document.createElement("select");
  sel.id = "board-select";
  sel.style.cssText = "margin:0 0 10px;padding:7px 10px;background:#101c16;" +
    "color:#d4e6da;border:1px solid #2e5a40;border-radius:8px;" +
    "font-family:ui-monospace,monospace;font-size:12.5px;max-width:100%";
  sel.addEventListener("change", function () { dessiner(sel.value); });
  svg.parentNode.insertBefore(sel, svg);
  remplirCircuit(null);

  dessiner("encours");

  // ---- Legende -----------------------------------------------------------
  var libelles = { standard: "standard", prod: "prod", coffre: "Coffre",
    relecture: "relecture", publication: "publication" };
  var leg = document.getElementById("board-legend");
  if (leg) {
    Object.keys(libelles).forEach(function (t) {
      var span = document.createElement("span");
      span.innerHTML = '<span class="sw" style="background:' + coul(t) +
        '"></span>' + libelles[t];
      leg.appendChild(span);
    });
    var s = document.createElement("span");
    s.innerHTML = '<span class="sw dash" style="color:#9aa7a0"></span>' +
      'une piste a la fois, a angles droits — pointilles = gabarit, clic = relancer';
    leg.appendChild(s);
    var p = document.createElement("span");
    p.innerHTML = '<span style="display:inline-block;width:9px;height:9px;' +
      'border-radius:50%;background:#d4a24c;box-shadow:0 0 6px #d4a24c;' +
      'vertical-align:middle;margin-right:6px"></span>' +
      'rond = la porte où en est le circuit (rechargé toutes les 20 s)';
    leg.appendChild(p);
  }
})();
