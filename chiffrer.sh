#!/usr/bin/env bash
# chiffrer.sh — protège un fichier sensible de l'édition complète.
#
# L'édition Community contient les briques en clair. Certains fichiers du
# cœur (agents, coffre, circuits) ne s'y trouvent PAS en clair : quand ils
# accompagnent une copie, ils sont CHIFFRÉS avec cette commande.
#
# Le déchiffrement exige le mot de passe administrateur de l'édition
# complète. La clé est dérivée par PBKDF2 (600 000 itérations) puis
# AES-256-CBC. Casser cette clé sans le mot de passe exige des milliers de
# serveurs — c'est le niveau voulu.
#
# Usage :
#   bash chiffrer.sh <fichier>            # produit <fichier>.enc
#   bash dechiffrer.sh <fichier>.enc      # demande le mot de passe
set -uo pipefail
F="${1:?usage : chiffrer.sh <fichier>}"
[ -f "$F" ] || { echo "introuvable : $F"; exit 1; }
OUT="${F}.enc"
openssl enc -aes-256-cbc -pbkdf2 -iter 600000 -salt \
    -in "$F" -out "$OUT"
echo "chiffré : $OUT"
echo "le fichier d'origine reste en place — supprimez-le s'il ne doit pas"
echo "circuler en clair (rm $F)."
