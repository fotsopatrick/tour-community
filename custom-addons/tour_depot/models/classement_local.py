# -*- coding: utf-8 -*-
"""Ranger les notes sans appeler d'intelligence artificielle.

Pourquoi ce fichier existe. Le rangeur du Dépôt posait une question à un
modèle toutes les 30 minutes, pour dix notes. Sur vingt tours clientes, ça fait
près de dix mille appels par jour, payés par le propriétaire. C'est le seul
coût qui **grandit avec le succès** — donc le seul qui puisse rendre l'offre
perdante.

La règle qui a été posée : **l'IA sert quand la réponse dépend du sens.**
Partout ailleurs, un algorithme public fait mieux — gratuitement,
instantanément, et surtout de façon *reproductible* : un classement par IA
change d'avis d'un jour à l'autre, pas une distance de Jaccard.

Ce que fait ce fichier, en trois briques, toutes en Python standard (aucune
bibliothèque à installer, donc aucune image à reconstruire) :

1. **Les doublons** — distance de Jaccard sur les mots normalisés. Deux notes
   qui partagent la même moitié de vocabulaire disent la même chose.
2. **Le classement** — un Bayes naïf multinomial qui apprend depuis les notes
   **déjà rangées par le modèle**. C'est la bonne façon d'utiliser un grand
   modèle : comme **professeur**, pas comme ouvrier.
3. **Le résumé** — extraction de la première phrase porteuse. Pas de
   reformulation : pour un aperçu de liste, la vraie phrase de l'auteur vaut
   mieux qu'une paraphrase.

Et une garantie, sans laquelle rien de tout ça ne devrait être branché :
**le classement local ne prend la main que s'il a fait ses preuves.** On mesure
son accord avec l'IA par validation croisée sur les notes existantes ; sous le
seuil, il se tait et laisse la main. Une économie payée par une régression
n'est pas une économie.
"""
import math
import re
import unicodedata

# Mots trop fréquents pour distinguer quoi que ce soit. Liste volontairement
# courte : un mot vide de trop, et on perd un signal utile.
VIDES = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "l", "et", "ou",
    "a", "au", "aux", "en", "dans", "sur", "pour", "par", "avec", "sans",
    "ce", "cet", "cette", "ces", "il", "elle", "on", "je", "tu", "nous",
    "vous", "ils", "elles", "que", "qui", "quoi", "dont", "est", "sont",
    "etre", "avoir", "fait", "faire", "plus", "moins", "tres", "pas", "ne",
    "se", "sa", "son", "ses", "mon", "ma", "mes", "y", "s", "c", "n", "je",
    "the", "and", "for", "with", "this", "that",
}

MOT = re.compile(r"[a-z0-9]+")


def normaliser(texte):
    """Minuscules, sans accents, sans ponctuation — la base commune."""
    if not texte:
        return ""
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return texte.lower()


def mots(texte, garder_vides=False):
    jetons = MOT.findall(normaliser(texte))
    if garder_vides:
        return jetons
    return [j for j in jetons if len(j) > 2 and j not in VIDES]


# ---------------------------------------------------------------- doublons
def similarite(texte_a, texte_b):
    """Jaccard : la part de vocabulaire commune. Entre 0 et 1.

    Choisi plutôt qu'une distance d'édition parce qu'on cherche des notes qui
    *redisent la même chose*, pas des textes identiques au caractère près —
    quelqu'un qui renote une idée trois semaines plus tard ne la réécrit pas
    mot pour mot.
    """
    a, b = set(mots(texte_a)), set(mots(texte_b))
    if not a or not b:
        return 0.0
    commun = len(a & b)
    return commun / float(len(a | b))


def chercher_doublon(texte, candidats, seuil=0.55):
    """Rend (id, score) du meilleur candidat au-dessus du seuil, sinon None.

    `candidats` : liste de (id, texte).
    """
    meilleur, score_max = None, 0.0
    for cid, ctexte in candidats:
        s = similarite(texte, ctexte)
        if s > score_max:
            meilleur, score_max = cid, s
    if meilleur is not None and score_max >= seuil:
        return meilleur, score_max
    return None


# --------------------------------------------------------------- résumé
def resumer(texte, longueur=180):
    """La première phrase qui porte de l'information, coupée proprement.

    Volontairement bête : un résumé de liste sert à reconnaître une note d'un
    coup d'œil. La reformulation, elle, coûte un appel — et n'aide pas.
    """
    if not texte:
        return ""
    plat = re.sub(r"\s+", " ", texte).strip()
    for phrase in re.split(r"(?<=[.!?])\s+", plat):
        if len(mots(phrase)) >= 3:
            return phrase[:longueur].strip()
    return plat[:longueur].strip()


# ------------------------------------------------------------- classement
class ClassifieurBayes(object):
    """Bayes naïf multinomial, en Python standard.

    Assez pour ce travail : classer un texte court dans huit catégories à
    partir de quelques dizaines d'exemples. Ce n'est pas de l'apprentissage
    profond, et c'est exactement le point — ça tient en cent lignes, ça
    s'explique, et ça donne toujours la même réponse.
    """

    def __init__(self):
        self.categories = {}      # catégorie -> nombre de documents
        self.frequences = {}      # catégorie -> {mot: compte}
        self.totaux = {}          # catégorie -> nombre total de mots
        self.vocabulaire = set()
        self.nb_documents = 0

    def apprendre(self, texte, categorie):
        # On compte chaque mot UNE fois par note, pas ses répétitions. Sans
        # ça, une note bavarde pèse plus lourd que dix notes courtes, et la
        # catégorie qui contient le moins de mots finit par gagner sur tous
        # les mots inconnus — c'est le défaut mesuré le 26/07 (27 % d'accord).
        jetons = set(mots(texte))
        if not jetons:
            return
        self.nb_documents += 1
        self.categories[categorie] = self.categories.get(categorie, 0) + 1
        freq = self.frequences.setdefault(categorie, {})
        for j in jetons:
            freq[j] = freq.get(j, 0) + 1
            self.vocabulaire.add(j)
        self.totaux[categorie] = self.totaux.get(categorie, 0) + len(jetons)

    def predire(self, texte):
        """Rend (catégorie, confiance) — la confiance est l'écart au second.

        On ne rend pas une probabilité : elle serait fausse (Bayes naïf est
        mal calibré) et donnerait une fausse assurance. L'écart entre le
        premier et le second, lui, dit quelque chose d'utile : si les deux
        meilleures catégories sont au coude à coude, il ne faut pas trancher.
        """
        jetons = list(set(mots(texte)))
        if not jetons or not self.nb_documents:
            return None, 0.0

        # Refuser de répondre quand on n'a rien reconnu. Sans ce garde-fou, le
        # classement se joue uniquement sur le lissage, et c'est la plus petite
        # catégorie qui l'emporte — une réponse tirée au sort, présentée avec
        # le même aplomb qu'une vraie. Mieux vaut se taire et laisser l'IA.
        connus = [j for j in jetons if j in self.vocabulaire]
        if len(connus) < max(1, len(jetons) // 4):
            return None, 0.0

        taille_vocab = len(self.vocabulaire) or 1
        scores = []
        for cat, n_docs in self.categories.items():
            # Log-probabilité, pour ne pas voir les produits tomber à zéro.
            score = math.log(n_docs / float(self.nb_documents))
            freq = self.frequences.get(cat, {})
            total = self.totaux.get(cat, 0)
            for j in jetons:
                # Lissage de Laplace : un mot jamais vu ne doit pas annuler
                # toute la catégorie.
                score += math.log((freq.get(j, 0) + 1.0) / (total + taille_vocab))
            scores.append((score, cat))
        if not scores:
            return None, 0.0
        scores.sort(reverse=True)
        meilleur = scores[0]
        if len(scores) == 1:
            return meilleur[1], 1.0
        # Écart normalisé par la longueur du texte : sans ça, un texte long
        # aurait mécaniquement un écart plus grand.
        ecart = (meilleur[0] - scores[1][0]) / float(len(jetons))
        return meilleur[1], max(0.0, min(1.0, ecart))


def entrainer(exemples):
    """`exemples` : liste de (texte, catégorie)."""
    c = ClassifieurBayes()
    for texte, categorie in exemples:
        if texte and categorie:
            c.apprendre(texte, categorie)
    return c


def evaluer(exemples, minimum=12, seuil_confiance=0.02):
    """Validation croisée « un contre tous ». Rend (justesse, couverture, n).

    **Le choix de mesure, et il est décisif.** On ne mesure PAS « combien de
    notes il classe correctement sur le total » : un refus n'est pas une
    erreur, c'est l'IA qui reprend la main, et rien n'est perdu. Ce qui doit
    autoriser la bascule, c'est : *quand il répond, a-t-il raison ?*

    - **justesse** = bonnes réponses / réponses données. C'est elle qui protège
      de la régression.
    - **couverture** = réponses données / notes. C'est elle qui dit si
      l'économie est réelle : un classifieur juste à 100 % mais qui répond une
      fois sur vingt ne fait économiser rien.

    Mesurer la justesse seule ferait basculer un classifieur muet ; mesurer la
    couverture seule ferait basculer un bavard qui se trompe. Il faut les deux.
    """
    exemples = [(t, c) for t, c in exemples if t and c]
    if len(exemples) < minimum:
        return 0.0, 0.0, len(exemples)
    bons = repondus = 0
    for i in range(len(exemples)):
        reste = exemples[:i] + exemples[i + 1:]
        modele = entrainer(reste)
        prediction, confiance = modele.predire(exemples[i][0])
        if prediction is None or confiance < seuil_confiance:
            continue
        repondus += 1
        if prediction == exemples[i][1]:
            bons += 1
    if not repondus:
        return 0.0, 0.0, len(exemples)
    return (bons / float(repondus),
            repondus / float(len(exemples)),
            len(exemples))
