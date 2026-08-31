(function () {
  if (!document.getElementById('chloe-app')) return;

  var convId = null;
  var listeEl = document.getElementById('chloe-tab-list');
  var msgEl = document.getElementById('chloe-messages');
  var etapesEl = document.getElementById('chloe-etapes-list');
  var input = document.getElementById('chloe-msg');
  var head = document.getElementById('chloe-chat-head');

  function api(route, data) {
    return fetch(route, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: data || {}})
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (j && typeof j === 'object' && 'result' in j) return j.result;
      return j;
    });
  }

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = (s === null || s === undefined) ? '' : String(s);
    return d.innerHTML;
  }

  function renderMessages(messages) {
    msgEl.innerHTML = '';
    (messages || []).forEach(function (m) {
      var d = document.createElement('div');
      d.className = 'msg ' + (m.role === 'user' ? 'msg-user' : 'msg-assistant');
      d.textContent = m.content || '';
      msgEl.appendChild(d);
    });
    msgEl.scrollTop = msgEl.scrollHeight;
  }

  function renderEtapes(etapes) {
    etapesEl.innerHTML = '';
    (etapes || []).forEach(function (mission) {
      var box = document.createElement('div');
      box.className = 'mission';
      var badge = mission.etat_label
        ? ' <span class="badge badge-' + esc(mission.etat) + '">' + esc(mission.etat_label) + '</span>'
        : '';
      box.innerHTML = '<div class="mission-nom">' + esc(mission.nom) + badge + '</div>';
      var ul = document.createElement('div');
      (mission.etapes || []).forEach(function (etape) {
        var row = document.createElement('label');
        row.className = 'etape-row';
        var checked = etape.etat === 'fait';
        var half = etape.etat === 'en_cours';
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = checked;
        if (half) cb.className = 'half';
        cb.disabled = true;
        var span = document.createElement('span');
        span.textContent = etape.nom;
        row.appendChild(cb);
        row.appendChild(span);
        ul.appendChild(row);
      });
      if (!(mission.etapes || []).length) {
        var vide = document.createElement('div');
        vide.className = 'etape-vide';
        vide.textContent = 'Pas encore d’étapes.';
        ul.appendChild(vide);
      }
      box.appendChild(ul);
      etapesEl.appendChild(box);
    });
  }

  function renderTabs(convs, actif) {
    listeEl.innerHTML = '';
    (convs || []).forEach(function (c) {
      var b = document.createElement('div');
      b.className = 'tab' + (c.id === actif ? ' active' : '');
      b.textContent = c.name;
      b.onclick = function () { ouvrir(c.id); };
      listeEl.appendChild(b);
    });
  }

  function ouvrir(id) {
    api('/tour_chloe/ouvrir', {conv_id: id}).then(function (d) {
      convId = d.id;
      head.textContent = d.name;
      renderMessages(d.messages);
      renderEtapes(d.etapes);
      return api('/tour_chloe/liste', {});
    }).then(function (convs) { renderTabs(convs, convId); });
  }

  // RELEVAGE DU JETON (correctif 14/08). Le moteur est asynchrone : l'envoi
  // rend un jeton, pas la reponse. Sans ce relevage, la page affichait
  // eternellement « La reponse arrive dans un instant » — c'est exactement ce
  // qui se passait depuis le 10/08. La bulle de l'accueil fait deja ceci.
  function relever(jeton, messages, attente) {
    var essais = 0;
    var MAXI = 120;          // 120 x 5 s = 10 minutes
    var fil = (messages || []).slice();
    fil.push({role: 'assistant', content: attente || 'Je m’en occupe...'});
    renderMessages(fil);

    var timer = setInterval(function () {
      essais++;
      api('/tour_chloe/resultat', {conv_id: convId, jeton: jeton})
        .then(function (d) {
          if (!d || d.etat === 'envoye') {
            if (essais >= MAXI) {
              clearInterval(timer);
              fil[fil.length - 1] = {
                role: 'assistant',
                content: 'Toujours en cours apres 10 minutes. Rouvre la '
                       + 'conversation pour voir la reponse.'};
              renderMessages(fil);
            }
            return;
          }
          clearInterval(timer);
          renderMessages(d.messages || fil);
          renderEtapes(d.etapes);
          api('/tour_chloe/liste', {}).then(function (convs) {
            if (convs) renderTabs(convs, convId);
          });
        })
        .catch(function () {
          // Le pont n'est pas encore pret : on retente au tour suivant.
          if (essais >= MAXI) clearInterval(timer);
        });
    }, 5000);
  }

  function envoyer() {
    var texte = input.value.trim();
    if (!texte) return;
    input.value = '';
    api('/tour_chloe/envoyer', {conv_id: convId, message: texte}).then(function (d) {
      if (d.error) {
        renderMessages([{role: 'assistant', content: d.error}]);
        return;
      }
      if (d.async && d.jeton) {
        renderEtapes(d.etapes);
        relever(d.jeton, d.messages, d.attente);
        return api('/tour_chloe/liste', {});
      }
      renderMessages(d.messages);
      renderEtapes(d.etapes);
      return api('/tour_chloe/liste', {});
    }).then(function (convs) { if (convs) renderTabs(convs, convId); });
  }

  function rafraichirEtapes() {
    if (convId) api('/tour_chloe/ouvrir', {conv_id: convId}).then(function (d) {
      renderEtapes(d.etapes);
    });
  }

  document.getElementById('chloe-new').onclick = function () {
    api('/tour_chloe/nouveau', {}).then(function (d) { ouvrir(d.id); });
  };
  document.getElementById('chloe-send').onclick = envoyer;
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); envoyer(); }
  });

  api('/tour_chloe/ouvrir', {conv_id: 0}).then(function (d) {
    convId = d.id;
    head.textContent = d.name;
    renderMessages(d.messages);
    renderEtapes(d.etapes);
    return api('/tour_chloe/liste', {});
  }).then(function (convs) { renderTabs(convs, convId); });

  setInterval(rafraichirEtapes, 15000);
})();
