# Circuit de déploiement — ALICE & Tour sur le cloud (rejouable)

- **Objet** : démontrer le cloud (Google Cloud Run + Azure ACI) pour la Tour
  Community (Odoo 18, Chloé/Braignak sur Gemini) et ALICE (gate + routeur,
  cerveau Gemini via `ALICE_BRAIN_URL`).
- **Date** : 2026-08-29 — **Statut : IMAGE PUBLIÉE (ghcr.io, relais alice) ; déploiements BLOQUÉS (H1–H3, H6 — voir §2).**
- **Environnement d'exécution** : Debian 12 (bookworm), x86_64, root,
  réseau sortant OK (Internet, login.microsoftonline.com joignable).
  Répertoire de travail : `/workspace/deploiement-cloud/`.
- **Règle** : chaque commande ci-dessous est exécutée puis **loggée** ; toute
  étape à interaction humaine est notée **HUMAIN** et bloque la suite.

---

## 1. État de l'environnement (vérifié le 29/08)

| Outil | Version / état |
|---|---|
| gcloud | 582.0.0 (installé : `curl https://sdk.cloud.google.com \| bash`) |
| az | 2.89.1 (installé : `curl -sL https://aka.ms/InstallAzureCLIDeb \| bash`) |
| docker | 20.10.24+dfsg1 (installé : `apt-get install -y docker.io`) |
| python3 | 3.11.2, pip 26.2.1 |
| réseau | `storage.googleapis.com`→400(attendue), `login.microsoftonline.com/organizations/…/openid-configuration`→200 |
| ALICE local (gate) | `http://192.168.1.61:8000/health` → `{"service":"alice-gate","status":"ok"}` (joignable depuis ce poste) |
| clés Gemini | 2 clés réelles validées (HTTP 200, `gemini-3.5-flash`) : clé ALICE `AQ.…xI AET` et clé TOUR `AQ.Ab8RN6KbnU…` (projet 168611493705) |

Coffre d'identifiants : `/root/.tour-vault/env.cloud` (chmod 600, hors
dépôt). Secrets **jamais** écrits dans ce circuit ni dans un commit.

## 2. PRÉREQUIS HUMAINS (bloquants — à lever avant toute reprise)

Les identifiants reçus le 29/08 pour le déploiement se sont révélés
**non exploitables** ; preuves mesures dans §3.

- **H1 — Service Account GCP valide (HUMAIN).** Le JSON fourni contient
  `"private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"`
  (placeholder, pas une vraie clé).
  _Action_ : générer une clé dans Console GCP → IAM → Comptes de service →
  (projet `tour-community-2026`) → Clés → « Ajouter une clé → JSON », puis :
  `chmod 600 /root/.tour-vault/gcp-sa.json` puis
  `gcloud auth activate-service-account --key-file=/root/.tour-vault/gcp-sa.json`
- **H2 — Projet GCP avec billing (HUMAIN).** Réclamer les crédits Google
  Cloud (console Cloud / hackathon « All Things Agentic ») et vérifier que la
  facturation est **activée sur le projet** sinon `gcloud services enable`
  échoue : `gcloud billing projects list`.
- **H3 — Service Principal Azure valide (HUMAIN).** Le tenant fourni
  `a1b2c3d4-…‑ef1234567890` **n'existe pas** (AADSTS90002). Le subscription
  `6db5d8cf-…` est donc inaccessible.
  _Action_ : fournir un tenant réel (console Azure AD → locataires) + SP avec
  rôle `Contributor` sur la subscription ciblée, puis mettre à jour
  `/root/.tour-vault/env.cloud` et relancer §5.4.
- **H4 — Clé Gemini pour le déploiement (HUMAIN).** La clé « Gemini » du bloc
  transmis est tronquée (`AIzaSyD[...]` — non exploitable). Deux clés réelles
  existent déjà (ALICE + TOUR, validées) ; les injecter à l'exécution :
  `export GEMINI_API_KEY="AQ.Ab8RN6KbnU…"` (jamais en dur dans le code).
- **H5 — Étendre la portée du token GitHub (HUMAIN).** Le push du lot
  « déploiement cloud » vers `fotsopatrick/tour-community` est **refusé 403**
  (`remote: Permission to fotsopatrick/tour-community.git denied`) : le
  fine-grained token écrit sur `alice` mais pas sur `tour-community` (l'API
  /repos renvoie des permissions *du compte*, pas celles du token).
  _Action_ : GitHub → Settings → Developer settings → Fine-grained tokens →
  le token → Repository access : ajouter `tour-community` → Contents : Read
  **and write**. Le commit `1e3a01e` est prêt (local), prêt à `git push`.
  (Docker Hub : poser `DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN` comme secrets du
  repo pour publier aussi `fotsopatrick/tour-community:latest`.)
  ➜ **10/08 16h00 — CONTOURNÉ (sans le token tour-community)** : l'image est
  publiée via un workflow relais hébergé dans `fotsopatrick/alice`
  (`.github/workflows/tour-publish.yml`, code sous `cloud/tour/`). Le token
  « tour community » fourni ensuite **échoue aussi** (403) → portée toujours
  insuffisante côté repo tour-community. Non bloquant pour l'image :
  ghcr.io/fotsopatrick/tour-community:latest est **publique et pullable**.
- **H6 — Clés Azure OpenAI reçues mais aucun déploiement appelable (HUMAIN).**
  Authentification **200** sur `tourdecontrole.openai.azure.com` (clé
  validée, catalogue de ~200 modèles), mais chaque tentative de chat sur les
  noms usuels de déploiement échoue en `DeploymentNotFound` (vérifié sur
  `gpt-4o, gpt-4o-mini, gpt-35-turbo, gpt-5…` et noms courts `chat/test/dev…`).
  _Action_ : provisionner un déploiement dans AI Studio/Azure OpenAI
  (ex. « gpt-4o ») et indiquer son **nom exact**, puis brancher opencode
  (`provider.azuretour.models`) et le bench.

## 3. Exécutions effectuées (log)

```
# 2026-08-29, tous status/erreurs conservés.
which gcloud az docker   ⇒ ok (versions §1)

# — Google Cloud auth (impossible, clé privée placeholder) :
gcloud auth activate-service-account --key-file=/root/.tour-vault/gcp-sa.json
#   ⇒ NON EXÉCUTÉ : le fichier clef n'est pas fourni (H1).

# — Azure : tentative d'authentification SP (trace partielle, secret non répété) :
az login --service-principal -u "$AZURE_CLIENT_ID" -p "$AZURE_CLIENT_SECRET" --tenant "$AZURE_TENANT_ID"
#   ⇒ exit=1 — ERROR: Unable to get authority configuration for
#   https://login.microsoftonline.com/a1b2c3d4-…‑ef1234567890

# — Vérification indépendante du tenant (réseau OK, donc erreur = tenant inexistant) :
curl -s -o /dev/null -w '%{http_code}' \
  https://login.microsoftonline.com/a1b2c3d4-e5f6-7890-abcd-ef1234567890/v2.0/.well-known/openid-configuration
#   ⇒ 400  {"error":"invalid_tenant","error_description":"AADSTS90002: Tenant
#      'a1b2c3d4-…' not found..."}   (témoin : endpoint générique → 200)

# — Validation des clés Gemini (les 2 vraies) :
curl -s -w '\nHTTP %{http_code}\n' \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key=$TOUR_KEY" \
  -d '{"contents":[{"parts":[{"text":"OK-TOUR"}]}]}'
#   ⇒ HTTP 200 (texte « OK-TOUR (projet 168611493705) »)

# — 29/08 2e vague : clés Azure OpenAI (ressource tourdecontrole) —
#   Authentification (clé1 et clé2) :
curl -s -o /dev/null -w '%{http_code}\n' \
  "https://tourdecontrole.openai.azure.com/openai/models?api-version=2024-10-21" \
  -H "api-key: $AZURE_OPENAI_KEY"
#   ⇒ 200 (catalogue ~200 modèles : gpt-4o, gpt-5.x, gpt-image…)

#   Chat via l'endpoint compatible v1 (modèle = nom de DÉPLOIEMENT) :
for m in gpt-4o gpt-4o-mini gpt-35-turbo gpt-5 gpt-4.1 chat test tour; do ...
#   ⇒ 404 DeploymentNotFound partout → AUCUN déploiement provisionné (H6).

# — Image de la Tour — contexte local : impossibilité technique —
dockerd --storage-driver=vfs --iptables=false --bridge=none          # OK (démon)
DOCKER_BUILDKIT=1 docker build --network=host -t tour-community:latest .
#   ⇒ échec buildkit : "operation not permitted" (bind-mount) ;
#      pas de CAP_SYS_ADMIN/NET_ADMIN dans ce bac à sable ⇒ on ne PEUT PAS
#      exécuter de conteneurs (ni docker run, ni kaniko local).
#   → CORRECTIF : build/push délégué à GitHub Actions (workflow public
#     docker-publish.yml → ghcr.io/fotsopatrick/tour-community:latest).

# — Publication via GitHub Actions — préparée mais PUSH BLOQUÉ (H5) :
git clone https://github.com/fotsopatrick/tour-community.git && cd tour-community
cp -r custom-addons/tour_community_{chat,braignak} …   # modules Gemini à jour
cp Dockerfile entrypoint.sh odoo.conf changements-gemini.md .
# .github/workflows/docker-publish.yml (push sur main + workflow_dispatch)
git commit -m "Déploiement cloud : Gemini, Dockerfile, workflow ghcr.io"   # 1e3a01e
git push origin main
#   ⇒ remote: Permission to fotsopatrick/tour-community.git denied → 403.
#      (token fine-grained sans Contents:write sur tour-community — H5)

# — opencode : fournisseurs câblés —
opencode.jsonc  → provider.azuretour (apiKey+baseURL https://…/openai/v1,
                  npm @ai-sdk/openai-compatible, modèles gpt-4o/gpt-4o-mini)
                  + provider.google ({env:GOOGLE_API_KEY}) ; mcp conservé.
#   → redémarrer opencode pour prise en compte.

# — 29/08 16h00 — IMAGE PUBLIÉE via relais (dépôt alice, sans token tour) —
# .github/workflows/tour-publish.yml (alice) : context ./cloud/tour,
#   push ghcr.io/fotsopatrick/tour-community:{latest,sha}.
# run 33261517182 (da54e0d) #   échec build : "pip3 … externally-managed-environment"
#   (PEP 668, Debian trixie d'Odoo 18) → Dockerfile : pip3 --break-system-packages.
# run 33261807933 (5a29035) #   SUCCESS.
# Vérif publique (dance token ghcr, sans auth) :
#   GET /v2/fotsopatrick/tour-community/manifests/latest ⇒ HTTP 200
#   tags/list ⇒ latest + 5a29035ddace61603084b5491d05107988b6d10d
# Le token « tour community » fourni après coup : push 403 aussi (H5 partiel).

# — 29/08 16h10 — deuxième ressource Azure retrouvée (AI Foundry) —
# clé kamdemorel-4813 : GET /openai/models?api-version=2024-10-21 ⇒ 200 (auth OK).
# Chat v1 : 404 DeploymentNotFound sur ~10 noms usuels ; /openai/deployments ⇒ 404.
# Énumération Foundry (/api/projects/…) : chemins 400/404 (scope API non exposé).
#   ⇒ H6 inchangé : besoin du NOM DE DÉPLOIEMENT exact (console AI Foundry → Deployments).

# — Préparation CLI :
export PATH="$PATH:/root/google-cloud-sdk/bin"
docker info >/dev/null   # démon dockerd non démarré → `systemctl start docker` si besoin
```

## 4. Enchaînement rejouable (une fois H1–H6 levés)

```bash
export PATH="$PATH:/root/google-cloud-sdk/bin"
# — config Google Cloud
gcloud auth activate-service-account --key-file=/root/.tour-vault/gcp-sa.json
gcloud config set project tour-community-2026
export GEMINI_API_KEY="AQ.Ab8RN6KbnU…"   # clé TOUR fournie par l'utilisateur

# 4.1 Tour → Cloud Run (+ Cloud SQL)   [collecter les sorties dans §6]
bash /workspace/deploiement-cloud/tour/deploy-tour-cloudrun.sh tour-community-2026 us-central1

# 4.2 ALICE → Cloud Run (cerveau Gemini)   [collecter les sorties dans §6]
bash /workspace/deploiement-cloud/alice/deploy-alice-cloudrun.sh tour-community-2026 us-central1

# 4.3 ALICE → Azure ACI (même image). Pipeline sans Docker-Hub :
#     on construit avec le docker local PUIS on pousse vers un registre ACR
#     (suite : az acr create/login + docker build + docker push).
bash /workspace/deploiement-cloud/alice/deploy-alice-aci.sh alice-rg eastus2   # attend un SP opérationnel

# 4.4 TOUR → Azure ACI (runbook complet, image ghcr.io) — [H3 + image publiée]
bash /workspace/deploiement-cloud/tour/deploy-tour-aci.sh
```

### 4.3 bis — publication de l'image ALICE sur le cloud Azure (non-Docker-Hub)

```bash
az acr create -n acralice${SU} -g alice-rg --sku Basic --admin-enabled false
az acr login -n acralice${SU}
docker build -t acralice${SU}.azurecr.io/alice:latest /workspace/deploiement-cloud/alice
docker push acralice${SU}.azurecr.io/alice:latest
az container create -g alice-rg --name alice-gate --image acralice${SU}.azurecr.io/alice:latest \
  --ports 8000 --cpu 1 --memory 1 --os-type Linux --dns-name-label "alice${SU}" \
  --environment-variables ALICE_BRAIN_URL=https://generativelanguage.googleapis.com/v1beta/openai/chat/completions \
                       ALICE_BRAIN_MODEL=gemini-3.5-flash \
  --secure-environment-variables ALICE_BRAIN_API_KEY="$GEMINI_API_KEY"
```

## 5. Bench comparatif (une fois les instancies en ligne)

```bash
python3 /workspace/deploiement-cloud/alice/bench_perf.py \
  http://192.168.1.61:8000 \
  <URL-Cloud-Run-alice>    # e.g. https://alice-abc123-uc.a.run.app
# puis (2e passage en 3 arg) :
python3 /workspace/deploiement-cloud/alice/bench_perf.py \
  http://192.168.1.61:8000 http://aliceXXX.eastus2.azurecontainer.io:8000 20
```

## 6. Sorties attendues (à recopier après déploiement)

| Service | URL | p50 ack | p50 completion | coût/1k req |
|---|---|---|---|---|
| Tour Cloud Run | _à remplir_ | — | — | — |
| ALICE Cloud Run | _à remplir_ | — | — | — |
| ALICE ACI (Azure) | _à remplir_ | — | — | — |
| ALICE local (Qwen) | http://192.168.1.61:8000 | — | — | 0 € |

## 7. Checklist de validation

- [ ] `gcloud auth list` montre le service account (H1)
- [ ] `gcloud billing projects describe tour-community-2026` → billingEnabled=true (H2)
- [ ] `az account show` retourne le SP (H3)
- [ ] Tour : `curl -L <URL>/web/login` → 200 ; Chloé crée une app (tool_call `construire_app`, `max_tokens=12288`)
- [ ] ALICE Cloud : `curl <URL>/health` → ok ; `bench_perf.py` termine sans erreur
- [ ] ACI : `az container show` → ProvisioningState=Succeeded ; health 200
- [ ] Ce circuit est à jour (chaque commande exécutée est loggée ici)