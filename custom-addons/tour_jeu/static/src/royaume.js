/* Le Royaume — un jeu 2D façon Pokémon (Génération 1/2).
 * Petit moteur maison, zéro dépendance : canvas + tuiles + déplacement en grille.
 * Les rencontres dans les hautes herbes sont du décor du jeu.
 */
(function () {
  "use strict";

  var T = 30;                 // taille d'une tuile (px)
  var COL = 40, LIG = 24;     // dimensions de la carte

  // Légende : G=herbe H=hautes herbes P=chemin W=eau T=arbre B=bâtiment
  //           F=clôture D=porte S=pancarte M=montagne
  var CARTE = [
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",
    "TTGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGTT",
    "TTGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGTT",
    "TTGGHHHHHHHGGGGGGGGGGGGGGGGGHHHHHHHGGGGTT",
    "TTGGHHHHHHHGGGGGPPPPPPPPGGGGHHHHHHHGGGGTT",
    "TTGGGGGGGGGGGGGPPTTTTTTPPGGGGGGGGGGGGGGTT",
    "TTGGGGGGGGGGGGGPPTSSSSTTPPGGGGGGGGGGGGGTT",
    "TTGGGGGGGGGGGGGPPTTTTTTPPPGGGGGGGGGGGGGTT",
    "TTGGHHHHHGGGGGGPPPPPPPPPPGGGGGGHHHHHGGGTT",
    "TTGGHHHHHGGGGGPPPPPPPPPPPPGGGGGGHHHHHGGGTT",
    "TTGGGGGGGGGGGPPPPPPPPPPPPPPGGGGGGGGGGGGGTT",
    "TTGGGGGGGGGGGPPPPBBBBBBBBPPGGGGGGGGGGGGGTT",
    "TTGGGGGGGGGGGPPPPBBBBBBBBPPGGGGGGGGGGGGGTT",
    "TTGGGGGGGGGGGPPPPBPDDPPBBPPGGGGGGGGGGGGGTT",
    "TTGGGGGGGGGGGPPPPBBBBBBBBPPGGGGGGGGGGGGGTT",
    "TTGGGGGGGGGGGPPPPBBBBBBBBPPGGGGGGGGGGGGGTT",
    "TTGGGGGGGGGGGPPPPPPPPPPPPPPGGGGGGGGGGGGGTT",
    "TTGGHHHHHHHGGGGGPPPPPPPPGGGGGGGGHHHHHHHGTT",
    "TTGGHHHHHHHGGGGGGGGGGGGGGGGGGGGGHHHHHHHGTT",
    "TTGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGTT",
    "TTGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGTT",
    "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT"
  ];
  var SOLIDE = { T: 1, W: 1, B: 1, F: 1, M: 1 };
  var ENCONTRE = { H: 1 };

  var ETAGES = ["Bivouac", "Abri", "Tourelle", "Forteresse", "Citadelle", "Titan"];
  var COULEUR_ETAGE = ["#a16207", "#b45309", "#2563eb", "#7c3aed", "#0ea5e9", "#f59e0b"];

  // ------------------------------------------------------------------ état
  var canvas, ctx, jeuDiv, dialog, hud;
  var MOI = null;          // {niveau, xp, etage, nom, ...} ou null (visiteur)
  var TOURS = [];          // [{nom, niveau, xp, etage, domaine_nom, nb_badges}]
  var joueur = {
    x: 20, y: 12,          // position en tuiles
    px: 20, py: 12,        // position animée (px)
    face: "bas", avance: false, deplacement: 0
  };
  var npc = [];            // personnages des autres tours
  var touche = {};         // clés enfoncées
  var enDialogue = false;
  var enRencontre = false;
  var msg = "";
  var images = {};         // sprites procéduraux en cache

  // ------------------------------------------------------------------ outils
  function rpc(url, params) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: params || {} })
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.error) throw new Error(d.error.message);
      return d.result;
    });
  }

  function solide(x, y) {
    if (x < 0 || y < 0 || x >= COL || y >= LIG) return true;
    return !!SOLIDE[CARTE[y][x]];
  }

  function etageDe(niveau) {
    var i = 0;
    for (var k = 0; k < ETAGES.length; k++) {
      if (niveau >= [0, 3, 6, 10, 15, 20][k]) i = k;
    }
    return i;
  }

  // ------------------------------------------------------------------ sprites
  function tuile(c, x, y, t) {
    var px = x * t, py = y * t;
    if (c === "G") {
      ctx.fillStyle = "#3e8e41"; ctx.fillRect(px, py, t, t);
      ctx.fillStyle = "#4ca64f";
      for (var i = 0; i < 4; i++) ctx.fillRect(px + (i * 7) % t, py + (i * 11) % t, 2, 2);
    } else if (c === "H") {
      ctx.fillStyle = "#2d6a30"; ctx.fillRect(px, py, t, t);
      ctx.fillStyle = "#1e4d22";
      for (var j = 0; j < 5; j++) ctx.fillRect(px + (j * 6) % t, py + (j * 9) % t, 3, 5);
      ctx.fillStyle = "#3f8f43";
      for (var k = 0; k < 4; k++) ctx.fillRect(px + 3 + (k * 8) % t, py + 2 + (k * 7) % t, 2, 4);
    } else if (c === "P") {
      ctx.fillStyle = "#c9a15f"; ctx.fillRect(px, py, t, t);
      ctx.fillStyle = "#b89152";
      ctx.fillRect(px + 2, py + 2, t - 4, t - 4);
      ctx.fillStyle = "#d3ac68";
      ctx.fillRect(px + 4, py + 4, t - 8, t - 8);
    } else if (c === "W") {
      var bleu = (Math.floor(Date.now() / 400) % 2) ? "#2f6fb0" : "#337cc2";
      ctx.fillStyle = bleu; ctx.fillRect(px, py, t, t);
      ctx.fillStyle = "#7fc4f0";
      ctx.fillRect(px + 4, py + 8 + (Date.now() / 300 % 6), 12, 2);
    } else if (c === "T") {
      ctx.fillStyle = "#1e4d22"; ctx.fillRect(px + 3, py + 3, t - 6, t - 6);
      ctx.fillStyle = "#2f6b34";
      ctx.fillRect(px, py + 6, t, t - 10);
      ctx.fillStyle = "#5d3a1a";
      ctx.fillRect(px + 11, py + 18, 8, 12);
    } else if (c === "B") {
      ctx.fillStyle = "#7b8794"; ctx.fillRect(px, py + 10, t, t - 10);
      ctx.fillStyle = "#94a3b8"; ctx.fillRect(px + 2, py + 12, t - 4, 4);
      ctx.fillStyle = "#c0523f";
      ctx.fillRect(px, py + 8, t, 4);
      ctx.fillRect(px - 3, py + 8, t + 6, 3);
    } else if (c === "F") {
      ctx.fillStyle = "#8a6d3b"; ctx.fillRect(px, py, t, t);
      ctx.fillStyle = "#a88950";
      ctx.fillRect(px + 3, py, 4, t);
      ctx.fillRect(px + 14, py, 4, t);
      ctx.fillRect(px + 24, py, 4, t);
    } else if (c === "S") {
      ctx.fillStyle = "#6b4d2a"; ctx.fillRect(px, py + 8, t, t - 8);
      ctx.fillStyle = "#a88950"; ctx.fillRect(px, py + 2, t, 6);
      ctx.fillStyle = "#f5f0e6";
      ctx.fillRect(px + 2, py + 12, t - 4, t - 12);
    } else if (c === "M") {
      ctx.fillStyle = "#4a5568"; ctx.fillRect(px, py + 10, t, t - 10);
      ctx.fillStyle = "#f0f4ff"; ctx.fillRect(px, py + 8, t, 4);
    }
  }

  function personnage(px, py, face, couleur, avance) {
    var b = Math.floor(px), h = Math.floor(py);
    var jambes = (avance && Math.floor(Date.now() / 200) % 2) ? 2 : 0;
    // jambes
    ctx.fillStyle = "#22293d";
    ctx.fillRect(b + 8, h + 20 - jambes, 4, 5);
    ctx.fillRect(b + 18, h + 20 - jambes, 4, 5);
    // corps
    ctx.fillStyle = couleur;
    ctx.fillRect(b + 6, h + 12, 18, 9);
    ctx.fillStyle = "#1c2438";
    ctx.fillRect(b + 6, h + 12, 18, 3);
    // tête
    ctx.fillStyle = "#f2c79b";
    ctx.fillRect(b + 8, h + 4, 14, 9);
    // cheveux/casquette
    ctx.fillStyle = couleur;
    ctx.fillRect(b + 8, h + 2, 14, 4);
    ctx.fillRect(b + (face === "droite" ? 14 : face === "gauche" ? 4 : 8), h + 2, 10, 3);
    // yeux selon la direction
    ctx.fillStyle = "#141a2b";
    if (face === "gauche") { ctx.fillRect(b + 8, h + 8, 3, 3); }
    else if (face === "droite") { ctx.fillRect(b + 20, h + 8, 3, 3); }
    else { ctx.fillRect(b + 9, h + 8, 3, 3); ctx.fillRect(b + 19, h + 8, 3, 3); }
  }

  function tourSprite(px, py, etage) {
    var b = Math.floor(px), h = Math.floor(py);
    var c = COULEUR_ETAGE[etage] || "#3b82f6";
    var haut = 14 + etage * 5;         // la tour grandit avec l'étage
    var large = 8 + etage * 2;
    ctx.fillStyle = c;
    ctx.fillRect(b + 15 - large / 2, h + 30 - haut, large, haut);
    ctx.fillStyle = "#0b1220";
    ctx.fillRect(b + 15 - large / 2, h + 30 - haut + 2, large, 3);
    ctx.fillRect(b + 15 - large / 2, h + 30 - 6, large, 3);
    if (etage >= 3) {
      ctx.fillStyle = "#f59e0b";
      ctx.fillRect(b + 15 - 3, h + 30 - haut - 4, 6, 4);
    }
  }

  // ------------------------------------------------------------------ carte
  function dessiner() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (var y = 0; y < LIG; y++) {
      for (var x = 0; x < COL; x++) {
        tuile(CARTE[y][x], x, y, T);
      }
    }
    // les tours des autres (NPC)
    for (var i = 0; i < npc.length; i++) {
      var n = npc[i];
      tourSprite(n.x * T, n.y * T, n.etage);
      personnage(n.x * T + 7, n.y * T + 4, n.face, n.couleur, false);
    }
    // le joueur
    personnage(joueur.px * T + 7, joueur.py * T + 4, joueur.face, joueur.couleur, joueur.avance);
    tourSprite(joueur.px * T, joueur.py * T - 8, joueur.etage);
  }

  function boucle() {
    if (!enDialogue && !enRencontre) {
      var vx = 0, vy = 0;
      if (touche.ArrowLeft || touche.q) vx = -1;
      if (touche.ArrowRight || touche.d) vx = 1;
      if (touche.ArrowUp || touche.z) vy = -1;
      if (touche.ArrowDown || touche.s) vy = 1;
      if (vx !== 0 && vy !== 0) { vx = 0; }
      if (vx || vy) {
        joueur.face = vx < 0 ? "gauche" : vx > 0 ? "droite" : vy < 0 ? "haut" : "bas";
        var nx = joueur.x + vx, ny = joueur.y + vy;
        if (!solide(nx, ny)) {
          joueur.x = nx; joueur.y = ny;
          joueur.avance = true;
          if (ENCONTRE[CARTE[ny][nx]] && Math.random() < 0.18) {
            lancerRencontre();
          }
        } else {
          joueur.avance = false;
        }
      } else {
        joueur.avance = false;
      }
      joueur.px += (joueur.x - joueur.px) * 0.35;
      joueur.py += (joueur.y - joueur.py) * 0.35;
    }
    dessiner();
    requestAnimationFrame(boucle);
  }

  // ------------------------------------------------------------------ dialog
  function ouvrirDialog(titre, corps, boutons) {
    enDialogue = true;
    dialog.innerHTML =
      '<div class="boite"><div class="btitre"></div><div class="btexte"></div>' +
      '<div class="bboutons"></div></div>';
    dialog.querySelector(".btitre").textContent = titre;
    dialog.querySelector(".btexte").innerHTML = corps;
    var bb = dialog.querySelector(".bboutons");
    (boutons || [{ label: "Fermer" }]).forEach(function (b) {
      var btn = document.createElement("button");
      btn.textContent = b.label;
      btn.onclick = function () { dialog.innerHTML = ""; enDialogue = false; if (b.onOk) b.onOk(); };
      bb.appendChild(btn);
    });
  }

  function procheNpc() {
    for (var i = 0; i < npc.length; i++) {
      var dx = Math.abs(npc[i].x - joueur.x);
      var dy = Math.abs(npc[i].y - joueur.y);
      if (dx + dy === 1) return npc[i];
    }
    return null;
  }

  function parler() {
    var n = procheNpc();
    if (n) {
      ouvrirDialog("🏰 " + n.nom, [
        "« Bonjour, gardien ! Ma tour est <b>" + n.etage + "</b> (niveau " + n.niveau + ").",
        "<b>" + n.xp + "</b> XP · <b>" + n.nb_badges + "</b> palier(s).",
        n.vocation ? "Ma vocation : " + n.vocation + "." : ""
      ].join("<br>"));
      return;
    }
    // pancarte au centre
    var c = CARTE[joueur.y][joueur.x];
    if (c === "S" || (c === "P" && joueur.x === 20 && joueur.y === 7)) {
      ouvrirDialog("📜 La pancarte", "Bienvenue dans le Royaume. Ta tour évolue au fil du temps — explore le royaume et rencontre les autres tours.");
      return;
    }
    if (c === "D") {
      ouvrirDialog("🏛️ Ta tour", "C'est ta tour. Elle est au stade <b>" + (ETAGES[joueur.etage] || "Bivouac") + "</b>. Chaque haut fait la fera grandir.");
    }
  }

  function lancerRencontre() {
    enRencontre = true;
    var bestiaire = ["🧿", "🗿", "🐲", "🦉", "🌪️", "🌿", "⚡", "🔮"];
    var best = bestiaire[Math.floor(Math.random() * bestiaire.length)];
    ouvrirDialog("⚔️ Une rencontre !", "Un esprit sauvage " + best + " apparaît dans les hautes herbes !<br><br><i>Il apparaît dans les hautes herbes — et disparaît aussitôt.</i>", [{
      label: "S'éloigner",
      onOk: function () { enRencontre = false; }
    }]);
  }

  // ------------------------------------------------------------------ entrée
  function demarrer(moi, tours) {
    if (moi && moi.niveau) {
      MOI = moi;
      joueur.etage = etageDe(moi.niveau);
      joueur.couleur = COULEUR_ETAGE[joueur.etage] || "#3b82f6";
      hud.style.display = "block";
      hud.querySelector(".h-nom").textContent = moi.nom || "Toi";
      hud.querySelector(".h-niveau").textContent = "Niveau " + moi.niveau;
      hud.querySelector(".h-etage").textContent = ETAGES[joueur.etage] || "";
      hud.querySelector(".h-xp").textContent = moi.xp + " XP";
    } else {
      joueur.etage = 0;
      joueur.couleur = "#3b82f6";
      hud.style.display = "block";
      hud.querySelector(".h-nom").textContent = "Visiteur";
      hud.querySelector(".h-niveau").textContent = "—";
      hud.querySelector(".h-etage").textContent = "Explore le Royaume";
      hud.querySelector(".h-xp").textContent = "";
    }
    // place les NPC des autres tours autour de la carte
    var places = [[28, 4], [32, 18], [6, 4], [10, 19], [22, 3], [33, 8], [4, 12]];
    var couleurs = ["#e11d48", "#7c3aed", "#0ea5e9", "#16a34a", "#ea580c", "#db2777", "#0284c7"];
    npc = [];
    for (var i = 0; i < tours.length && i < places.length; i++) {
      var t = tours[i];
      npc.push({
        nom: t.nom,
        niveau: t.niveau,
        xp: t.xp,
        nb_badges: t.nb_badges,
        etage: etageDe(t.niveau),
        vocation: t.domaine_nom || "",
        couleur: couleurs[i],
        face: "bas",
        x: places[i][0], y: places[i][1]
      });
    }
    requestAnimationFrame(boucle);
  }

  function initialiser() {
    canvas = document.getElementById("royaume");
    jeuDiv = document.getElementById("jeu");
    dialog = document.getElementById("dialog");
    hud = document.getElementById("hud");
    ctx = canvas.getContext("2d");
    canvas.width = COL * T; canvas.height = LIG * T;
    canvas.style.maxWidth = "100%";

    document.addEventListener("keydown", function (e) {
      touche[e.key] = true;
      if (e.key === "Enter" || e.key === "e" || e.key === "E" || e.key === " ") {
        if (!enDialogue && !enRencontre) parler();
      }
      if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", " "].indexOf(e.key) !== -1) e.preventDefault();
    });
    document.addEventListener("keyup", function (e) { touche[e.key] = false; });

    // barre tactile (mobile)
    document.querySelectorAll("#jeu .pad button").forEach(function (b) {
      var k = b.getAttribute("data-k");
      b.addEventListener("touchstart", function (e) { e.preventDefault(); touche[k] = true; });
      b.addEventListener("touchend", function (e) { e.preventDefault(); touche[k] = false; });
    });
    var aBtn = document.getElementById("btn-ok");
    if (aBtn) aBtn.addEventListener("click", function () { if (!enDialogue && !enRencontre) parler(); });

    rpc("/tour/jeu-de-la-tour-public/api/royaume", {}).then(function (d) {
      demarrer(d.moi, d.tours || []);
    }).catch(function (e) {
      ouvrirDialog("⚠️ Hors ligne", "Impossible de lire le royaume : " + e.message);
      demarrer(null, []);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialiser);
  } else {
    initialiser();
  }
})();
