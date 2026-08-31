# =====================================================================
# ALICE déployée (gate + routeur + ingest + UI) — conteneur unique.
# Code pris dans ./src (copie à jour du code d'Alice => dépôt alice).
# Cerveau : Azure OpenAI (deployment ALICE_BRAIN_DEPLOYMENT) par défaut
# dans les clouds ; locale, la même image peut pointer Qwen ou Gemini.
# Mémoire longue : SQLite éphémère ou PostgreSQL persistant (ALICE_DB_URL),
# ce qui rend l'ingestion persistante sur Cloud SQL / Azure PostgreSQL.
# =====================================================================
FROM python:3.12-slim

# NOTE (29/08) : apt supprimé du build — le DNS de la machine de build est
# instable pour libapt. Conséquence : pdftotext (poppler-utils) absent →
# l'ingest PDF répond une erreur claire ; l'ingest .txt/.md/URL fonctionne.
# Réintroduire ce bloc quand le build DNS est fiable.

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && pip install --no-cache-dir psycopg2-binary requests

# Code : alicization (flat), gate, MCP.
COPY src/alicization /app/alicization
COPY src/alice_gate.py /app/alice_gate.py
COPY src/mcp_alice.py /app/mcp_alice.py

# Cerveau par défaut : Azure OpenAI (tourdecontrole, deployment gpt-5-mini).
# En local : ALICE_BRAIN_AZURE=0 + ALICE_BRAIN_URL/ALICE_BRAIN_API_KEY.
ENV ALICE_BRAIN_AZURE=1 \
    ALICE_BRAIN_BASE=https://tourdecontrole.openai.azure.com/ \
    ALICE_BRAIN_DEPLOYMENT=gpt-5-mini \
    ALICE_BRAIN_API_VERSION=2024-12-01-preview \
    ALICE_CARTE=/app/alicization/carte-vivante/cartes.json \
    ALICE_DB=/tmp/alice/state/alice.db \
    ALICE_CHUNK_SIZE=900 \
    ALICE_CHUNK_OVERLAP=120

# PORT est injecté par Cloud Run ; défaut 8000 (ACI).
EXPOSE 8000 8080
CMD ["python", "/app/alice_gate.py"]