/* La vue LIVE d'un débat (08/08, Patrick) : au clic sur un débat, une
 * mini-salle avec les SEULS membres concernés, leurs messages en bulles
 * au-dessus de la tête, et le chat qui défile à droite — comme une vue
 * live de YouTube. Réutilise le dessin du bureau (bonhomme, chaise,
 * table, bulle) sans en dépendre : le code est autonome.
 */
(function () {
  var PALETTE = ['#4f8ef7','#e868a8','#3fa63f','#c9a227','#e06040','#8a5ae0',
                 '#2bb8c9','#d8732a','#7a9a4a','#b04090','#5a6ae0','#c04040',
                 '#2fae5a','#d0b040','#4090b0','#b060c0','#60b060','#f59e0b'];

  function couleurDe(nom) {
    var h = 0;
    for (var i = 0; i < nom.length; i++) h = (h * 31 + nom.charCodeAt(i)) >>> 0;
    return PALETTE[h % PALETTE.length];
  }

  /* Place les N agents autour d'une table rectangulaire. On rend les
   * positions en proportions [0..1] du canvas, pour une taille adaptée. */
  function places(n, W, H) {
    var r = [];
    if (n <= 1) {
      r = [{ x: .5, y: .5 }];
    } else if (n <= 4) {
      // une table, agents au nord et au sud
      for (var i = 0; i < n; i++) {
        var cote = i % 2;                       // 0 nord, 1 sud
        var idx = Math.floor(i / 2);
        var nb = Math.ceil(n / 2);
        var x = .5 - (nb - 1) * .14 + idx * .28;
        r.push({ x: x, y: cote === 0 ? .3 : .7 });
      }
    } else if (n <= 8) {
      // deux rangées de 4 max
      for (var j = 0; j < n; j++) {
        var c = j % 2;
        var k = Math.floor(j / 2);
        var m = Math.ceil(n / 2);
        var x2 = .5 - (m - 1) * .17 + k * .34;
        r.push({ x: x2, y: c === 0 ? .28 : .72 });
      }
    } else {
      // grille autour de la table
      var cols = Math.min(5, Math.ceil(Math.sqrt(n * 2.2)));
      var rows = Math.ceil(n / cols);
      for (var a = 0; a < n; a++) {
        var ci = a % cols;
        var ri = Math.floor(a / cols);
        var x3 = (ci + .5) / cols;
        var y3 = (ri + .5) / rows;
        r.push({ x: x3, y: y3 });
      }
    }
    return r;
  }

  function bonhomme(ctx, px, py, couleur, embleme, nom) {
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
    if (embleme && embleme !== '•') {
      ctx.font = 'bold 12px system-ui';
      ctx.textAlign = 'center';
      ctx.fillStyle = '#020817';
      ctx.fillText(embleme, px, py + 4);
    }
    ctx.fillStyle = '#e8eef7';
    ctx.font = '9px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText(nom, px, py - 18);
  }

  function bulle(ctx, x, y, titre, texte, couleur) {
    ctx.font = 'bold 13px system-ui';
    var wT = ctx.measureText(titre).width;
    ctx.font = '12px system-ui';
    var wS = ctx.measureText(texte).width;
    var w = Math.max(wT, wS) + 30;
    w = Math.min(w, 320);
    var h = 52;
    var bx = x - w / 2, by = y - h - 12;
    if (bx < 4) bx = 4;
    if (bx + w > ctx.canvas.width - 4) bx = ctx.canvas.width - w - 4;
    if (by < 4) by = y + 22;
    ctx.fillStyle = 'rgba(255,255,255,.98)';
    ctx.fillRect(bx, by, w, h);
    ctx.strokeStyle = couleur || '#334155';
    ctx.lineWidth = 2;
    ctx.strokeRect(bx, by, w, h);
    ctx.fillStyle = '#0f172a';
    ctx.textAlign = 'center';
    ctx.font = 'bold 13px system-ui';
    ctx.fillText(titre, x, by + 18);
    ctx.font = '12px system-ui';
    ctx.fillStyle = '#334155';
    // coupe le texte à la largeur de la bulle
    var ligne = texte;
    while (ctx.measureText(ligne).width > w - 16 && ligne.length > 1)
      ligne = ligne.slice(0, -1);
    ctx.fillText(ligne + (ligne.length < texte.length ? '…' : ''), x, by + 36);
  }

  function table(ctx, W, H) {
    var tx = W * .18, ty = H * .42, tw = W * .64, th = H * .16;
    ctx.fillStyle = 'rgba(0,0,0,.14)';
    ctx.fillRect(tx + 4, ty + 4, tw, th);
    var g = ctx.createLinearGradient(tx, ty, tx, ty + th);
    g.addColorStop(0, '#c39a68');
    g.addColorStop(1, '#9a6f42');
    ctx.fillStyle = g;
    ctx.fillRect(tx, ty, tw, th);
    ctx.strokeStyle = '#7a5430';
    ctx.lineWidth = 2;
    ctx.strokeRect(tx, ty, tw, th);
    ctx.fillStyle = '#f8f4e8';
    ctx.font = 'bold ' + Math.max(9, W * .014) + 'px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('TABLE DE RÉUNION', W / 2, ty + th / 2 + 3);
  }

  function dessiner(ctx, d, etat, W, H) {
    var agents = etat.agents;
    ctx.fillStyle = '#cfc6b4';
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = '#b0a68f';
    ctx.lineWidth = 1;
    for (var y = 0; y < H; y += 26) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }
    ctx.fillStyle = '#8a7f6a';
    ctx.fillRect(0, 0, W, 4);
    ctx.fillRect(0, H - 4, W, 4);
    table(ctx, W, H);
    for (var i = 0; i < agents.length; i++) {
      var a = agents[i];
      // chaise : petit carré derrière le personnage
      ctx.fillStyle = '#20202a';
      ctx.fillRect(a.x - 6, a.y + 8, 12, 5);
      bonhomme(ctx, a.x, a.y, a.couleur, a.embleme, a.nom);
    }
    if (etat.bulle) {
      var qui = etat.bulle.agent;
      bulle(ctx, qui.x, qui.y, qui.nom, etat.bulle.texte, qui.couleur);
    }
  }

  function chargerDebat(data) {
    var ecran = document.getElementById('ecran');
    var zoneSalle = document.getElementById('ec-salle');
    var chat = document.getElementById('ec-chat');
    var conclu = document.getElementById('ec-conclu');
    document.getElementById('ec-question').textContent = data.question;
    document.getElementById('ec-synthese').textContent =
      data.synthese || 'Aucune conclusion écrite — mais voici le fil de la discussion.';
    conclu.style.display = 'none';
    chat.innerHTML = '';
    zoneSalle.innerHTML = '';

    var cv = document.createElement('canvas');
    cv.width = 900;
    cv.height = 380;
    cv.style.width = '100%';
    cv.style.height = 'auto';
    cv.style.display = 'block';
    zoneSalle.appendChild(cv);
    var ctx = cv.getContext('2d');
    var W = cv.width, H = cv.height;

    // participants concernés, dédupliqués dans l'ordre des messages
    var vus = {}, ags = [];
    (data.participants || []).forEach(function (p) {
      if (!p.nom || vus[p.nom]) return;
      vus[p.nom] = true;
      ags.push(p);
    });
    (data.messages || []).forEach(function (m) {
      if (!vus[m.auteur]) { vus[m.auteur] = true; ags.push({ nom: m.auteur, embleme: '•' }); }
    });
    var pos = places(ags.length, W, H);
    var agents = ags.map(function (p, i) {
      return {
        nom: p.nom, embleme: p.embleme, couleur: couleurDe(p.nom),
        x: pos[i].x * W, y: pos[i].y * H
      };
    });
    var etat = { agents: agents, bulle: null };

    dessiner(ctx, data, etat, W, H);

    // le fil : chaque message en bulle sur la tête de son auteur, et en
    // parallèle dans le chat de droite (façon YouTube Live)
    var msgs = data.messages || [];
    var idx = 0;
    function suite() {
      if (idx >= msgs.length) {
        conclu.style.display = 'block';
        conclu.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        return;
      }
      var m = msgs[idx++];
      // bulle au-dessus de la tête de l'auteur (le temps de lire)
      var a = null;
      for (var k = 0; k < agents.length; k++)
        if (agents[k].nom === m.auteur) { a = agents[k]; break; }
      if (a) {
        etat.bulle = { agent: a, texte: m.texte };
        dessiner(ctx, data, etat, W, H);
      }
      // message dans le chat à droite
      var el = document.createElement('div');
      el.className = 'm ia';
      var texte = m.texte;
      var elq = document.createElement('div');
      elq.className = 'qui';
      elq.textContent = m.auteur;
      var elt = document.createElement('div');
      elt.textContent = texte;
      el.appendChild(elq);
      el.appendChild(elt);
      chat.appendChild(el);
      chat.scrollTop = chat.scrollHeight;
      // durée de lecture proportionnelle à la longueur
      var duree = Math.min(9000, Math.max(2600, m.texte.length * 22));
      setTimeout(suite, duree);
    }
    setTimeout(suite, 600);
  }

  window.ouvrirDebatLive = function (data) {
    var ecran = document.getElementById('ecran');
    ecran.classList.add('vu');
    chargerDebat(data);
  };
})();
