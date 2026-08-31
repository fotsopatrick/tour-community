# ALICE + Carte vivante — déployés sur Azure ACI (29/08/2026)

## URL

| Service | URL | État |
|---|---|---|
| ALICE (gate + webapp + ingest) | http://alice-demo-2026.eastus2.azurecontainer.io:8000 | ✅ Running |
| Carte vivante | http://carte-vivante-2026.eastus2.azurecontainer.io | ✅ Running |

## ALICE — endpoints (vérifiés)

- `GET  /health`                    → {"service":"alice-gate","status":"ok","memoire":{...}}
- `GET  /`                          → UI chat (chat.html)
- `POST /api/v1/ingest`             → {text|url|file} → {"status":"ok","chunks":N}
- `GET  /api/v1/knowledge?q=...`    → recherche dans la mémoire
- `GET  /connaissances`             → liste des documents ingérés
- `POST /chat`                      → réponse du cerveau (Azure OpenAI gpt-5-mini)
- `GET  /api/v1/gate/<job_id>`, `POST /api/v1/gate` (jobs)

## Infrastructure Azure (groupe rg-alice-azure, eastus2)

- ACR  : `acralice9caf1.azurecr.io` — images `alice:latest`, `carte-vivante:latest`
- ACI  : `alice-gate` (CPU 1, RAM 1 Go, port 8000)
- ACI  : `carte-vivante` (CPU 0.5, RAM 0.5, port 80)
- Cerveau ALICE : Azure OpenAI `tourdecontrole.openai.azure.com`, déploiement
  `gpt-5-mini` (validé HTTP 200), clé passée en variable SÉCURISÉE (jamais en dur).
- Mémoire : SQLite éphémère (`/tmp/alice/state/alice.db`) — l'ingestion vit dans
  le conteneur ; un redémarrage ACI vide la mémoire. Suivi : PostgreSQL (Flexible
  Server) pour la persistance.

## Comment c'est construit

- Source : `deploiement-azure/alice/` (src/alice_gate.py + src/alicization/)
- Build local (nomi) puis push ACR : `az acr build` est bloqué sur cette
  subscription (`TasksOperationsNotAllowed`).
- Piège build réglé : le DNS de la machine de build est instable pour `apt`
  (libapt), donc la couche `apt-get install curl poppler-utils` a été retirée
  du Dockerfile. Conséquence : l'ingest PDF répond une erreur claire
  (pdftotext absent) ; l'ingest `.txt` / `.md` / URL fonctionne.
- La carte vivante est servie par un conteneur statique (http.server).

## Accès Azure (identifiants)

- Les identifiants Azure vivent dans le coffre du conteneur `alicization-builder`
  (`/root/.tour-vault/env.cloud`) et dans `.env.azure` sur tour-vps.
  Aucun secret n'est committé.

## Tests

- `python3 deploy/alice/tests_alice.py` : mémoire + santé + carte + OCR (adapté à l'URL ACI).
- Vérification manuelle détaillée dans le RAPPORT-COMPLET (ingest, knowledge, chat).