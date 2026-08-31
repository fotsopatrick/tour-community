(function () {
  var cont = document.getElementById('bureau');
  if (!cont) return;
  var cv = document.createElement('canvas');
  cv.width = 800;
  cv.height = 400;
  cv.style.width = '100%';
  cv.style.height = 'auto';
  cv.style.display = 'block';
  cv.style.cursor = 'pointer';
  cont.appendChild(cv);
  var ctx = cv.getContext('2d');
  var W = cv.width, H = cv.height;
  var TABLE = { x: W / 2 - 225, y: H / 2 - 85, w: 450, h: 170 };
  var TABLEAU = { x: 118, y: 76 };
  var NOMS = ['Raphaël','Chloe','Clark','Lois','Victor','Braignak','Emil','Pete','Martha','Oliver','Jor-El','Lex','Mirline','Sentinelle','Releve','Cœur','NouvelArticle'];
  var COULEURS = ['#4f8ef7','#e868a8','#3fa63f','#c9a227','#e06040','#8a5ae0','#2bb8c9','#d8732a','#7a9a4a','#b04090','#5a6ae0','#c04040','#2fae5a','#d0b040','#4090b0','#b060c0','#60b060'];
  var PRESENTATIONS = {
    'Raphaël': 'Le chef — coordonne les missions.',
    'Chloe': 'La voix — discute et oriente.',
    'Clark': 'Le bâtisseur — code les modules.',
    'Lois': 'La relectrice — vérifie avant de publier.',
    'Victor': 'La sécurité — garde les portes.',
    'Braignak': 'L’observateur — lit, étudie, propose.',
    'Emil': 'Membre de l’équipe — les circuits.',
    'Pete': 'Membre de l’équipe — les circuits.',
    'Martha': 'La réglementaire — les textes.',
    'Oliver': 'Membre de l’équipe.',
    'Jor-El': 'L’apprentissage — documente.',
    'Lex': 'Le garde-fou — surveille les boucles.',
    'Mirline': 'Le bras — exécute les chantiers.',
    'Sentinelle': 'Veille sur les sites.',
    'Releve': 'Relève les compteurs.',
    'Cœur': 'Le pouls de la tour.',
    'NouvelArticle': 'Surveille les publications.'
  };

  var CHAISES = [];
  var i;
  for (i = 0; i < 6; i++) CHAISES.push({ x: TABLE.x + 48 + i * 66, y: TABLE.y - 36, ori: 0 });
  for (i = 0; i < 6; i++) CHAISES.push({ x: TABLE.x + 48 + i * 66, y: TABLE.y + TABLE.h + 36, ori: 2 });
  CHAISES.push({ x: TABLE.x - 36, y: TABLE.y + 46, ori: 3 });
  CHAISES.push({ x: TABLE.x + TABLE.w + 36, y: TABLE.y + 46, ori: 1 });
  CHAISES.push({ x: TABLE.x + TABLE.w + 36, y: TABLE.y + 112, ori: 1 });
  CHAISES.push({ x: TABLE.x - 36, y: TABLE.y + 112, ori: 3 });
  CHAISES.push({ x: TABLE.x + TABLE.w + 36, y: TABLE.y + 24, ori: 1 });

  var agents = [];
  for (i = 0; i < NOMS.length; i++) {
    var c = CHAISES[i % CHAISES.length];
    agents.push({ nom: NOMS[i], couleur: COULEURS[i], cx: c.x, cy: c.y, x: c.x, y: c.y, etat: 'assis', pause: 0 });
  }
  var agentClic = null;

  // --- LE VISITEUR (avatar deplagable, style Pokemon) ---
  var joueur = { x: W - 70, y: H - 60, v: 2.4 };
  var touches = {};
  window.addEventListener('keydown', function (e) {
    var tag = (document.activeElement && document.activeElement.tagName) || '';
    if (tag === 'INPUT' || tag === 'TEXTAREA') return;
    var k = (e.key || '').toLowerCase();
    if (['arrowup','arrowdown','arrowleft','arrowright','z','q','s','d','w','a'].indexOf(k) >= 0) e.preventDefault();
    touches[e.key] = true;
  });
  window.addEventListener('keyup', function (e) { touches[e.key] = false; });

  // --- LE PETIT BRAIGNAK, personnage cliquable ---
  var braignak = { x: 205, y: 96 };

  function bougeJoueur() {
    var dx = 0, dy = 0;
    if (touches['ArrowLeft'] || touches['q'] || touches['Q']) dx = -1;
    if (touches['ArrowRight'] || touches['d'] || touches['D']) dx = 1;
    if (touches['ArrowUp'] || touches['z'] || touches['Z']) dy = -1;
    if (touches['ArrowDown'] || touches['s'] || touches['S']) dy = 1;
    if (!dx && !dy) return;
    var nx = joueur.x + dx * joueur.v;
    var ny = joueur.y + dy * joueur.v;
    if (!dansTable(nx, joueur.y) && nx > 14 && nx < W - 14) joueur.x = nx;
    if (!dansTable(joueur.x, ny) && ny > 14 && ny < H - 14) joueur.y = ny;
  }

  function sol() {
    ctx.fillStyle = '#cfc6b4';
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = '#b0a68f';
    ctx.lineWidth = 1;
    for (var y = 0; y < H; y += 28) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(W, y);
      ctx.stroke();
    }
    ctx.fillStyle = '#8a7f6a';
    ctx.fillRect(0, 0, W, 10);
    ctx.fillRect(0, H - 10, W, 10);
    ctx.fillRect(0, 0, 10, H);
    ctx.fillRect(W - 10, 0, 10, H);
  }

  function tableauBlanc() {
    var x = 24, y = 58, w = 66, h = 96;
    ctx.fillStyle = '#8a7f6a';
    ctx.fillRect(x - 3, y + h, w + 6, 6);
    ctx.fillStyle = '#eef2f4';
    ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = '#c8ccd0';
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);
    ctx.strokeStyle = '#e04040';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x + 12, y + 26);
    ctx.lineTo(x + 42, y + 19);
    ctx.stroke();
    ctx.strokeStyle = '#3b82f6';
    ctx.beginPath();
    ctx.moveTo(x + 12, y + 40);
    ctx.lineTo(x + 52, y + 33);
    ctx.stroke();
    ctx.strokeStyle = '#2fae5a';
    ctx.beginPath();
    ctx.moveTo(x + 12, y + 54);
    ctx.lineTo(x + 36, y + 47);
    ctx.stroke();
    ctx.fillStyle = '#cbd5e1';
    ctx.font = '9px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('IDÉES', x + w / 2, y - 8);
  }

  function table() {
    ctx.fillStyle = 'rgba(0,0,0,.14)';
    ctx.fillRect(TABLE.x + 6, TABLE.y + 6, TABLE.w, TABLE.h);
    var g = ctx.createLinearGradient(TABLE.x, TABLE.y, TABLE.x, TABLE.y + TABLE.h);
    g.addColorStop(0, '#c39a68');
    g.addColorStop(1, '#9a6f42');
    ctx.fillStyle = g;
    ctx.fillRect(TABLE.x, TABLE.y, TABLE.w, TABLE.h);
    ctx.strokeStyle = '#7a5430';
    ctx.lineWidth = 3;
    ctx.strokeRect(TABLE.x, TABLE.y, TABLE.w, TABLE.h);
    ctx.strokeStyle = 'rgba(255,255,255,.25)';
    ctx.lineWidth = 1;
    ctx.strokeRect(TABLE.x + 5, TABLE.y + 5, TABLE.w - 10, TABLE.h - 10);
    var cx = TABLE.x + TABLE.w / 2, cy = TABLE.y + TABLE.h / 2;
    ctx.fillStyle = '#2a2a38';
    ctx.fillRect(cx - 45, cy - 22, 90, 62);
    ctx.fillStyle = '#e8e8f0';
    ctx.fillRect(cx - 41, cy - 18, 82, 54);
    ctx.fillStyle = '#c0d0e0';
    ctx.fillRect(cx - 20, cy - 12, 40, 26);
    ctx.fillStyle = '#f8f4e8';
    ctx.fillRect(cx + 48, cy - 16, 42, 30);
    ctx.strokeStyle = '#b0a090';
    ctx.lineWidth = 1;
    ctx.strokeRect(cx + 48, cy - 16, 42, 30);
    ctx.fillStyle = '#e04040';
    ctx.fillRect(cx + 56, cy - 10, 5, 16);
    ctx.fillStyle = '#3b82f6';
    ctx.fillRect(cx + 66, cy - 10, 5, 16);
    ctx.fillStyle = '#2fae5a';
    ctx.fillRect(cx + 76, cy - 10, 5, 16);
    ctx.fillStyle = '#5a4428';
    ctx.font = '12px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('TABLE DE RÉUNION', cx, cy + 44);
  }

  function dansTable(px, py) {
    return px > TABLE.x && px < TABLE.x + TABLE.w && py > TABLE.y && py < TABLE.y + TABLE.h;
  }

  function chaise(x, y, ori) {
    var dx = 0, dy = 0;
    if (ori === 0) dy = -1;
    else if (ori === 2) dy = 1;
    else if (ori === 3) dx = -1;
    else dx = 1;
    ctx.fillStyle = '#20202a';
    ctx.fillRect(x + dx * 7 - 8, y + dy * 7 - 8, 16, 16);
    ctx.fillStyle = '#14141c';
    if (ori === 0) ctx.fillRect(x - 8, y - 16, 16, 6);
    else if (ori === 2) ctx.fillRect(x - 8, y + 10, 16, 6);
    else if (ori === 3) ctx.fillRect(x - 16, y - 8, 6, 16);
    else ctx.fillRect(x + 10, y - 8, 6, 16);
  }

  function bonhomme(px, py, couleur) {
    var o = ctx.createRadialGradient(px, py + 6, 2, px, py + 6, 10);
    o.addColorStop(0, 'rgba(0,0,0,.28)');
    o.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = o;
    ctx.beginPath();
    ctx.ellipse(px, py + 6, 9, 4, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = couleur;
    ctx.beginPath();
    ctx.arc(px, py, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#f0c8a0';
    ctx.beginPath();
    ctx.arc(px, py - 8, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#3a2a20';
    ctx.beginPath();
    ctx.arc(px, py - 9, 5, Math.PI, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.fillRect(px - 2, py - 9, 1.5, 1.5);
    ctx.fillRect(px + 1, py - 9, 1.5, 1.5);
  }

  function nomm(px, py, texte) {
    ctx.fillStyle = '#e8eef7';
    ctx.font = '9px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText(texte, px, py - 18);
  }

  function bulle(x, y, titre, texte) {
    ctx.font = 'bold 15px system-ui';
    var wT = ctx.measureText(titre).width;
    ctx.font = '14px system-ui';
    var wS = ctx.measureText(texte).width;
    var w = Math.max(wT, wS) + 34;
    var h = 58;
    var bx = x - w / 2, by = y - h - 10;
    ctx.fillStyle = 'rgba(255,255,255,.98)';
    ctx.fillRect(bx, by, w, h);
    ctx.strokeStyle = '#334155';
    ctx.lineWidth = 2;
    ctx.strokeRect(bx, by, w, h);
    ctx.fillStyle = '#0f172a';
    ctx.textAlign = 'center';
    ctx.font = 'bold 15px system-ui';
    ctx.fillText(titre, x, by + 22);
    ctx.font = '14px system-ui';
    ctx.fillStyle = '#334155';
    ctx.fillText(texte, x, by + 44);
  }

  function peutSePlacer(px, py, qui) {
    if (px > TABLE.x && px < TABLE.x + TABLE.w && py > TABLE.y && py < TABLE.y + TABLE.h) return false;
    if (px < 16 || px > W - 16 || py < 16 || py > H - 16) return false;
    for (var k = 0; k < agents.length; k++) {
      var o = agents[k];
      if (o === qui) continue;
      var dx = px - o.x, dy = py - o.y;
      if (dx * dx + dy * dy < 200) return false;
    }
    return true;
  }

  function avancer(a, ux, uy, v) {
    if (peutSePlacer(a.x + ux * v, a.y, a)) a.x += ux * v;
    if (peutSePlacer(a.x, a.y + uy * v, a)) a.y += uy * v;
  }

  var prochainLeve = 150;

  function bougerAgents() {
    prochainLeve--;
    if (prochainLeve <= 0) {
      prochainLeve = 260 + Math.floor(Math.random() * 280);
      var dispo = agents.filter(function (a) { return a.etat === 'assis'; });
      if (dispo.length) {
        dispo[Math.floor(Math.random() * dispo.length)].etat = 'versTableau';
      }
    }
    for (var k = 0; k < agents.length; k++) {
      var a = agents[k];
      if (a.etat === 'versTableau') {
        var dx = TABLEAU.x - a.x, dy = TABLEAU.y - a.y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 4) {
          a.etat = 'auTableau';
          a.pause = 200 + Math.floor(Math.random() * 180);
        } else {
          avancer(a, dx / dist, dy / dist, 1.2);
        }
      } else if (a.etat === 'auTableau') {
        a.pause--;
        if (a.pause <= 0) a.etat = 'retour';
      } else if (a.etat === 'retour') {
        var rx = a.cx - a.x, ry = a.cy - a.y;
        var rd = Math.sqrt(rx * rx + ry * ry);
        if (rd < 4) {
          a.x = a.cx;
          a.y = a.cy;
          a.etat = 'assis';
        } else {
          avancer(a, rx / rd, ry / rd, 1.2);
        }
      }
    }
  }

  cv.addEventListener('click', function (e) {
    var rect = cv.getBoundingClientRect();
    var rx = (e.clientX - rect.left) * (cv.width / rect.width);
    var ry = (e.clientY - rect.top) * (cv.height / rect.height);
    var dbx = rx - braignak.x, dby = ry - braignak.y;
    if (dbx * dbx + dby * dby < 34 * 34) {
      if (window.ouvrirChatBraignak) window.ouvrirChatBraignak();
      return;
    }
    var meilleur = null, bestD = 260;
    for (var i = 0; i < agents.length; i++) {
      var dx = rx - agents[i].x, dy = ry - agents[i].y;
      var d = dx * dx + dy * dy;
      if (d < bestD) { bestD = d; meilleur = agents[i]; }
    }
    agentClic = meilleur;
  });

  function cadre() {
    sol();
    tableauBlanc();
    table();
    for (var c = 0; c < CHAISES.length; c++) chaise(CHAISES[c].x, CHAISES[c].y, CHAISES[c].ori);
    for (var a = 0; a < agents.length; a++) {
      bonhomme(agents[a].x, agents[a].y, agents[a].couleur);
      nomm(agents[a].x, agents[a].y, agents[a].nom);
    }
    // Le petit Braignak, cliquable
    bonhomme(braignak.x, braignak.y, '#f59e0b');
    ctx.font = 'bold 13px system-ui';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#f59e0b';
    ctx.fillText('🔭', braignak.x, braignak.y - 30);
    ctx.font = '9px system-ui';
    ctx.fillStyle = '#e8eef7';
    ctx.fillText('Braignak', braignak.x, braignak.y - 18);
    // Le visiteur
    bougeJoueur();
    bonhomme(joueur.x, joueur.y, '#0ea5e9');
    ctx.font = '9px system-ui';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#e8eef7';
    ctx.fillText('Toi', joueur.x, joueur.y - 18);
    if (agentClic) {
      bulle(agentClic.x, agentClic.y, agentClic.nom, PRESENTATIONS[agentClic.nom] || 'Membre de l’équipe.');
    }
    requestAnimationFrame(cadre);
  }
  cadre();
})();
