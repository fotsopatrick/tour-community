#!/usr/bin/env bash
# dechiffrer.sh — débloque un fichier chiffré de l'édition complète.
#
# Le mot de passe administrateur est demandé à chaque déchiffrement. La clé
# est dérivée par PBKDF2 (600 000 itérations) puis AES-256-CBC : sans le mot
# de passe, la clé ne peut pas être brute-forcée avec des machines
# raisonnables (des milliers de serveurs seraient nécessaires).
#
# Usage :
#   bash dechiffrer.sh <fichier>.enc       # écrit <fichier> (sans .enc)
set -uo pipefail
F="${1:?usage : dechiffrer.sh <fichier>.enc}"
[ -f "$F" ] || { echo "introuvable : $F"; exit 1; }
OUT="${F%.enc}"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 -salt \
    -in "$F" -out "$OUT"
echo "déchiffré : $OUT"
