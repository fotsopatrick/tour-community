/* PACMAN CIRCUITS — chaque circuit est un labyrinthe.
 *
 * Le pacman = la DONNÉE qui avance de porte en porte (le circuit en cours).
 * Les pastilles = les PORTES : grises = à venir, vertes = passées (le circuit
 * a franchi la porte). Les murs = la structure du circuit.
 *
 * C'est le « travail réel et gouverné » en format jeu : on VOIT la donnée
 * manger les portes une par une — comme le signal qui avance dans le circuit.
 */
(function () {
  "use strict";

  var canvas = document.getElementById("pacman");
  if (!canvas) return;
  var data;
  try { data = JSON.parse(document.getElementById("pacman-data").textContent); }
  catch (e) { return; }
  var ctx = canvas.getContext("2d");

  var COLS = 19, ROWS = 19, CELL = 26;
  canvas.width = COLS * CELL;
  canvas.height = ROWS * CELL;

  // --- le circuit à montrer : le premier « en cours », sinon le premier ---
  var circuits = (data.circuits || []).filter(function (c) { return c.etat === "en_cours"; });
  if (!circuits.length) circuits = data.circuits || [];
  if (!circuits.length) { return; }
  var circuit = circuits[0];
  var portes = circuit.portes || [];

  // --- les murs : bordure + blocs internes (décor de labyrinthe) ---
  var murs = {};
  function mur(x, y) { murs[x + "," + y] = true; }
  for (var i = 0; i < COLS; i++) { mur(i, 0); mur(i, ROWS - 1); }
  for (var j = 0; j < ROWS; j++) { mur(0, j); mur(COLS - 1, j); }
  var blocs = [
    [3, 3], [3, 4], [3, 5], [COLS - 4, 3], [COLS - 4, 4], [COLS - 4, 5],
    [3, ROWS - 4], [3, ROWS - 5], [3, ROWS - 6],
    [COLS - 4, ROWS - 4], [COLS - 4, ROWS - 5], [COLS - 4, ROWS - 6],
    [Math.floor(COLS / 2), 7], [Math.floor(COLS / 2), 8], [Math.floor(COLS / 2), 9],
    [Math.floor(COLS / 2), ROWS - 8], [Math.floor(COLS / 2), ROWS - 9], [Math.floor(COLS / 2), ROWS - 10],
  ];
  blocs.forEach(function (c) { mur(c[0], c[1]); });

  // --- le chemin (serpent) qui évite les murs ---
  var path = [];
  for (var r = 1; r <= ROWS - 2; r++) {
    var cols = [];
    for (var c = 1; c <= COLS - 2; c++) cols.push(c);
    if (r % 2 === 0) cols.reverse();
    for (var k = 0; k < cols.length; k++) {
      if (murs[cols[k] + "," + r]) continue;
      path.push({ x: cols[k], y: r });
    }
  }

  // --- les portes, placées à intervalle régulier sur le chemin ---
  var pas = Math.max(1, Math.floor(path.length / (portes.length + 1)));
  var gateIndex = [];
  for (var g = 0; g < portes.length; g++) gateIndex.push(pas * (g + 1));

  // combien de portes déjà franchies (l'étape courante du circuit)
  var etape = Math.max(0, Math.min(portes.length, circuit.etape_courante || 0));
  var mange = {};
  for (var g0 = 0; g0 < etape; g0++) mange[g0] = true;

  var avance = 0;
  var VITESSE = 0.55; // cellules par frame (~30 cellules/s à ×1)

  // --- lecture / pause (06/08, Patrick : « j'ai demandé un play ») ---
  // On pouvait régler la vitesse mais jamais ARRÊTER le flux : impossible de
  // regarder une porte précise sans attendre le tour suivant.
  var enLecture = true;
  var btnPlay = document.getElementById("pac-play");
  var btnRejouer = document.getElementById("pac-rejouer");
  function majPlay() {
    if (!btnPlay) { return; }
    btnPlay.textContent = enLecture ? "⏸ Pause" : "▶ Lecture";
    btnPlay.setAttribute("aria-pressed", enLecture ? "true" : "false");
  }
  if (btnPlay) {
    btnPlay.addEventListener("click", function () {
      enLecture = !enLecture;
      majPlay();
    });
    majPlay();
  }
  if (btnRejouer) {
    btnRejouer.addEventListener("click", function () {
      avance = 0;
      enLecture = true;
      majPlay();
    });
  }
  // La barre d'espace fait play/pause, sauf si on tape dans un champ.
  document.addEventListener("keydown", function (e) {
    if (e.code !== "Space" && e.key !== " ") { return; }
    var t = e.target || {};
    var tag = (t.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select" || t.isContentEditable) { return; }
    e.preventDefault();
    enLecture = !enLecture;
    majPlay();
  });

  // --- réglage de vitesse (02/08, Patrick : « adapte la vitesse ») ---
  var slider = document.getElementById("vitesse");
  var lbl = document.getElementById("vitesse-lbl");
  function facteur() {
    var v = slider ? parseInt(slider.value, 10) : 5;
    return v / 5; // 1 = ×0.2 (très lent) … 5 = ×1 … 10 = ×2
  }
  if (slider && lbl) {
    var majLbl = function () { lbl.textContent = "×" + facteur().toFixed(1); };
    slider.addEventListener("input", majLbl);
    majLbl();
  }

  function dessiner() {
    ctx.fillStyle = "#020817";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // murs
    ctx.fillStyle = "#0f172a";
    for (var key in murs) {
      var p = key.split(",");
      ctx.fillRect(p[0] * CELL, p[1] * CELL, CELL, CELL);
    }
    // bordure du labyrinthe
    ctx.strokeStyle = "#1e293b";
    ctx.lineWidth = 3;
    ctx.strokeRect(0, 0, canvas.width, canvas.height);

    // corridor du chemin
    ctx.strokeStyle = "#141c2e";
    ctx.lineWidth = CELL * 0.7;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    for (var pi = 0; pi < path.length; pi++) {
      var cx = path[pi].x * CELL + CELL / 2;
      var cy = path[pi].y * CELL + CELL / 2;
      if (pi === 0) ctx.moveTo(cx, cy);
      else ctx.lineTo(cx, cy);
    }
    ctx.stroke();

    // portes (pastilles)
    for (var gi = 0; gi < portes.length; gi++) {
      var idx = gateIndex[gi];
      if (idx >= path.length) continue;
      var px = path[idx].x * CELL + CELL / 2;
      var py = path[idx].y * CELL + CELL / 2;
      var grise = !mange[gi];
      ctx.beginPath();
      ctx.arc(px, py, 7, 0, Math.PI * 2);
      ctx.fillStyle = grise ? "#64748b" : "#22c55e";
      ctx.fill();
      if (grise || gi === etape - 1) {
        ctx.fillStyle = "#cbd5e1";
        ctx.font = "8px monospace";
        ctx.textAlign = "center";
        ctx.fillText((portes[gi].nom || "").slice(0, 7), px, py - 14);
      }
    }

    // le pacman (la donnée qui avance)
    var pos = Math.floor(avance);
    if (pos < path.length) {
      var cur = path[pos];
      var nxt = path[Math.min(pos + 1, path.length - 1)];
      var frac = avance - pos;
      var x = cur.x * CELL + CELL / 2 + (nxt.x - cur.x) * CELL * frac;
      var y = cur.y * CELL + CELL / 2 + (nxt.y - cur.y) * CELL * frac;
      var angle = Math.atan2((nxt.y - cur.y) * CELL, (nxt.x - cur.x) * CELL);
      for (var m in gateIndex) {
        if (!mange[m] && gateIndex[m] <= pos) mange[m] = true;
      }
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(angle);
      ctx.beginPath();
      ctx.arc(0, 0, 11, 0.2, Math.PI * 2 - 0.2);
      ctx.closePath();
      ctx.fillStyle = "#facc15";
      ctx.fill();
      ctx.restore();
    }
  }

  function animer() {
    dessiner();
    if (enLecture && avance < path.length - 1) {
      avance = Math.min(path.length - 1, avance + VITESSE * facteur());
    }
    requestAnimationFrame(animer);
  }
  animer();
})();
