#!/bin/sh
# Tour de controle — point d'entree de l'image.
#
# Deux temps :
#   1. Init : cree/met a jour la base avec les modules (sans frais si la base
#      existe deja : les modules installes sont ignores).
#   2. Serveur : odoo ecoute sur $PORT (variable injectee par Cloud Run).
#
# Toutes les valeurs passent par l'environnement (aucun secret en dur).
set -e

export PGHOST="${PGHOST:-127.0.0.1}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-odoo}"
export PGPASSWORD="${PGPASSWORD:-}"
export PGDATABASE="${PGDATABASE:-tour_prod}"
export HTTP_PORT="${PORT:-8069}"
export ODOO_ADMIN_PASSWD="${ODOO_ADMIN_PASSWD:-admin}"

# Les modules Community installables. tour_webmcp depend des agents et des
# briques ; ne rien retirer sans lire les manifests.
MODULES="${ODOO_INIT_MODULES:-base,web,mail,auth_signup,project,tour_actus,tour_apprentissage,tour_community_braignak,tour_community_chat,tour_community_theme,tour_condense_community,tour_cookie_secure,tour_cv,tour_dashboard,tour_messages,tour_nouveautes,tour_projets,tour_rappels,tour_rate_login,tour_recette,tour_reponses,tour_retours,tour_sauvegardes,tour_vault,tour_webapps,tour_webmcp}"

COMMON="\
 --addons-path=/opt/odoo/addons,/opt/odoo/odoo/addons,/opt/odoo/custom-addons \
 --db_host=${PGHOST} --db_port=${PGPORT} --db_user=${PGUSER} \
 --db_password=${PGPASSWORD} --database=${PGDATABASE} \
 --admin_passwd=${ODOO_ADMIN_PASSWD} --http-port=${HTTP_PORT} \
 --data-dir=/tmp/odoo-data --without-demo=all"

echo "[entrypoint] init de la base ${PGDATABASE} (modules : ${MODULES})"
python3 odoo-bin ${COMMON} --stop-after-init --init="${MODULES}"

echo "[entrypoint] demarrage du serveur sur le port ${HTTP_PORT}"
exec python3 odoo-bin ${COMMON}