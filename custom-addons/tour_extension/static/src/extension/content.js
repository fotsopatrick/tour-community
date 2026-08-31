// Content script général : le pont entre la page et l'extension.
//
// La page envoie window.postMessage -> ici on le reçoit, on le transmet au
// background, et on renvoie les résultats à la page. C'est le canal
// "page <-> content script <-> background".
//
// GARDE ANTI-ÉCHO (31/07) : on ne retransmet à l'extension QUE les messages
// qui portent une `question`. Sans ce garde-fou, le content script ré-émettait
// sa PROPRE réponse -> ça bouclait à l'infini.

window.addEventListener("message", (event) => {
  if (event.source !== window) return;
  const data = event.data;
  if (!data || data.__tour !== 1) return;
  if (!data.question || typeof data.question !== "string") return;

  chrome.runtime.sendMessage({ type: "recherche", question: data.question }, (reponse) => {
    window.postMessage(
      { __tour: 1, direction: "page<-ext", reponse: reponse || "(pas de reponse)" },
      "*"
    );
  });
});

// Depuis l'extension vers la page (résultats de recherche)
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.type === "resultats") {
    window.postMessage(
      { __tour: 1, direction: "resultats", resultats: message.resultats || [] },
      "*"
    );
    sendResponse({ ok: true });
  }
});
