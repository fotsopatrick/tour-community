#!/usr/bin/env python3
# /home/orel/alicization/outils/care_hacking.py
# Le care hacking : parler gentiment, prendre soin des gens.
#
# C'est la façon de parler d'Alice lorsqu'on est fatigué, perdu, content,
# ou agacé : elle détecte l'humeur, adapte son ton et ajoute des mots doux.
# Aucun appel externe : tout est local.

import re


def _normaliser(texte):
    """Minuscules, espaces multiples collés, ponctuation de bout retirée."""
    return re.sub(r"\s+", " ", texte.lower().strip())


_ACCENTS = str.maketrans("àâäéèêëîïôöûüùç", "aaaeeeeiioouuuc")


def _sans_accents(texte):
    """Enlève les accents (é→e, à→a...)."""
    return texte.translate(_ACCENTS)


# Le registre des humeurs qu'Alice sait reconnaître.
# Une humeur est détectée dès qu'un de ses indices apparaît dans la phrase.
_REGISTRE_HUMEURS = {
    "fatigue": ["fatigu", "epuise", "creve", "sommeil", "plus d energie", "pas envie", "lourd", "lasse", "vermine"],
    "perdu": ["perdu", "comprends pas", "comprend rien", "coince", "bloque", "comment faire", "ou est", "ou va", "je sais pas", "aucune idee"],
    "content": ["super", "genial", "bravo", "content", "heureux", "top", "merci", "fier", "youpi", "trop bien", "excellent", "parfait"],
    "frustre": ["marre", "enerve", "agace", "frustre", "sert a rien", "pff", "pas normal", "toujours pareil", "ca marche jamais"],
}


def detecter_humeur(texte):
    """Détecte l'humeur dans un texte : fatigue, perdu, content, frustre, neutre."""
    p = _sans_accents(_normaliser(texte))
    for humeur, indices in _REGISTRE_HUMEURS.items():
        for indice in indices:
            if indice in p:
                return humeur
    return "neutre"


# Le ton à adopter pour chaque humeur (et une petite phrase d'introduction).
_TONS = {
    "content": {
        "ton": "joyeux",
        "introduction": "Génial, ça me fait plaisir !",
        "vitesse": "rapide",
    },
    "perdu": {
        "ton": "guidant",
        "introduction": "Pas de panique, on avance pas à pas.",
        "vitesse": "lente",
    },
    "fatigue": {
        "ton": "calme",
        "introduction": "On y va tout doucement, pas besoin de se presser.",
        "vitesse": "lente",
    },
    "frustre": {
        "ton": "apaisant",
        "introduction": "Je comprends, c'est agaçant. Reprenons calmement.",
        "vitesse": "lente",
    },
    "neutre": {
        "ton": "naturel",
        "introduction": "",
        "vitesse": "normale",
    },
}


def adapter_ton(humeur):
    """Renvoie le ton à adopter pour une humeur donnée (dict ton/introduction/vitesse)."""
    return _TONS.get(humeur, _TONS["neutre"])


# Les petits mots gentils, un par humeur (le premier est choisi).
_PETITS_MOTS = {
    "content": ["Bravo, super travail !", "Je suis fier de toi !", "Tu assures !"],
    "perdu": ["Ne t'inquiète pas, je t'accompagne.", "Tu y es presque, encore un petit pas."],
    "fatigue": ["Prends ton temps.", "Repose-toi deux minutes si besoin."],
    "frustre": ["Respire, on va y arriver.", "C'est normal que ça coince parfois."],
    "neutre": [],
}


def ajouter_petits_mots(texte, humeur=None):
    """Ajoute un petit mot gentil à la fin (l'humeur est détectée si absente)."""
    if humeur is None:
        humeur = detecter_humeur(texte)
    mots = _PETITS_MOTS.get(humeur, [])
    if not mots:
        return texte.rstrip()
    return texte.rstrip() + " " + mots[0]


def envelopper(texte, reponse):
    """
    Réponse complète « care » : introduction adaptée à l'humeur + réponse + petit mot.
    C'est ce qu'Alice peut utiliser autour de ses réponses brutes.
    """
    humeur = detecter_humeur(texte)
    ton = adapter_ton(humeur)
    debut = ton["introduction"]
    message = reponse if not debut else debut + " " + reponse
    return ajouter_petits_mots(message, humeur)