# Tour de contrôle — Community : image Odoo 18 + serveur WebMCP
# Cible : Cloud Run (avec proxy Cloud SQL injecte par --add-cloudsql-instances)
# Build : gcloud builds submit --tag gcr.io/PROJECT/tour-community
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Depot systeme necessaire a psycopg2, lxml, pillow, python-ldap
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
        git \
        curl \
        postgresql-client \
        libpq-dev \
        libldap2-dev \
        libsasl2-dev \
        libssl-dev \
        libjpeg-dev \
        zlib1g-dev \
        libfreetype6-dev \
        liblcms2-dev \
        libwebp-dev \
        libxml2-dev \
        libxslt1-dev \
        libffi-dev \
        fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/odoo

# Le code source Odoo 18 (Community)
RUN git clone --depth 1 --branch 18.0 https://github.com/odoo/odoo.git /opt/odoo

# Les briques libres de la Tour (custom-addons) — contexte = racine du depot
COPY custom-addons/ /opt/odoo/custom-addons/

# Le point d'entree (init base + lancement) et le modele de releve de carte
COPY deploy/entrypoint.sh /opt/odoo/entrypoint.sh
RUN chmod +x /opt/odoo/entrypoint.sh

# Dependances Python d'Odoo + les deux librairies utiles a la Tour
RUN pip install --upgrade pip \
    && pip install -r /opt/odoo/requirements.txt \
    && pip install psycopg2-binary requests mcp

# Stockage d'apps construites par Chloe + donnees Odoo (a garder leger/persistant cote Cloud)
RUN mkdir -p /var/lib/odoo/community-apps

EXPOSE 8080

ENTRYPOINT ["/opt/odoo/entrypoint.sh"]