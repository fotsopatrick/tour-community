/* La carte des appels API — plan « circuit imprimé » animé (10/08, Merline).
 *
 * Dans le langage de la carte des circuits (tour_circuits/circuits-board.js) :
 *  - la clé DeepSeek est l'ALIMENTATION, en bas de la plaque ;
 *  - chaque agent qui consomme est un COMPOSANT (puce) ;
 *  - chaque flux d'appels est une PISTE dont l'épaisseur porte le volume ;
 *  - des points lumineux circulent le long des pistes : ce sont les appels.
 * Les données arrivent en JSON (#board-data), la carte est dessinée en SVG,
 * aucune librairie externe. Trois périodes sont servies d'un coup ; les
 * boutons basculent sans recharger.
 */
(function () {
  var data;
  try { data = JSON.parse(document.getElementById("board-data").textContent); }
  catch (e) { return; }
  var svg = document.getElementById("board");
  if (!svg) return;
  var NS = "http://www.w3.org/2000/svg";
  var W = 1040, H = 620;

  // ---- couleurs (fond de plaque, traces, niveaux) ------------------------
  var FOND = "#0b1210";
  var VIA = "#123524";
  var COULS = ["#9fd07a", "#c9d36a", "#d4a24c", "#e2a03f", "#e26d5a"];
  function niveau(ratio) {
    var r = Math.max(0, Math.min(0.999, ratio));
    var i = Math.floor(r * COULS.length);
    return COULS[i];
  }

  // ---- état ---------------------------------------------------------------
  var periode = "7j";
  var enPause = false;
  var raf = null;
  var pointsActifs = [];   // {path, pl, t, vitesse, couleur}
  var derniereFrame = 0;

  function el(n, a, p) {
    var e = document.createElementNS(NS, n);
    for (var k in a) e.setAttribute(k, a[k]);
    if (p) p.appendChild(e);
    return e;
  }
  function fmt(n) {
    if (n >= 1e9) return (n / 1e9).toFixed(2) + " Md";
    if (n >= 1e6) return (n / 1e6).toFixed(1) + " M";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + " k";
    return String(n);
  }

  function couleursPeriode() { return data.periodes[periode]; }
  function agentsTries(d) {
    return (d.agents || []).slice().sort(function (a, b) {
      return (b.entree + b.sortie) - (a.entree + a.sortie);
    });
  }
  function maxJets(d) {
    var m = 0;
    (d.agents || []).forEach(function (a) {
      var j = (a.entree || 0) + (a.sortie || 0);
      if (j > m) m = j;
    });
    return m;
  }

  // ---- dessin -------------------------------------------------------------
  function dessiner() {
    svg.textContent = "";
    pointsActifs = [];
    var d = couleursPeriode();
    var agents = agentsTries(d);
    var maxj = maxJets(d);
    var maxCout = 0;
    agents.forEach(function (a) { if ((a.cout || 0) > maxCout) maxCout = a.cout; });

    // fond de plaque + vias
    el("rect", { x: 0, y: 0, width: W, height: H, fill: FOND }, svg);
    for (var vx = 30; vx < W; vx += 46) {
      for (var vy = 26; vy < H; vy += 46) {
        el("circle", { cx: vx, cy: vy, r: 1.6, fill: VIA }, svg);
      }
    }

    // l'alimentation : la clé DeepSeek, en bas au centre
    var core = { x: W / 2, y: 552, w: 260, h: 40 };
    el("rect", { x: core.x - core.w / 2, y: core.y - core.h / 2,
                 width: core.w, height: core.h, rx: 6, fill: "#17301f",
                 stroke: "#2f7d4f", "stroke-width": 1.5 }, svg);
    for (var b = -5; b <= 5; b++) {
      el("rect", { x: core.x + b * 22 - 4, y: core.y - core.h / 2 - 8,
                   width: 8, height: 9, fill: "#2f7d4f" }, svg);
    }
    el("text", { x: core.x, y: core.y - 4, "text-anchor": "middle",
                 fill: "#9fd07a", "font-size": 15, "font-weight": 700 }, svg)
      .textContent = "CLÉ DEEPSEEK";
    var sous = el("text", { x: core.x, y: core.y + 12, "text-anchor": "middle",
                            fill: "#5f8f6b", "font-size": 9.5 }, svg);
    sous.textContent = (data.coeur.modele || "") + " · tarif in 0.25 / out 1.0 € par million";

    // placement des puces : 2 rangées, la basse décalée d'une demi-colonne
    var n = agents.length;
    var nCols = Math.max(1, Math.ceil(n / 2));
    var M = 70, ESP = (W - 2 * M) / nCols;
    var P = { w: 118, h: 46 };
    var y0 = 132, y1 = 300;
    var positions = [];
    agents.forEach(function (a, i) {
      var rang = Math.floor(i / nCols);
      var col = i % nCols;
      var x = M + (col + (rang === 1 ? 0.5 : 0)) * ESP + ESP / 2;
      if (rang === 1 && col >= nCols - 1) x = M + (nCols - 0.5) * ESP; // dernière, au bord
      var y = rang === 0 ? y0 : y1;
      positions.push({ a: a, x: x, y: y, rang: rang, col: col });
    });

    // ---- les pistes (d'abord) --------------------------------------------
    var depass = [];
    positions.forEach(function (p, i) {
      var jets = (p.a.entree || 0) + (p.a.sortie || 0);
      var ratio = maxj ? Math.log(1 + jets) / Math.log(1 + maxj) : 0;
      var coutRatio = maxCout ? (p.a.cout || 0) / maxCout : 0;
      var yRail = 396 + i * 10;
      var path = el("path", {
        d: "M " + p.x + " " + (p.y + P.h / 2) +
           " L " + p.x + " " + yRail +
           " L " + core.x + " " + yRail +
           " L " + core.x + " " + (core.y - core.h / 2),
        fill: "none", stroke: niveau(coutRatio),
        "stroke-width": Math.round((1.5 + 7 * ratio) * 10) / 10,
        "stroke-linecap": "round", "stroke-linejoin": "round",
        opacity: 0.5 + 0.5 * ratio
      }, svg);
      depass.push({ p: p, path: path, ratio: ratio, coutRatio: coutRatio, jets: jets });
    });

    // ---- les composants (au-dessus) --------------------------------------
    positions.forEach(function (p) {
      var ratio = maxCout ? (p.a.cout || 0) / maxCout : 0;
      var g = el("g", { "class": "appels-puce", cursor: "pointer" }, svg);
      var px = p.x - P.w / 2, py = p.y - P.h / 2;
      // broches
      for (var b2 = 0; b2 < 6; b2++) {
        var yy = py + 8 + b2 * 6;
        el("rect", { x: px - 5, y: yy, width: 6, height: 3, fill: "#3a4b40" }, g);
        el("rect", { x: px + P.w - 1, y: yy, width: 6, height: 3, fill: "#3a4b40" }, g);
      }
      // corps
      var corps = el("rect", { x: px, y: py, width: P.w, height: P.h, rx: 5,
                               fill: "#13261a", stroke: niveau(ratio),
                               "stroke-width": 2 }, g);
      var nom = el("text", { x: p.x, y: py + 19, "text-anchor": "middle",
                             fill: "#dce8dd", "font-size": 11.5, "font-weight": 700 }, g);
      nom.textContent = p.a.agent || "?";
      var sousT = el("text", { x: p.x, y: py + 34, "text-anchor": "middle",
                               fill: niveau(ratio), "font-size": 9.5 }, g);
      sousT.textContent = (p.a.nb || 0) + " appels · " + fmt((p.a.entree || 0) + (p.a.sortie || 0)) +
                          " jetons · " + ((p.a.cout || 0).toFixed(3)) + " €";
      // halo pulsant sur le TOP 3 (les endroits qui consomment le plus)
      if (positions.indexOf(p) < 3 && (p.a.cout || 0) > 0) {
        el("circle", { "class": "appels-halo", cx: p.x, cy: p.y, r: P.w / 2 + 10,
                       fill: "none", stroke: niveau(ratio), "stroke-width": 2,
                       opacity: 0 }, g);
      }
      g.addEventListener("click", function () { detail(p.a, d); });
      g.addEventListener("mouseenter", function () {
        nom.setAttribute("fill", "#ffffff");
      });
      g.addEventListener("mouseleave", function () {
        nom.setAttribute("fill", "#dce8dd");
      });
    });

    // ---- les points qui circulent (les appels) ----------------------------
    depass.forEach(function (dp) {
      var nb = Math.max(1, Math.round(dp.ratio * 7));
      var pl = dp.path.getTotalLength();
      for (var k = 0; k < nb; k++) {
        var c = el("circle", { r: 3, fill: niveau(dp.coutRatio), opacity: 0.95 }, svg);
        pointsActifs.push({ path: dp.path, pl: pl, c: c, vitesse: 0.18 + 0.45 * dp.ratio,
                            t: Math.random() });
      }
    });

    // légende + ligne de vie
    var legend = document.getElementById("appels-legend");
    if (legend) {
      legend.textContent = "";
      ["Trace fine = peu d'appels", "Trace épaisse = beaucoup d'appels",
       "Vert = faible dépense", "Jaune = moyenne", "Rouge = forte dépense",
       "Rond = un appel qui circule", "Halo = le top 3 de la période"].forEach(function (t) {
        var d2 = document.createElement("span");
        d2.textContent = t;
        d2.style.marginRight = "14px";
        legend.appendChild(d2);
      });
    }
    var live = document.getElementById("appels-live");
    if (live) {
      live.textContent = (d.totaux.nb || 0) + " appels · " +
        ((d.totaux.cout || 0).toFixed(3)) + " € · période " + periode;
    }
    animerBars(d.serie || []);
    if (!raf && !enPause) lancer();
  }

  // ---- animation ----------------------------------------------------------
  function lancer() {
    if (raf) return;
    var debut = null;
    function frame(ts) {
      if (!debut) debut = ts;
      var dt = Math.min(0.05, (ts - debut) / 1000);
      debut = ts;
      if (!enPause) {
        for (var i = 0; i < pointsActifs.length; i++) {
          var p = pointsActifs[i];
          p.t += p.vitesse * dt;
          if (p.t >= 1) p.t = Math.random() * 0.2;
          var pt = p.path.getPointAtLength(p.t * p.pl);
          p.c.setAttribute("cx", pt.x);
          p.c.setAttribute("cy", pt.y);
        }
        var halos = svg.querySelectorAll(".appels-halo");
        var s = (Math.sin(performance.now() / 300) + 1) / 2;
        halos.forEach(function (h) {
          h.setAttribute("opacity", (0.25 + 0.55 * s).toFixed(2));
        });
      }
      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
  }

  // ---- interaction --------------------------------------------------------
  function detail(a, d) {
    var box = document.getElementById("appels-detail");
    if (!box) return;
    var totalCout = d.totaux.cout || 0;
    box.innerHTML =
      '<div class="c-h" style="display:flex;align-items:baseline;gap:8px">' +
      '<span class="c-n" style="font-size:15px;font-weight:700">' + (a.agent || "?") + '</span>' +
      '<span class="tag blue">' + periode + '</span></div>' +
      '<div class="detail-row"><span>Appels</span><b>' + (a.nb || 0) + '</b></div>' +
      '<div class="detail-row"><span>Jetons entrée</span><b>' + fmt(a.entree || 0) + '</b></div>' +
      '<div class="detail-row"><span>Jetons sortie</span><b>' + fmt(a.sortie || 0) + '</b></div>' +
      '<div class="detail-row"><span>Coût estimé</span><b>' + (a.cout || 0).toFixed(3) + ' €</b></div>' +
      '<div class="detail-row"><span>Part de la dépense</span><b>' +
      (totalCout ? ((a.cout / totalCout) * 100).toFixed(1) : "0") + ' %</b></div>' +
      '<div class="detail-row"><span>Refus (budget)</span><b>' + (a.refus || 0) + '</b></div>' +
      '<p class="hint" style="margin:8px 0 0">Ce composant est relié à la clé DeepSeek : ' +
      'chaque appel part d\'ici vers l\'API et revient avec la réponse.</p>';
  }

  function animerBars(serie) {
    var bars = document.querySelectorAll("#appels-bars .bar");
    if (!bars.length) return;
    var max = 1;
    serie.forEach(function (s) { if (s.nb > max) max = s.nb; });
    bars.forEach(function (b, i) {
      var s = serie[i];
      var h = s ? Math.max(6, Math.round((s.nb / max) * 100)) : 4;
      b.style.height = h + "%";
    });
  }

  document.getElementById("appels-periodes").addEventListener("click", function (e) {
    var b = e.target;
    if (b.tagName !== "BUTTON" || !b.dataset.periode) return;
    periode = b.dataset.periode;
    this.querySelectorAll("button").forEach(function (x) { x.classList.remove("actif"); });
    b.classList.add("actif");
    dessiner();
  });
  var pauseBtn = document.getElementById("appels-pause");
  pauseBtn.addEventListener("click", function () {
    enPause = !enPause;
    pauseBtn.textContent = enPause ? "▶ Lecture" : "⏸ Pause";
  });

  // au survol d'une puce, on arrête momentanément les points ? non — on démarre.
  dessiner();
})();
