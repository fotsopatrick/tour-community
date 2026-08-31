/* Carte 3D — style « simulateur de carte électronique » (02/08, Patrick).
 *
 * Refonte pro : plus de consoles flottantes ni d'effets de jeu. La tour est
 * une carte électronique (PCB) : chaque agent est un composant (puce) posé
 * sur le substrat, chaque circuit une piste de cuivre qui relie ses portes,
 * chaque message du bus une impulsion qui se propage le long des pistes.
 * Patrick est le composant central (le processeur). Une LED clignote quand
 * un agent travaille. Même donnée, même JSON, même contrôleur que le plan 2D.
 *
 * Three.js est vendored (three.min.js, aucun CDN). Sans WebGL, la page
 * affiche un repli qui renvoie vers le plan 2D.
 */
(function () {
  "use strict";

  var carte = document.getElementById("carte3d");
  if (!carte) return;
  var data;
  try { data = JSON.parse(document.getElementById("board3d-data").textContent); }
  catch (e) { return; }

  var RENDERER = null;
  try {
    RENDERER = new THREE.WebGLRenderer({
      canvas: carte, antialias: true, alpha: true,
    });
  } catch (e) { RENDERER = null; }
  if (!RENDERER) {
    document.getElementById("repli-3d").style.display = "block";
    carte.style.display = "none";
    return;
  }

  // ---- Palette PRO, fixe : une carte électronique reste une carte ---------
  // (indépendante du thème clair/sombre — comme KiCad ou un viewer de PCB)
  var PCB_BOARD = 0x0e2018;   // substrat vert sombre (FR-4)
  var PCB_EDGE  = 0x1e3a2e;
  var COPPER    = 0xb87333;   // piste de cuivre
  var PAD_GOLD  = 0xd4af37;   // pastille / sérigraphie dorée
  var SILK      = 0xe8e6d5;   // sérigraphie blanc cassé
  var CHIP      = 0x171e26;   // corps de composant
  var CHIP_EDGE = 0x37424e;
  var CPU_CHIP  = 0x8a5a1e;   // le processeur (Patrick)
  var LED_OFF   = 0x12301f;
  var LED_ON    = 0x3ddc84;

  var TYPES = {
    "standard": "#d97730", "prod": "#c0392b", "coffre": "#d4af37",
    "relecture": "#3ddc84", "revision": "#3ddc84",
    "publication": "#d97730", "detection": "#d97730",
  };
  function couleurType(t) {
    try { return new THREE.Color(TYPES[t] || "#8a94a0"); }
    catch (e) { return new THREE.Color("#8a94a0"); }
  }

  // ---- Scène ---------------------------------------------------------------
  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(40, 1, 0.1, 400);
  var orbit = { theta: -Math.PI / 4, phi: 1.12, radius: 38 };
  var RAYON = 13.5;

  scene.add(new THREE.AmbientLight(0xffffff, 0.5));
  var dir = new THREE.DirectionalLight(0xffffff, 0.85);
  dir.position.set(16, 30, 10);
  scene.add(dir);
  var dir2 = new THREE.DirectionalLight(0xffffff, 0.25);
  dir2.position.set(-18, 10, -16);
  scene.add(dir2);

  // ---- Placement : Patrick au centre, les agents en anneau -----------------
  var noms = [];
  (data.agents || []).forEach(function (a) { noms.push(a.name); });
  (data.circuits || []).forEach(function (c) {
    (c.portes || []).forEach(function (p) {
      if (noms.indexOf(p.agent) < 0) noms.push(p.agent);
    });
  });
  (data.bus || []).forEach(function (b) {
    if (noms.indexOf(b.de) < 0) noms.push(b.de);
    if (noms.indexOf(b.vers) < 0) noms.push(b.vers);
  });

  var centre = null;
  for (var i = 0; i < noms.length; i++) {
    if (/patrick/i.test(noms[i])) { centre = noms[i]; noms.splice(i, 1); break; }
  }

  // La charge = combien de pistes + de messages + d'activité. Elle ne fait
  // plus flotter les composants : elle s'affiche au survol/clic (comme une
  // mesure dans un logiciel de simulation, jamais un objet qui lévite).
  function charge(nom) {
    var c = 0;
    (data.circuits || []).forEach(function (circ) {
      (circ.portes || []).forEach(function (p) { if (p.agent === nom) c += 1; });
    });
    (data.bus || []).forEach(function (b) {
      if (b.de === nom || b.vers === nom) c += 1;
    });
    (data.activite || []).forEach(function (a) { if (a.agent === nom) c += 2; });
    return c;
  }

  var positions = {};
  if (centre) positions[centre] = new THREE.Vector3(0, 0, 0);
  var n = noms.length || 1;
  for (var q = 0; q < noms.length; q++) {
    var ang = -Math.PI / 2 + (2 * Math.PI * q) / n;
    positions[noms[q]] = new THREE.Vector3(
      RAYON * Math.cos(ang), 0, RAYON * Math.sin(ang));
  }
  var travaille = {};
  (data.activite || []).forEach(function (a) { travaille[a.agent] = a; });

  // ---- Le substrat PCB : une vraie carte, pas une grille de jeu -------------
  var board = new THREE.Mesh(
    new THREE.BoxGeometry(48, 0.5, 48),
    new THREE.MeshStandardMaterial({
      color: PCB_BOARD, roughness: 0.85, metalness: 0.1,
    }));
  board.position.y = -0.26;
  scene.add(board);
  var boardLiseres = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(48, 0.5, 48)),
    new THREE.LineBasicMaterial({ color: PCB_EDGE }));
  boardLiseres.position.y = -0.26;
  scene.add(boardLiseres);

  // Fines pistes d'habillage sur le substrat (décor : le substrat d'une carte
  // n'est jamais nu — des pistes d'acheminement le sillonnent).
  (function habillage() {
    var mat = new THREE.LineBasicMaterial({
      color: COPPER, transparent: true, opacity: 0.10 });
    var demis = [8, 14, 20];
    demis.forEach(function (r) {
      var pts = [];
      for (var a = 0; a <= 64; a++) {
        var t = a / 64 * Math.PI * 2;
        pts.push(new THREE.Vector3(r * Math.cos(t), -0.005, r * Math.sin(t)));
      }
      var ligne = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(pts), mat);
      scene.add(ligne);
    });
    var vias = new THREE.Mesh(
      new THREE.CylinderGeometry(0.10, 0.10, 0.02, 12),
      new THREE.MeshStandardMaterial({ color: PAD_GOLD, roughness: 0.4, metalness: 0.7 }));
    vias.position.y = -0.01;
    scene.add(vias);
  })();

  // ---- Les composants (les agents) : des puces posées sur la carte ----------
  var groupes = [], corpsPieces = [];

  function creerComposant(nom, pos, patron) {
    var grp = new THREE.Group();
    var W = patron ? 3.4 : 2.5, P = patron ? 2.6 : 1.7, H = 0.14;

    var corps = new THREE.Mesh(
      new THREE.BoxGeometry(W, H, P),
      new THREE.MeshStandardMaterial({
        color: patron ? CPU_CHIP : CHIP, roughness: 0.55, metalness: 0.4,
      }));
    corps.position.y = H / 2;
    grp.add(corps);

    var tranche = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(W, H, P)),
      new THREE.LineBasicMaterial({ color: patron ? PAD_GOLD : CHIP_EDGE }));
    tranche.position.y = H / 2;
    grp.add(tranche);

    // Petites pattes (comme les broches d'un boîtier CMS)
    var patteMat = new THREE.MeshStandardMaterial({
      color: PAD_GOLD, roughness: 0.35, metalness: 0.8 });
    var cotes = patron ? 12 : 8;
    for (var s = 0; s < 2; s++) {
      for (var k = 0; k < cotes; k++) {
        var patte = new THREE.Mesh(
          new THREE.BoxGeometry(0.10, 0.04, 0.42),
          patteMat);
        var x = -W / 2 + (k + 0.5) * (W / cotes);
        if (s === 0) { patte.position.set(x, -0.02, -P / 2 - 0.06); }
        else { patte.position.set(x, -0.02, P / 2 + 0.06); }
        grp.add(patte);
      }
    }

    // LED d'activité (clignote quand l'agent travaille)
    var led = new THREE.Mesh(
      new THREE.SphereGeometry(0.10, 10, 10),
      new THREE.MeshStandardMaterial({
        color: LED_OFF, emissive: LED_OFF, emissiveIntensity: 1, roughness: 0.4 }));
    led.position.set(W / 2 + 0.3, H + 0.05, 0);
    grp.add(led);

    // Sérigraphie (comme une référence de composant sur une carte)
    var lbl = etiquette(nom);
    lbl.position.set(0, H + 0.3, 0);
    grp.add(lbl);

    grp.position.copy(pos);
    scene.add(grp);
    grp.userData = {
      agent: nom, patron: !!patron, corps: corps, tranche: tranche,
      led: led, lbl: lbl, charge: charge(nom), etat: travaille[nom] || null,
    };
    corps.userData.agent = nom;
    corpsPieces.push(corps);
    groupes.push(grp);
    return grp;
  }

  function etiquette(nom) {
    var can = document.createElement("canvas");
    can.width = 512; can.height = 96;
    var ctx = can.getContext("2d");
    ctx.font = "600 38px 'Consolas','DejaVu Sans Mono',monospace";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillStyle = SILK.getStyle ? SILK.getStyle() : "#e8e6d5";
    var txt = nom.toUpperCase();
    ctx.fillText(txt, 256, 48);
    var tex = new THREE.CanvasTexture(can);
    tex.anisotropy = 4;
    var spr = new THREE.Sprite(
      new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }));
    spr.scale.set(6.5, 1.25, 1);
    return spr;
  }

  Object.keys(positions).forEach(function (nom) {
    if (nom === centre) return;
    creerComposant(nom, positions[nom], false);
  });
  if (centre) creerComposant(centre, positions[centre], true);

  // ---- Les circuits : des pistes de cuivre (plates) qui relient les portes ---
  var traces = [], enCoursTraces = [];

  // --- DÉDOUBLONNAGE (02/08, Patrick) : une seule piste par paire de
  // personnes — entre deux agents comme entre moi (le centre) et un agent.
  // Plusieurs circuits entre les mêmes gens feraient une pelote ; on garde
  // une ligne, en préférant le circuit EN COURS (celui qui joue).
  var candidats = [];
  (data.circuits || []).forEach(function (c) {
    var portes = c.portes || [];
    if (!portes.length) return;
    var agents = [];
    portes.forEach(function (p) {
      if (p.agent && agents.indexOf(p.agent) < 0) agents.push(p.agent);
    });
    if (centre && portes[portes.length - 1].agent !== centre &&
        agents.indexOf(centre) < 0) agents.push(centre);
    if (agents.length < 2) return;
    var cle = agents.slice().sort().join("|");
    var enCours = c.etat === "en_cours";
    var deja = null;
    for (var k = 0; k < candidats.length; k++) {
      if (candidats[k].cle === cle) { deja = candidats[k]; break; }
    }
    if (deja) {
      if (enCours && !deja.enCours) { deja.enCours = true; deja.c = c; }
      return;
    }
    candidats.push({ cle: cle, enCours: enCours, c: c });
  });

  candidats.forEach(function (sel) {
    var c = sel.c;
    var portes = c.portes || [];
    var pts = [];
    for (var pi = 0; pi < portes.length; pi++) {
      var dep = positions[portes[pi].agent];
      if (dep) pts.push(dep);
    }
    if (!pts.length) return;
    if (centre && portes[portes.length - 1].agent !== centre) {
      var dern = positions[portes[portes.length - 1].agent];
      if (dern) pts.push(positions[centre]);
    }
    if (pts.length < 2) return;

    var courbe = new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.5);
    var enCours = sel.enCours;
    var tube = new THREE.TubeGeometry(courbe, 48, enCours ? 0.14 : 0.09, 6, false);
    var couleur = couleurType(c.type_operation);
    var mat = new THREE.MeshStandardMaterial({
      color: couleur, roughness: 0.4, metalness: 0.6,
      transparent: true, opacity: enCours ? 0.95 : 0.35,
    });
    var mesh = new THREE.Mesh(tube, mat);
    mesh.scale.y = 0.28;      // aplati : une piste, pas un tube
    mesh.position.y = 0.02;
    scene.add(mesh);

    var agentsPiste = portes.map(function (p) { return p.agent; });
    if (centre && portes[portes.length - 1].agent !== centre) {
      agentsPiste.push(centre);
    }

    var entree = {
      curve: courbe, type: c.type_operation, etat: c.etat,
      agents: agentsPiste,
      fin: enCours
        ? Math.min(1, Math.max(0.05, (c.etape_courante || 1) / Math.max(1, pts.length - 1)))
        : 1,
      mesh: mesh,
    };
    traces.push(entree);
    if (enCours) {
      enCoursTraces.push(entree);
      var boule = new THREE.Mesh(
        new THREE.SphereGeometry(0.20, 10, 10),
        new THREE.MeshBasicMaterial({ color: couleur }));
      boule.position.copy(courbe.getPoint(0));
      scene.add(boule);
      entree.boule = boule;
    }
  });

  // ---- Le bus : des impulsions qui se propagent le long des pistes -----------
  var busPulses = [];
  (data.bus || []).forEach(function (b, idx) {
    var dep = positions[b.de], arr = positions[b.vers];
    if (!dep || !arr) return;
    var mil = new THREE.Vector3(
      (dep.x + arr.x) / 2,
      0.30 + (idx % 3) * 0.16,
      (dep.z + arr.z) / 2);
    var courbe = new THREE.CatmullRomCurve3([dep, mil, arr], false, "centripetal", 0.5);
    var ligne = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(courbe.getPoints(24)),
      new THREE.LineBasicMaterial({ color: COPPER, transparent: true, opacity: 0.25 }));
    ligne.position.y = 0.03;
    scene.add(ligne);
    var p = new THREE.Mesh(
      new THREE.SphereGeometry(0.16, 8, 8),
      new THREE.MeshBasicMaterial({ color: PAD_GOLD, transparent: true, opacity: 0 }));
    scene.add(p);
    busPulses.push({
      curve: courbe, mesh: p, decalage: idx * 0.9,
      cycle: 3.2 + (idx % 4) * 0.8,
      de: b.de, vers: b.vers, sujet: b.sujet || "",
    });
  });

  // ---- Focus + contexte : onglets, sélecteur d'agent, filtre de liens -------
  // (analyse de réseaux : on met en avant UN agent + ses liens directs, le
  // reste s'efface — la vue reste propre et professionnelle.)
  var TOUS_AGENTS = [];
  if (centre) TOUS_AGENTS.push(centre);
  TOUS_AGENTS = TOUS_AGENTS.concat(noms);

  var select = document.getElementById("focus-agent");
  if (select) {
    TOUS_AGENTS.forEach(function (nom) {
      var opt = document.createElement("option");
      opt.value = nom; opt.textContent = nom;
      select.appendChild(opt);
    });
    select.disabled = false;
  }

  var MODE = "global";      // global | focus
  var FOCUS = null;         // agent sélectionné
  var FILTRE = "tout";      // tout | circuits | bus
  // 02/08 : le Pacman est la vue par DÉFAUT — l'ancienne vue (plan
  // électronique complet) est désactivée au chargement. On peut la
  // réactiver en recliquant sur « Pacman ».
  var PACMAN = true;

  function liensDe(agent) {
    var voisins = {}, traces = [], bus = [];
    (data.circuits || []).forEach(function (c, ci) {
      (c.portes || []).forEach(function (p) {
        if (p.agent === agent) {
          (c.portes || []).forEach(function (q) {
            if (q.agent !== agent) voisins[q.agent] = true;
          });
          if (traces.indexOf(ci) < 0) traces.push(ci);
        }
      });
    });
    (data.bus || []).forEach(function (b, bi) {
      if (b.de === agent || b.vers === agent) {
        if (b.de !== agent) voisins[b.de] = true;
        if (b.vers !== agent) voisins[b.vers] = true;
        if (bus.indexOf(bi) < 0) bus.push(bi);
      }
    });
    return { voisins: Object.keys(voisins), traces: traces, bus: bus };
  }

  function dansEgo(agent, ego) {
    return agent === FOCUS || ego.voisins.indexOf(agent) >= 0;
  }

  function appliqueVue() {
    var ego = FOCUS ? liensDe(FOCUS) : null;
    var actif = MODE === "global";

    groupes.forEach(function (g) {
      var nom = g.userData.agent;
      var visible = actif || (ego && dansEgo(nom, ego));
      g.visible = visible;
      if (g.userData.corps && g.userData.corps.material) {
        var c = g.userData.patron ? CPU_CHIP : CHIP;
        if (MODE === "focus" && nom === FOCUS) c = PAD_GOLD;
        g.userData.corps.material.color.setHex(c);
      }
    });

    traces.forEach(function (e, i) {
      var visible = false;
      if (PACMAN) {
        // Mode Pacman : SEULS les circuits en cours jouent (pas de lignes de
        // gabarits), MAIS les filtres continuent de s'appliquer : « Bus »
        // cache les circuits, « Circuits » ne garde que les pistes en cours.
        visible = e.etat === "en_cours" && FILTRE !== "bus";
      } else if (actif) {
        visible = FILTRE !== "bus";
      } else if (ego && FILTRE !== "bus" && ego.traces.indexOf(i) >= 0) {
        var ok = true;
        for (var a = 0; a < e.agents.length; a++) {
          if (!dansEgo(e.agents[a], ego)) { ok = false; break; }
        }
        visible = ok;
      }
      e.mesh.visible = visible;
      if (e.boule) e.boule.visible = visible;
    });

    busPulses.forEach(function (b, i) {
      var visible = false;
      if (PACMAN) {
        // En mode Pacman le bus reste piloté par le filtre choisi.
        visible = FILTRE === "bus" || FILTRE === "tout";
      } else if (actif) { visible = FILTRE !== "circuits"; }
      else if (ego && FILTRE !== "circuits" && ego.bus.indexOf(i) >= 0) {
        visible = dansEgo(b.de, ego) && dansEgo(b.vers, ego);
      }
      b.mesh.visible = visible;
    });

    var liensEl = document.getElementById("liens3d");
    if (liensEl) {
      if (MODE === "focus" && ego) {
        var texte = "<b>" + FOCUS + "</b> — " + ego.voisins.length +
          " lien(s) direct(s) : " + (ego.voisins.join(", ") || "aucun");
        if (FILTRE === "circuits") texte += " (circuits)";
        else if (FILTRE === "bus") texte += " (bus)";
        liensEl.innerHTML = texte;
      } else {
        liensEl.innerHTML = "";
      }
    }
  }

  function setMode(mode) {
    MODE = mode;
    document.querySelectorAll(".carte3d-tab").forEach(function (b) {
      b.classList.toggle("actif", b.getAttribute("data-mode") === mode);
    });
    if (MODE === "focus" && !FOCUS && TOUS_AGENTS.length) FOCUS = TOUS_AGENTS[0];
    if (select) select.value = FOCUS || "";
    appliqueVue();
  }
  function setFiltre(f) {
    FILTRE = f;
    document.querySelectorAll(".carte3d-f").forEach(function (b) {
      b.classList.toggle("actif", b.getAttribute("data-filtre") === f);
    });
    appliqueVue();
  }

  document.querySelectorAll(".carte3d-tab").forEach(function (b) {
    b.addEventListener("click", function () {
      setMode(b.getAttribute("data-mode"));
    });
  });
  document.querySelectorAll(".carte3d-f").forEach(function (b) {
    b.addEventListener("click", function () {
      setFiltre(b.getAttribute("data-filtre"));
    });
  });
  var btnPacman = document.getElementById("carte3d-pacman");
  if (btnPacman) {
    if (PACMAN) btnPacman.classList.add("actif");
    btnPacman.addEventListener("click", function () {
      PACMAN = !PACMAN;
      btnPacman.classList.toggle("actif", PACMAN);
      appliqueVue();
    });
  }
  if (select) {
    select.addEventListener("change", function () {
      FOCUS = select.value;
      appliqueVue();
    });
  }

  // L'ancienne vue est désactivée au chargement : on applique la vue (Pacman
  // par défaut) avant la première image, sinon le plan complet resterait
  // visible jusqu'au premier clic.
  appliqueVue();

  // ---- Interaction : orbite, zoom, clic ---------------------------------------
  var derniereX = 0, derniereY = 0;

  carte.addEventListener("pointerdown", function (ev) {
    derniereX = ev.clientX; derniereY = ev.clientY;
    carte.setPointerCapture(ev.pointerId);
  });
  carte.addEventListener("pointermove", function (ev) {
    if (ev.buttons & 1) {
      var dx = ev.clientX - derniereX, dy = ev.clientY - derniereY;
      derniereX = ev.clientX; derniereY = ev.clientY;
      orbit.theta -= dx * 0.0055;
      orbit.phi -= dy * 0.0055;
      orbit.phi = Math.max(0.25, Math.min(Math.PI - 0.25, orbit.phi));
    }
  });
  carte.addEventListener("pointerup", function () { derniereX = 0; derniereY = 0; });
  carte.addEventListener("wheel", function (ev) {
    ev.preventDefault();
    orbit.radius *= 1 + ev.deltaY * 0.0011;
    orbit.radius = Math.max(14, Math.min(95, orbit.radius));
  }, { passive: false });

  var ray = new THREE.Raycaster();
  var souris = new THREE.Vector2();
  var infoEl = document.getElementById("sel3d");

  function surligner(grp) {
    groupes.forEach(function (g) {
      var e = g.userData.corps;
      if (e && e.material) {
        e.material.color.setHex((g === grp)
          ? (g.userData.patron ? PAD_GOLD : 0x2a3540)
          : (g.userData.patron ? CPU_CHIP : CHIP));
      }
    });
  }

  carte.addEventListener("click", function (ev) {
    var r = carte.getBoundingClientRect();
    souris.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    souris.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
    ray.setFromCamera(souris, camera);
    var touches = ray.intersectObjects(corpsPieces);
    if (touches.length) {
      var agent = touches[0].object.userData.agent;
      var grp = null;
      for (var g = 0; g < groupes.length; g++) {
        if (groupes[g].userData.agent === agent) { grp = groupes[g]; break; }
      }
      var msg = "Composant : " + agent +
        " — charge " + (grp ? grp.userData.charge : "?");
      if (grp && grp.userData.etat) {
        msg += " — travaille sur : " + grp.userData.etat.nom;
      }
      if (infoEl) infoEl.textContent = msg;
      surligner(grp);
    }
  });

  // ---- Animation ----------------------------------------------------------------
  var horloge = new THREE.Clock();

  function animer() {
    var t = horloge.elapsedTime;

    camera.position.setFromSpherical(
      new THREE.Spherical(orbit.radius, orbit.phi, orbit.theta));
    camera.lookAt(0, 0.2, 0);

    // Pulsation le long des circuits en cours (le signal avance porte à porte)
    enCoursTraces.forEach(function (e, ei) {
      if (!e.boule) return;
      var ph = (t * 0.45 + ei * 0.13) % 1;
      var p = e.curve.getPointAt(Math.min(ph * 1.12, e.fin));
      e.boule.position.copy(p);
      e.boule.position.y = 0.10;
      if (PACMAN) {
        // Mode Pacman : le signal devient une boule jaune bien visible
        e.boule.material.color.setHex(0xfacc15);
        e.boule.material.opacity = 1;
        e.boule.scale.setScalar(1.5);
      } else {
        e.boule.material.opacity = 0.85 + 0.15 * Math.sin(ph * Math.PI * 2);
        e.boule.scale.setScalar(1);
      }
    });

    // Impulsions du bus
    busPulses.forEach(function (b) {
      var ph = ((t + b.decalage) / b.cycle) % 1;
      if (ph <= 0.97) {
        var p = b.curve.getPointAt(ph);
        b.mesh.position.copy(p);
        b.mesh.material.opacity = Math.sin(Math.min(1, ph * 1.05) * Math.PI) * 0.95;
        b.mesh.scale.setScalar(1 + Math.sin(ph * Math.PI * 2) * 0.25);
      } else {
        b.mesh.material.opacity = 0;
      }
    });

    // LED : l'agent qui travaille clignote, les autres restent éteintes
    groupes.forEach(function (g) {
      var led = g.userData.led, etat = g.userData.etat;
      if (!led) return;
      if (etat) {
        var phase = 0.5 + 0.5 * Math.sin(t * 3.2 + (g.userData.agent.length || 0));
        led.material.color.setHex(LED_ON);
        led.material.emissive.setHex(LED_ON);
        led.material.emissiveIntensity = 0.4 + phase * 1.6;
      } else {
        led.material.color.setHex(LED_OFF);
        led.material.emissive.setHex(LED_OFF);
        led.material.emissiveIntensity = 0.4;
      }
    });

    RENDERER.render(scene, camera);
    requestAnimationFrame(animer);
  }

  // ---- Démarrage / redimensionnement --------------------------------------------
  function dimensionner() {
    if (!carte.clientWidth) return;
    RENDERER.setSize(carte.clientWidth, carte.clientHeight, false);
    camera.aspect = carte.clientWidth / carte.clientHeight;
    camera.updateProjectionMatrix();
  }

  // La carte garde sa palette (une carte reste une carte) ; on laisse le fond
  // transparent pour se fondre dans la page.
  function rafraichirTheme() {
    scene.background = null;
  }

  dimensionner();
  rafraichirTheme();
  window.addEventListener("resize", dimensionner);
  requestAnimationFrame(animer);

  // ---- Légende --------------------------------------------------------------------
  var libelles = { standard: "standard", prod: "mise en production",
    coffre: "Coffre", relecture: "relecture", revision: "révision",
    publication: "publication", detection: "détection" };
  var leg = document.getElementById("legende3d");
  if (leg) {
    Object.keys(libelles).forEach(function (t) {
      var span = document.createElement("span");
      span.innerHTML = '<span class="sw" style="background:' +
        couleurType(t).getStyle() + '"></span>' + libelles[t];
      leg.appendChild(span);
    });
    var s1 = document.createElement("span");
    s1.innerHTML = '<span class="sw" style="background:#' +
      PAD_GOLD.toString(16) + '"></span>message du bus';
    leg.appendChild(s1);
    var s2 = document.createElement("span");
    s2.innerHTML = '<span class="sw" style="background:#' +
      LED_ON.toString(16) + '"></span>agent qui travaille';
    leg.appendChild(s2);
    var s3 = document.createElement("span");
    s3.innerHTML = '<span class="sw dash" style="color:#' +
      COPPER.toString(16) + '"></span>gabarit (translucide)';
    leg.appendChild(s3);
  }

  window.TourCarte3D = {
    rafraichirTheme: function () { rafraichirTheme(); },
  };
})();
