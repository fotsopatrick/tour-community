#!/usr/bin/env bash
# install_alice.sh — installe tout ce qu'il faut pour faire tourner Alice
# sur un Linux vierge (Debian / Ubuntu).
#
# Usage :
#   sudo bash install_alice.sh /chemin/vers/alicization
# (le chemin est optionnel ; par défaut : /home/alice/alicization)
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

PROJET="${1:-/home/alice/alicization}"

echo "==> [1/4] Paquets système"
apt-get update -y
apt-get install -y --no-install-recommends \
  tesseract-ocr imagemagick python3 python3-pip git

echo "==> [2/4] Dépendances Python"
# Debian/Ubuntu récents bloquent pip systèmes (PEP 668) : on assume l'external management.
python3 -m pip install --break-system-packages --upgrade pip 2>/dev/null || true
python3 -m pip install --break-system-packages \
  flask flask-cors requests numpy gymnasium

echo "==> [3/4] Vérification des outils"
python3 - <<'PY'
import flask, flask_cors, requests, numpy, gymnasium
print("  python : flask, flask-cors, requests, numpy, gymnasium OK")
PY
if command -v tesseract >/dev/null 2>&1; then
  echo "  tesseract : OK ($(tesseract --version | head -1))"
else
  echo "  tesseract : MANQUANT" >&2
fi
if command -v convert >/dev/null 2>&1; then
  echo "  imagemagick : OK"
else
  echo "  imagemagick : MANQUANT" >&2
fi

if [ -d "$PROJET/tests" ]; then
  echo "==> [4/4] Self-check du projet ($PROJET)"
  ( cd "$PROJET" && python3 -m unittest discover -s tests -p "test_*.py" -v ) \
    || echo "  ⚠  Des tests échouent : voir la sortie ci-dessus."
else
  echo "==> [4/4] Pas de dossier tests (le projet n'est pas encore copié) —"
  echo "        on s'arrête ici. Copie le projet puis relance."
fi

echo "Installation terminée."
echo "Lancement :  bash $PROJET/start_alice.sh"