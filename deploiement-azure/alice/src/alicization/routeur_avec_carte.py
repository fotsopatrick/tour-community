# -*- coding: utf-8 -*-
"""
ROUTEUR — avec CARTE VIVANTE
Il regarde la carte avant de réfléchir !
Comme Raphaël : d'abord la carte, ensuite le modèle.
"""

from adaptateur_carte import AdaptateurCarte
from memory import Memoire
import re


class Routeur:
    """
    Le routeur est comme un grand chef d'orchestre.
    Il regarde la carte avant de décider.
    """

    def __init__(self, chemin_db="state/alicization.db", chemin_carte="carte-vivante/cartes.json"):
        self.carte = AdaptateurCarte(chemin_carte)
        self.memoire = Memoire(chemin_db)

    def router(self, requete):
        """Décide quoi faire avec la requête."""

        # 1. NETTOYER la requête (enlever les mots inutiles)
        requete_propre = self._nettoyer(requete)

        # 2. CONSULTER LA CARTE (priorité absolue !)
        info_carte = self._consulter_carte(requete_propre)

        if info_carte:
            return {
                "decision": "circuit",
                "source": "carte",
                "info": info_carte,
                "message": f"Je sais déjà ! C'est sur la carte : {info_carte['type']}"
            }

        # 3. CONSULTER LA MÉMOIRE (les procédures apprises)
        info_memoire = self.memoire.chercher(requete_propre)

        if info_memoire:
            return {
                "decision": "circuit",
                "source": "memoire",
                "info": info_memoire,
                "message": "Je me souviens ! J'ai appris ça avant."
            }

        # 4. APPELER LE MODÈLE (apprendre quelque chose de nouveau)
        return {
            "decision": "modele",
            "source": "nouveau",
            "message": "Je ne connais pas ça. Je vais apprendre."
        }

    def _consulter_carte(self, requete):
        """
        Regarde dans la carte si quelque chose correspond à la requête.
        La carte peut contenir : circuits, outils, processus, acteurs, demandes.
        """
        mots_requete = requete.split()

        # 1. Chercher un CIRCUIT connu
        #    (un chemin rejouable qui fait ce que demande l'utilisateur)
        circuits = self.carte.get_par_type("circuit")
        for circuit in circuits:
            mots_cles = circuit.get("mots_cles", [])
            # Vérifier si un mot-clé est dans la requête OU si un mot de la requête est un mot-clé
            for mc in mots_cles:
                if mc in requete or mc in mots_requete:
                    return {"type": "circuit", "data": circuit}

        # 2. Chercher un OUTIL disponible
        #    (une opération qui peut être utilisée)
        outils = self.carte.get_par_type("outil")
        for outil in outils:
            nom_outil = outil.get("nom", "").lower()
            if nom_outil and (nom_outil in requete or nom_outil in mots_requete):
                return {"type": "outil", "data": outil}

        # 3. Chercher un PROCESSUS existant
        #    (un flux de travail déjà défini)
        processus = self.carte.get_par_type("processus")
        for process in processus:
            mots_cles = process.get("mots_cles", [])
            for mc in mots_cles:
                if mc in requete or mc in mots_requete:
                    return {"type": "processus", "data": process}

        # 4. Chercher un ACTEUR qui peut répondre
        #    (un agent, un humain, une machine)
        acteurs = self.carte.get_par_type("agent")
        acteurs += self.carte.get_par_type("patron")
        acteurs += self.carte.get_par_type("moteur")
        for acteur in acteurs:
            # Vérifier si la compétence ou le nom correspond
            if acteur.get("competence") and acteur.get("competence").lower() in requete:
                return {"type": "acteur", "data": acteur}
            if acteur.get("nom") and acteur.get("nom").lower() in requete:
                return {"type": "acteur", "data": acteur}

        # 5. Chercher une DEMANDE en cours
        #    (une mission active qui correspond)
        demandes = self.carte.get_par_type("demande")
        for demande in demandes:
            mots_cles = demande.get("mots_cles", [])
            for mc in mots_cles:
                if mc in requete or mc in mots_requete:
                    return {"type": "demande", "data": demande}
            # Aussi chercher dans le détail
            detail = demande.get("detail", "").lower()
            if detail and requete in detail:
                return {"type": "demande", "data": demande}

        # Rien trouvé sur la carte
        return None

    def _nettoyer(self, texte):
        """Enlève les mots inutiles, garde les underscores et tirets pour les identifiants."""
        mots_inutiles = ["peux-tu", "s'il te plaît", "pourrais-tu", "est-ce que"]
        for mot in mots_inutiles:
            texte = texte.replace(mot, "")
        # Garder les underscores et tirets pour les noms d'outils/identifiants
        texte = re.sub(r'[^a-zA-Z0-9\sàâäéèêëïîôùûüÿçœæ_-]', '', texte)
        return texte.strip().lower()

    def carte_stats(self):
        """Retourne un résumé de ce que contient la carte."""
        return self.carte.stats()