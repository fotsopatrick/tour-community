(function(){
  'use strict';

  // ─── CSS ────────────────────────────────────────────────────────────────
  var style = document.createElement('style');
  style.textContent =
    '#chloe-btn{' +
      'position:fixed;bottom:24px;right:24px;z-index:2147483647;' +
      'width:56px;height:56px;border-radius:50%;background:#3b82f6;' +
      'border:none;cursor:pointer;' +
      'box-shadow:0 4px 16px rgba(59,130,246,0.4);' +
      'display:flex;align-items:center;justify-content:center;' +
      'transition:transform 0.2s, box-shadow 0.2s;' +
    '}' +
    '#chloe-btn:hover{' +
      'transform:scale(1.08);' +
      'box-shadow:0 6px 24px rgba(59,130,246,0.5);' +
    '}' +
    '#chloe-btn:active{' +
      'transform:scale(0.95);' +
    '}' +
    '#chloe-btn svg{' +
      'width:26px;height:26px;fill:white;display:block;' +
    '}' +

    '#chloe-panel{' +
      'position:fixed;bottom:96px;right:24px;z-index:2147483646;' +
      'width:360px;height:480px;border-radius:12px;' +
      'background:#0f172a;' +
      'box-shadow:0 8px 32px rgba(0,0,0,0.5);' +
      'display:none;flex-direction:column;' +
      'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;' +
      'color:#e2e8f0;overflow:hidden;' +
      'animation:chloe-slide 0.2s ease-out;' +
    '}' +
    '#chloe-panel.open{' +
      'display:flex;' +
    '}' +
    '@keyframes chloe-slide{' +
      'from{opacity:0;transform:translateY(12px)}' +
      'to{opacity:1;transform:translateY(0)}' +
    '}' +

    '#chloe-header{' +
      'display:flex;align-items:center;justify-content:space-between;' +
      'padding:14px 16px;background:#1e293b;' +
      'border-bottom:1px solid #334155;' +
      'border-radius:12px 12px 0 0;flex-shrink:0;' +
    '}' +
    '#chloe-header-title{' +
      'font-weight:600;font-size:15px;' +
      'display:flex;align-items:center;gap:8px;' +
    '}' +
    '#chloe-header-title svg{' +
      'width:18px;height:18px;fill:#3b82f6;' +
    '}' +
    '#chloe-header-close{' +
      'background:none;border:none;color:#94a3b8;cursor:pointer;' +
      'font-size:20px;line-height:1;padding:2px 6px;border-radius:4px;' +
      'transition:background 0.15s;' +
    '}' +
    '#chloe-header-close:hover{' +
      'background:#334155;color:#f1f5f9;' +
    '}' +
    '#chloe-header-clear{' +
      'background:none;border:none;color:#94a3b8;cursor:pointer;' +
      'font-size:17px;line-height:1;padding:2px 6px;border-radius:4px;' +
      'transition:background 0.15s;' +
    '}' +
    '#chloe-header-clear:hover{' +
      'background:#334155;color:#f1f5f9;' +
    '}' +
    '#chloe-header-refresh{' +
      'background:none;border:none;color:#94a3b8;cursor:pointer;' +
      'font-size:17px;line-height:1;padding:2px 6px;border-radius:4px;' +
      'transition:background 0.15s;' +
    '}' +
    '#chloe-header-refresh:hover{' +
      'background:#334155;color:#f1f5f9;' +
    '}' +

    '#chloe-messages{' +
      'flex:1;overflow-y:auto;padding:12px 16px;' +
      'display:flex;flex-direction:column;gap:10px;scroll-behavior:smooth;' +
    '}' +
    '#chloe-messages::-webkit-scrollbar{' +
      'width:5px;' +
    '}' +
    '#chloe-messages::-webkit-scrollbar-track{' +
      'background:transparent;' +
    '}' +
    '#chloe-messages::-webkit-scrollbar-thumb{' +
      'background:#475569;border-radius:3px;' +
    '}' +

    '.chloe-msg{' +
      'max-width:85%;padding:9px 14px;border-radius:14px;' +
      'font-size:14px;line-height:1.45;word-wrap:break-word;' +
    '}' +
    '.chloe-msg.user{' +
      'align-self:flex-end;background:#3b82f6;color:white;' +
      'border-bottom-right-radius:4px;' +
    '}' +
    '.chloe-msg.bot{' +
      'align-self:flex-start;background:#1e293b;color:#e2e8f0;' +
      'border-bottom-left-radius:4px;' +
    '}' +
    '.chloe-msg.bot.error{' +
      'background:#7f1d1d;color:#fca5a5;' +
    '}' +
    '.chloe-msg .chloe-time{' +
      'font-size:10px;opacity:0.6;margin-top:4px;text-align:right;' +
    '}' +

    '#chloe-typing{' +
      'display:none;align-self:flex-start;background:#1e293b;' +
      'padding:10px 18px;border-radius:14px;' +
      'border-bottom-left-radius:4px;gap:5px;' +
    '}' +
    '#chloe-typing.show{' +
      'display:flex;' +
    '}' +
    '#chloe-typing span{' +
      'width:7px;height:7px;border-radius:50%;background:#64748b;' +
      'animation:chloe-bounce 1.2s infinite;' +
    '}' +
    '#chloe-typing span:nth-child(2){animation-delay:0.2s}' +
    '#chloe-typing span:nth-child(3){animation-delay:0.4s}' +
    '@keyframes chloe-bounce{' +
      '0%,60%,100%{transform:translateY(0)}' +
      '30%{transform:translateY(-6px)}' +
    '}' +

    '#chloe-input-area{' +
      'display:flex;align-items:center;gap:8px;' +
      'padding:10px 12px 12px;border-top:1px solid #334155;' +
      'flex-shrink:0;background:#0f172a;' +
    '}' +
    '#chloe-input{' +
      'flex:1;background:#1e293b;border:1px solid #334155;' +
      'border-radius:8px;padding:10px 14px;color:#e2e8f0;' +
      'font-size:14px;outline:none;transition:border 0.15s;' +
    '}' +
    '#chloe-input:focus{' +
      'border-color:#3b82f6;' +
    '}' +
    '#chloe-input::placeholder{' +
      'color:#64748b;' +
    '}' +
    '#chloe-send{' +
      'background:#3b82f6;border:none;border-radius:8px;' +
      'width:40px;height:40px;' +
      'display:flex;align-items:center;justify-content:center;' +
      'cursor:pointer;transition:background 0.15s, transform 0.15s;flex-shrink:0;' +
    '}' +
    '#chloe-send:hover{' +
      'background:#2563eb;' +
    '}' +
    '#chloe-send:active{' +
      'transform:scale(0.92);' +
    '}' +
    '#chloe-send svg{' +
      'width:18px;height:18px;fill:white;' +
    '}' +
    '#chloe-send:disabled{' +
      'background:#475569;cursor:not-allowed;transform:none;' +
    '}';
  document.head.appendChild(style);

  // ─── HTML ───────────────────────────────────────────────────────────────

  // Bouton flottant
  var btn = document.createElement('button');
  btn.id = 'chloe-btn';
  btn.setAttribute('aria-label', 'Ouvrir le chat Chloe');
  btn.innerHTML =
    '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">' +
      '<path d="M12 2C6.48 2 2 6.48 2 12c0 1.88.52 3.73 1.5 5.28L2 22l4.72-1.5C8.27 21.48 10.12 22 12 22c5.52 0 10-4.48 10-10S17.52 2 12 2zm0 18c-1.46 0-2.86-.35-4.12-1.02l-.3-.17-2.8.89.89-2.8-.17-.3C4.35 14.86 4 13.46 4 12c0-4.41 3.59-8 8-8s8 3.59 8 8-3.59 8-8 8z"/>' +
      '<path d="M11 11h2v6h-2zm0-4h2v2h-2z"/>' +
    '</svg>';

  // Panneau
  var panel = document.createElement('div');
  panel.id = 'chloe-panel';

  // Entete
  var header = document.createElement('div');
  header.id = 'chloe-header';

  var title = document.createElement('div');
  title.id = 'chloe-header-title';
  title.innerHTML =
    '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/></svg>' +
    'Chloe';

  var closeBtn = document.createElement('button');
  closeBtn.id = 'chloe-header-close';
  closeBtn.setAttribute('aria-label', 'Fermer');
  closeBtn.innerHTML = '&times;';

  var refreshBtn = document.createElement('button');
  refreshBtn.id = 'chloe-header-refresh';
  refreshBtn.setAttribute('aria-label', 'Recharger la conversation');
  refreshBtn.title = 'Recharger la conversation';
  refreshBtn.innerHTML = '&#10227;';

  var clearBtn = document.createElement('button');
  clearBtn.id = 'chloe-header-clear';
  clearBtn.setAttribute('aria-label', 'Effacer la conversation');
  clearBtn.title = 'Effacer la conversation';
  clearBtn.innerHTML = '&#128465;';

  header.appendChild(title);
  header.appendChild(refreshBtn);
  header.appendChild(clearBtn);
  header.appendChild(closeBtn);

  // Messages
  var msgBox = document.createElement('div');
  msgBox.id = 'chloe-messages';

  // Typing indicator
  var typing = document.createElement('div');
  typing.id = 'chloe-typing';
  typing.innerHTML = '<span></span><span></span><span></span>';

  // Input area
  var inputArea = document.createElement('div');
  inputArea.id = 'chloe-input-area';

  var input = document.createElement('input');
  input.type = 'text';
  input.id = 'chloe-input';
  input.placeholder = 'Ecrivez votre message...';
  input.setAttribute('autocomplete', 'off');

  var fichier = document.createElement('input');
  fichier.type = 'file';
  fichier.id = 'chloe-fichier';
  fichier.style.display = 'none';
  fichier.accept = '.png,.jpg,.jpeg,.gif,.webp,.pdf,.txt,.log,.json';
  fichier.addEventListener('change', onFichier);

  var clipBtn = document.createElement('button');
  clipBtn.id = 'chloe-clip';
  clipBtn.setAttribute('aria-label', 'Joindre une capture');
  clipBtn.title = 'Joindre une capture — dis « bug » et je la range dans la tour';
  clipBtn.innerHTML = '&#128206;';
  clipBtn.addEventListener('click', function(){ fichier.click(); });

  var pieceBar = document.createElement('div');
  pieceBar.id = 'chloe-piece';
  pieceBar.style.cssText =
    'display:none;align-items:center;gap:8px;padding:6px 12px;' +
    'background:#1e293b;border-top:1px solid #334155;font-size:12.5px;' +
    'color:#e2e8f0;flex-shrink:0;';

  var sendBtn = document.createElement('button');
  sendBtn.id = 'chloe-send';
  sendBtn.setAttribute('aria-label', 'Envoyer');
  sendBtn.innerHTML =
    '<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';

  inputArea.appendChild(fichier);
  inputArea.appendChild(clipBtn);
  inputArea.appendChild(input);
  inputArea.appendChild(sendBtn);

  panel.appendChild(header);
  panel.appendChild(msgBox);
  panel.appendChild(typing);
  panel.appendChild(pieceBar);
  panel.appendChild(inputArea);

  document.body.appendChild(btn);
  document.body.appendChild(panel);

  // ─── LOGIQUE ────────────────────────────────────────────────────────────

  var LS_KEY  = 'tour_copilote.history';
  var API_URL = '/tour_copilote/chat';
  var history = [];

  // Charger historique
  function loadHistory(){
    try{
      var raw = localStorage.getItem(LS_KEY);
      if(raw){
        var parsed = JSON.parse(raw);
        if(Array.isArray(parsed)){
          history = parsed;
        }
      }
    }catch(e){ /* silencieux */ }
  }

  // Sauvegarder historique
  function saveHistory(){
    try{
      localStorage.setItem(LS_KEY, JSON.stringify(history));
    }catch(e){ /* silencieux */ }
  }

  // Rendu de tous les messages
  function renderAll(){
    msgBox.innerHTML = '';
    for(var i = 0; i < history.length; i++){
      appendMessageDOM(history[i].role, history[i].content);
    }
    scrollDown();
  }

  // Ajouter un message au DOM
  function appendMessageDOM(role, content, extraClass){
    var div = document.createElement('div');
    div.className = 'chloe-msg ' + (role === 'user' ? 'user' : 'bot') + (extraClass ? ' ' + extraClass : '');
    var text = document.createElement('div');
    text.textContent = content;
    div.appendChild(text);
    var time = document.createElement('div');
    time.className = 'chloe-time';
    var now = new Date();
    time.textContent =
      now.getHours().toString().padStart(2,'0') + ':' +
      now.getMinutes().toString().padStart(2,'0');
    div.appendChild(time);
    msgBox.appendChild(div);
    scrollDown();
  }

  // Defilement vers le bas
  function scrollDown(){
    msgBox.scrollTop = msgBox.scrollHeight;
  }

  // Ajouter un message a l'historique + DOM
  function addMessage(role, content){
    history.push({role: role, content: content});
    saveHistory();
    appendMessageDOM(role, content);
  }

  var pieceEnAttente = null;

  function onFichier(evt){
    var f = evt.target.files && evt.target.files[0];
    if(!f) return;
    var lecteur = new FileReader();
    lecteur.onload = function(){
      pieceEnAttente = { nom: f.name, donnees: lecteur.result };
      pieceBar.innerHTML =
        '<span>&#128206; ' + (f.name || '') + '</span>' +
        '<button id="chloe-piece-x" style="background:none;border:none;' +
        'color:#94a3b8;cursor:pointer;font-size:15px;">&times;</button>';
      pieceBar.style.display = 'flex';
      var x = document.getElementById('chloe-piece-x');
      if(x) x.addEventListener('click', function(){
        pieceEnAttente = null;
        pieceBar.style.display = 'none';
        fichier.value = '';
      });
    };
    lecteur.readAsDataURL(f);
  }

  function effacerConversation(){
    history = [];
    saveHistory();
    msgBox.innerHTML = '';
    if(pieceEnAttente){ pieceEnAttente = null; pieceBar.style.display = 'none'; fichier.value = ''; }
    scrollDown();
  }

  function rechargerConversation(){
    history = [];
    loadHistory();
    renderAll();
    scrollDown();
  }

  // Rendu d'un message bot avec ses actions
  function appendMessageDOM(role, content, extraClass, actions){
    var div = document.createElement('div');
    div.className = 'chloe-msg ' + (role === 'user' ? 'user' : 'bot') + (extraClass ? ' ' + extraClass : '');
    var text = document.createElement('div');
    text.textContent = content;
    div.appendChild(text);
    if(actions && actions.length){
      var box = document.createElement('div');
      box.className = 'chloe-actions';
      box.style.cssText = 'margin-top:6px;font-size:12px;color:#a5b4fc;';
      for(var i = 0; i < actions.length; i++){
        var a = document.createElement('div');
        a.textContent = '\u2713 ' + actions[i];
        box.appendChild(a);
      }
      div.appendChild(box);
    }
    var time = document.createElement('div');
    time.className = 'chloe-time';
    var now = new Date();
    time.textContent =
      now.getHours().toString().padStart(2,'0') + ':' +
      now.getMinutes().toString().padStart(2,'0');
    div.appendChild(time);
    msgBox.appendChild(div);
    scrollDown();
  }

  // Envoyer un message
  async function sendMessage(){
    var text = input.value.trim();
    var avecPiece = !!pieceEnAttente;
    if(!text && !avecPiece) return;

    // Bloquer UI
    input.value = '';
    sendBtn.disabled = true;
    input.disabled = true;
    typing.classList.add('show');
    scrollDown();

    // Message user
    addMessage('user', text || '(capture jointe)');

    // Appel API
    try{
      var body = JSON.stringify({
        jsonrpc: '2.0',
        method: 'call',
        params: {
          messages: history,
          piece_jointe: pieceEnAttente || null
        }
      });
      pieceEnAttente = null;
      pieceBar.style.display = 'none';
      fichier.value = '';

      var resp = await fetch(API_URL, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: body
      });

      if(!resp.ok){
        throw new Error('HTTP ' + resp.status);
      }

      var data = await resp.json();
      var reply = null;

      if(data && data.result){
        if(typeof data.result.reply === 'string'){
          reply = data.result.reply;
        }else if(data.result.messages && Array.isArray(data.result.messages)){
          var last = data.result.messages[data.result.messages.length - 1];
          if(last && last.content){
            reply = last.content;
          }else if(typeof last === 'string'){
            reply = last;
          }
        }else{
          reply = JSON.stringify(data.result);
        }
      }

      if(reply){
        addMessage('bot', reply);
        var actions = (data.result && data.result.actions) || [];
        if(actions.length && history.length){
          // afficher les actions sous le dernier message bot
          var msgs = msgBox.querySelectorAll('.chloe-msg.bot');
          var last = msgs[msgs.length - 1];
          if(last){
            var box = document.createElement('div');
            box.className = 'chloe-actions';
            box.style.cssText = 'margin-top:6px;font-size:12px;color:#a5b4fc;';
            for(var i = 0; i < actions.length; i++){
              var a = document.createElement('div');
              a.textContent = '\u2713 ' + actions[i];
              box.appendChild(a);
            }
            last.appendChild(box);
          }
        }
      }else{
        addMessage('bot', 'Chloe est indisponible', 'error');
      }

    }catch(err){
      addMessage('bot', 'Chloe est indisponible', 'error');
    }finally{
      sendBtn.disabled = false;
      input.disabled = false;
      typing.classList.remove('show');
      input.focus();
      scrollDown();
    }
  }

  // Ouverture / fermeture
  function openPanel(){
    panel.classList.add('open');
    input.focus();
  }
  function closePanel(){
    panel.classList.remove('open');
  }
  function togglePanel(){
    if(panel.classList.contains('open')){
      closePanel();
    }else{
      openPanel();
    }
  }

  // ─── EVENTS ─────────────────────────────────────────────────────────────
  btn.addEventListener('click', togglePanel);
  closeBtn.addEventListener('click', closePanel);
  refreshBtn.addEventListener('click', rechargerConversation);
  clearBtn.addEventListener('click', effacerConversation);
  sendBtn.addEventListener('click', sendMessage);
  input.addEventListener('keydown', function(e){
    if(e.key === 'Enter' && !e.shiftKey){
      e.preventDefault();
      sendMessage();
    }
  });

  // ─── INIT ───────────────────────────────────────────────────────────────
  loadHistory();
  renderAll();

  // Exposer pour debug
  window.__chloe = {
    history: history,
    addMessage: addMessage,
    sendMessage: sendMessage,
    openPanel: openPanel,
    closePanel: closePanel,
    effacer: effacerConversation,
    recharger: rechargerConversation
  };

})();
