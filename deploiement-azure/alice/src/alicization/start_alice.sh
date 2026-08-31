#!/usr/bin/env bash
# start_alice.sh — lance Alice et ses voisins locaux.
#
#   bash start_alice.sh [dossier_racine]
#   dossier_racine par défaut : /home/alice
#   (il contient alicization/, chat_backend.py, carte-vivante/, donjon-vr/)
set -uo pipefail

BASE="${1:-/home/alice}"
LOG_DIR="${LOG_DIR:-$BASE/alicization/logs}"
mkdir -p "$LOG_DIR"

service_ou_vit() {
  local pid
  pid=$(pgrep -f -- "$1" | head -1)
  [ -n "$pid" ]
}

lancer() {
  local nom="$1" pattern="$2" cwd="$3"
  shift 3
  if service_ou_vit "$pattern"; then
    echo "  ✅ $nom déjà lancé"
    return
  fi
  export PYTHONPATH="$cwd:$PYTHONPATH"
  ( cd "$cwd" && setsid nohup "$@" >>"$LOG_DIR/$nom.log" 2>&1 </dev/null & )
  echo "  🚀 $nom lancé  (log : $LOG_DIR/$nom.log)"
}

echo "Alice ↕ voisins locaux (base : $BASE)"

if [ -f "$BASE/chat_backend.py" ]; then
  lancer chat-backend "chat_backend.py" "$BASE" /home/alice/alicization-venv/bin/python "$BASE/chat_backend.py"
else
  echo "  ⚠  $BASE/chat_backend.py absent → API Alice non lancée"
fi

if [ -d "$BASE/carte-vivante" ]; then
  lancer carte "http.server 8100" "$BASE/carte-vivante" python3 -m http.server 8100 --bind 0.0.0.0
else
  echo "  ⚠  $BASE/carte-vivante absent → carte non servie"
fi

if [ -d "$BASE/donjon-vr" ]; then
  lancer donjon "http.server 8099" "$BASE/donjon-vr" python3 -m http.server 8099 --bind 127.0.0.1
else
  echo "  ⚠  $BASE/donjon-vr absent → Donjon non lancé"
fi

sleep 1
echo "---- État ----"
curl -s -o /dev/null -w "  API Alice 8002    : HTTP %{http_code}\n" http://127.0.0.1:8002/health 2>/dev/null || echo "  API Alice 8002    : fermé"
for port in 8100 8099; do
  if (exec 3<>/dev/tcp/127.0.0.1/$port) 2>/dev/null; then
    echo "  Port $port        : ouvert"
    exec 3>&- 3<&-
  else
    echo "  Port $port        : fermé"
  fi
done