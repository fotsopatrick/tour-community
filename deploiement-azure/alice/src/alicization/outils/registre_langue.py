#!/usr/bin/env python3
# /home/orel/alicization/outils/registre_langue.py
# Registres de langue : familier / courant / soutenu — extraits des 3 livres.
#
# Fonctions :
#   detecter_registre(phrase)   -> "familier", "courant" ou "soutenu"
#   traduire_vers_courant(mot)  -> la version courante d'un mot familier
#   synonyme_soutenu(mot)       -> un synonyme soutenu d'un mot courant
#   traduire_vers_soutenu(mot)  -> d'un mot familier à son équivalent soutenu
#   synonyme_familier(mot)      -> un synonyme familier d'un mot courant

import re

REGISTRES = {
    "familier": {
        "manger": ["bouffer", "grailler"],
        "dormir": ["pioncer", "roupiller"],
        "rire": ["rigoler", "se marrer"],
        "parler": ["jacter", "causer"],
        "avoir peur": ["avoir la frousse", "avoir la trouille"],
    },
    "courant": {
        "manger": ["manger", "se nourrir"],
        "dormir": ["dormir"],
        "rire": ["rire"],
        "parler": ["parler", "prendre la parole"],
        "avoir peur": ["avoir peur"],
    },
    "soutenu": {
        "manger": ["se sustenter", "se restaurer"],
        "dormir": ["faire un somme", "se reposer"],
        "rire": ["laisser éclater sa joie"],
        "parler": ["proférer", "s'exprimer"],
        "avoir peur": ["être épouvanté", "être effrayé"],
    }
}

# Ordre de détection : les registres marqués d'abord, le courant en filet de sécurité.
_ORDRE_DETECTION = ("familier", "soutenu", "courant")


def _normaliser(texte):
    """Minuscules, espaces multiples collés, sans ponctuation de bout de ligne."""
    return re.sub(r"\s+", " ", texte.lower().strip())


_ACCENTS = str.maketrans("àâäéèêëîïôöûüùç", "aaaeeeeiioouuuc")


def _sans_accents(texte):
    """Enlève les accents (é→e, à→a...)."""
    return texte.translate(_ACCENTS)


_SUFFIXES = ("ent", "ers", "er", "irs", "ir", "res", "re", "es", "se", "s", "e")


def _base(mot):
    """Racine d'un mot sans accent ni terminaison (bouffer→bouff, mangée→mang)."""
    m = _sans_accents(mot.lower())
    for suffixe in _SUFFIXES:
        if len(m) - len(suffixe) >= 3 and m.endswith(suffixe):
            m = m[:-len(suffixe)]
            break
    return m


def traduire_vers_courant(mot_familier):
    """Traduit un mot familier vers son équivalent courant."""
    cible = _normaliser(mot_familier)
    for courant, variantes in REGISTRES["familier"].items():
        if cible in [_normaliser(v) for v in variantes]:
            return courant
    return mot_familier  # si non trouvé


def synonyme_soutenu(mot_courant):
    """Trouve un synonyme soutenu pour un mot courant."""
    cible = _normaliser(mot_courant)
    for courant, variantes in REGISTRES["soutenu"].items():
        if cible in [_normaliser(v) for v in variantes] or cible == _normaliser(courant):
            return variantes[0]
    return mot_courant


def traduire_vers_soutenu(mot_familier):
    """D'un mot familier à son équivalent soutenu (via le courant)."""
    courant = traduire_vers_courant(mot_familier)
    return synonyme_soutenu(courant)


def synonyme_familier(mot_courant):
    """Trouve un synonyme familier pour un mot courant."""
    cible = _normaliser(mot_courant)
    for courant, variantes in REGISTRES["familier"].items():
        if cible == _normaliser(courant) or cible in [_normaliser(v) for v in variantes]:
            return variantes[0]
    return mot_courant


def detecter_registre(phrase):
    """
    Détecte si la phrase est familière, courante ou soutenue.
    Compare les RACINES des mots (sans accent ni terminaison) pour tolérer la
    conjugaison : « j'ai bouffé » et « bouffer » ont la même racine.
    """
    p = _normaliser(phrase)
    if not p:
        return "courant"
    mots_phrase = {_base(m) for m in re.findall(r"\w+", p)}
    for registre in _ORDRE_DETECTION:
        for variantes in REGISTRES[registre].values():
            for v in variantes:
                racines_variante = {_base(m) for m in re.findall(r"\w+", _normaliser(v))}
                if racines_variante and mots_phrase & racines_variante:
                    return registre
    return "courant"  # par défaut