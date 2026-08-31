# ============================================================
# ROUTEUR — le chef d'orchestre d'Alice
# Il consulte la carte, puis le carnet, puis le modèle.
# ============================================================

import re
import json
import time
import subprocess
import os
from pathlib import Path
from adaptateur_carte import AdaptateurCarte
from memory import Memoire

SEUIL_CONFIANCE = 0.6

# Mots génériques trop fréquents dans les requêtes : ils ne prouvent PAS
# que l'utilisateur vise un circuit précis (ex: « procédure », « créer »).
MOTS_GENERIQUES_CARTE = {
    "procedure", "procédure", "etapes", "etape", "operation", "opérations",
    "operation", "configurer", "configuration", "creer", "créer", "afficher",
    "liste", "lister", "trouver", "chercher", "regarder", "faire", "un",
    "une", "des", "les", "la", "le", "au", "aux", "pour", "sur", "de", "du",
}


def op_k7(x):
    """op_k7 : x * 3 + 7"""
    return x * 3 + 7


def op_m2(x):
    """op_m2 : x * 5 + 2"""
    return x * 5 + 2


def op_q9(x):
    """op_q9 : x * 2 + 11"""
    return x * 2 + 11


def op_r4(x):
    """op_r4 : x * 4 + 13"""
    return x * 4 + 13


def op_t1(x):
    """op_t1 : x * 7 - 3"""
    return x * 7 - 3


def op_v6(x):
    """op_v6 : x * 6 + 9"""
    return x * 6 + 9


def executer_action(commande, chemin_base="/home/alice"):
    """
    Exécute une commande shell simple dans un environnement sécurisé.
    Retourne la sortie stdout ou un message d'erreur.
    """
    commande = commande.strip()
    if not commande:
        return "Commande vide."

    # Sécurité : commandes autorisées
    commandes_autorisees = [
        "echo", "cat", "ls", "mkdir", "touch", "rm", "mv", "cp", "chmod", "chown",
        "head", "tail", "grep", "find", "wc", "sort", "uniq", "diff", "patch",
        "tar", "gzip", "gunzip", "make", "gcc", "clang", "python3", "bash",
        "wget", "curl", "git", "cmake", "autoconf", "automake", "ld", "ar", "as"
    ]

    mots = commande.split()
    if mots and mots[0] not in commandes_autorisees:
        return f"Commande non autorisée : {mots[0]}. Utilise une des : {', '.join(commandes_autorisees[:10])}..."

    # Sécurité : interdire les chemins dangereux
    if ".." in commande or "/etc/passwd" in commande or "/shadow" in commande or "sudo" in commande:
        return "Action interdite pour des raisons de sécurité."

    try:
        resultat = subprocess.run(
            commande,
            shell=True,
            cwd=chemin_base,
            capture_output=True,
            text=True,
            timeout=120
        )
        if resultat.stdout:
            return resultat.stdout.strip()
        elif resultat.stderr:
            return f"Erreur : {resultat.stderr.strip()}"
        else:
            return f"Commande exécutée avec succès : {commande}"
    except subprocess.TimeoutExpired:
        return "La commande a dépassé le temps autorisé."
    except Exception as e:
        return f"Erreur : {e}"


def call_model(messages, temperature=0.2, max_tokens=256):
    """
    Alice appelle son cerveau pour réfléchir.

    Trois cerveaux possibles (choisis par l'environnement) :
      - Qwen local (défaut)  : ALICE_BRAIN_URL http://host:8081/v1/chat/completions
        + clé Bearer optionnelle ;
      - Gemini (OpenAI-compatible) : ALICE_BRAIN_URL google + ALICE_BRAIN_API_KEY ;
      - Azure OpenAI          : ALICE_BRAIN_AZURE=1, ALICE_BRAIN_BASE (resource),
        ALICE_BRAIN_DEPLOYMENT (nom du deployment) et ALICE_BRAIN_API_KEY
        (en-tête 'api-key', pas Bearer).
    """
    import urllib.request
    import os

    azure = os.environ.get("ALICE_BRAIN_AZURE") == "1"
    cle = os.environ.get("ALICE_BRAIN_API_KEY", "").strip()

    if azure:
        base = os.environ.get("ALICE_BRAIN_BASE",
                              "https://tourdecontrole.openai.azure.com/").rstrip("/")
        deployment = os.environ.get("ALICE_BRAIN_DEPLOYMENT", "gpt-5-mini")
        api_version = os.environ.get("ALICE_BRAIN_API_VERSION", "2024-12-01-preview")
        modele = deployment
        url = ("%s/openai/deployments/%s/chat/completions?api-version=%s"
               % (base, deployment, api_version))
        en_tetes = {"Content-Type": "application/json"}
        if cle:
            en_tetes["api-key"] = cle
    else:
        modele = os.environ.get("ALICE_BRAIN_MODEL", "qwen2.5-3b-instruct")
        url = os.environ.get(
            "ALICE_BRAIN_URL",
            "http://192.168.1.61:8081/v1/chat/completions")
        en_tetes = {"Content-Type": "application/json"}
        if cle:
            en_tetes["Authorization"] = "Bearer %s" % cle

    payload = {
        "model": modele,
        "messages": messages,
        "stream": False
    }

    # Les modèles à raisonnement (gpt-5, o1/o3/o4-mini) :
    #  - n'acceptent pas max_tokens → max_completion_tokens ;
    #  - n'acceptent pas temperature ≠ 1 (on l'omet).
    if any(nom in modele.lower() for nom in ("gpt-5", "o1", "o3", "o4")):
        payload["max_completion_tokens"] = max_tokens
    else:
        payload["temperature"] = temperature
        payload["max_tokens"] = max_tokens

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=en_tetes
    )

    # Les ressources de démo ont un quota serré : on retente poliment sur
    # 429/5xx (3 essais, backoff 2s puis 5s).
    import urllib.error as _urlerr
    dernier = None
    for _essai in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as reponse:
                donnees = json.loads(reponse.read().decode('utf-8'))
                return donnees["choices"][0]["message"]["content"]
        except _urlerr.HTTPError as erreur:
            dernier = erreur
            if erreur.code not in (429, 500, 502, 503, 504):
                break
            time.sleep(2 if _essai == 0 else 5)
        except Exception as erreur:
            return f"Erreur : {erreur}"
    return f"Erreur : {dernier}"


class Routeur:
    """
    Le routeur est comme un aiguilleur de train.
    Il regarde d'abord sa carte, puis son carnet, puis il réfléchit.
    """

    def __init__(self, chemin_carte="carte-vivante/cartes.json", chemin_db="state/alicization.db"):
        self.carte = AdaptateurCarte(chemin_carte)
        self.memoire = Memoire(chemin_db)
        # T04 : les opérations que Alice sait appliquer (affines x*a + b)
        self.operations = [op_k7, op_m2, op_q9, op_r4, op_t1, op_v6]

    def appliquer_procedure(self, procedure, valeur):
        """
        Applique une procédure (liste d'opérations) à une valeur donnée.
        Exemple : procedure = ['op_k7', 'op_m2', 'op_q9'] et valeur = 17
        Retourne le résultat final (ou None si une op est inconnue).
        """
        resultat = valeur
        for nom_op in procedure:
            op_func = None
            for op in self.operations:
                if op.__name__ == nom_op:
                    op_func = op
                    break
            if op_func is not None:
                resultat = op_func(resultat)
            else:
                return None
        return resultat

    def _tracer(self, message, type_etape="info"):
        """
        Écrit une trace dans le fichier trace.log avec une icône et l'heure.
        type_etape peut être : "carte", "memoire", "modele", "succes", "erreur", "info"
        """
        from datetime import datetime
        icones = {
            "carte": "🗺️",
            "memoire": "📖",
            "modele": "🧠",
            "action": "⚡",
            "succes": "✅",
            "erreur": "❌",
            "info": "📦"
        }
        heure = datetime.now().strftime("%H:%M:%S")
        icone = icones.get(type_etape, "📦")
        with open("/home/alice/alicization/trace.log", "a", encoding="utf-8") as f:
            f.write(f"[{heure}] {icone} {message}\n")

    def router(self, requete):
        """
        La fonction principale du routeur.
        Elle prend une requête et décide quoi faire.
        """
        # tracer la réception
        self._tracer(f"REQUÊTE : {requete}", "info")
        requete_propre = self._nettoyer(requete)

        # --- ÉTAPE 1 : CONSULTER LA CARTE ---
        self._tracer(f"CARTE : recherche de '{requete_propre}'...", "carte")
        info_carte = self._consulter_carte(requete_propre)

        if info_carte:
            etapes = info_carte["data"].get("etapes", [])
            message = f"Je sais déjà ! C'est sur la carte. Voici les étapes :\n" + "\n".join(etapes)

            # --- T04 : GÉNÉRALISATION ---
            # Si la question demande d'appliquer la procédure à une valeur,
            # on extrait les opérations (op_*) et on les applique au nombre de la question.
            procedure = []
            if isinstance(info_carte["data"].get("procedure"), list):
                procedure = info_carte["data"]["procedure"]
            if not procedure:
                procedure = [re.findall(r'op_[a-z0-9]+', e) for e in etapes]
                procedure = [p for sub in procedure for p in sub]

            match_nombres = re.findall(r'\b([0-9]+)\b', requete)
            demande_application = bool(re.search(r'appliqu|g[eé]n[eé]ralis', requete, re.IGNORECASE))

            if match_nombres and procedure and demande_application:
                valeur = float(match_nombres[-1])
                resultat = self.appliquer_procedure(procedure, valeur)
                if resultat is not None:
                    self._tracer(f"GÉNÉRALISATION : {procedure} appliquée à {valeur:.0f} → {resultat:.0f}", "succes")
                    return {
                        "decision": "circuit",
                        "source": "carte",
                        "message": f"En appliquant la procédure à {valeur:.0f}, on obtient : {resultat:.0f}",
                        "etapes": etapes,
                        "procedure": procedure,
                        "resultat": resultat
                    }

            self._tracer(f"CARTE : trouvé → {info_carte['type']} : {info_carte['data']['nom']}", "succes")
            return {
                "decision": "circuit",
                "source": "carte",
                "info": info_carte,
                "etapes": etapes,
                "message": message
            }

        self._tracer("CARTE : pas trouvé", "erreur")

        # --- ÉTAPE 2 : CONSULTER LA MÉMOIRE ---
        self._tracer(f"MÉMOIRE : recherche de '{requete_propre}'...", "memoire")
        info_memoire = self.memoire.chercher(requete_propre)

        if info_memoire:
            etapes = info_memoire.get("etapes", [])
            if etapes:
                message = f"Je me souviens ! J'ai appris ça avant. Voici les étapes :\n" + "\n".join(etapes)
            else:
                message = "Je me souviens ! J'ai appris ça avant."
            self._tracer(f"MÉMOIRE : trouvé → {info_memoire['nom']}", "succes")
            return {
                "decision": "circuit",
                "source": "memoire",
                "info": info_memoire,
                "etapes": etapes,
                "message": message
            }

        self._tracer("MÉMOIRE : pas trouvé", "erreur")

        # --- ÉTAPE 2.4 : LES YEUX D'ALICE (OCR) ---
        # « lis cette image <chemin> » ou « ocr ... » → Alice lit le texte dessus.
        pattern_ocr = re.compile(
            r'(?:lis\s+(?:cette\s+)?l[\'\u2019]?image|lis\s+(?:cette\s+)?image|(?:^|\s)ocr|cette\s+image|d[eé]chiffre l[\'\u2019]?image)',
            re.IGNORECASE)
        if pattern_ocr.search(requete):
            self._tracer("OCR : demande de lecture d'image", "action")
            match_img = re.search(r'(\S+\.(?:png|jpg|jpeg|webp|gif))', requete, re.IGNORECASE)
            if match_img:
                chemin = match_img.group(1)
                if chemin.startswith("~/"):
                    chemin = os.path.expanduser(chemin)
                elif not chemin.startswith("/"):
                    chemin = os.path.join("/home/alice", chemin)
                from outils.ocr import extraire_texte
                texte = extraire_texte(chemin)
                if texte:
                    self._tracer(f"OCR : {len(texte)} caractères lus dans {chemin}", "succes")
                    return {
                        "decision": "action",
                        "source": "outil_ocr",
                        "message": "J'ai lu sur l'image :\n" + texte
                    }
                self._tracer(f"OCR : rien lu dans {chemin}", "erreur")
                return {
                    "decision": "action",
                    "source": "outil_ocr",
                    "message": f"Je n'ai rien lu dans cette image : {chemin}"
                }

        # --- ÉTAPE 2.5 : DÉTECTER LES ACTIONS DIRECTES ---
        pattern_action = r'(?:crée\s+un\s+fichier|crée\s+fichier|écris\s+dans|ajoute\s+à|affiche\s+\S+|montre\s+\S+|cat\s+\S+|liste\s+les\s+fichiers|ls|crée\s+un\s+dossier|supprime\s+le\s+fichier)'

        if re.search(pattern_action, requete, re.IGNORECASE):
            self._tracer("ACTION : détection d'une action directe", "action")

            if "crée" in requete and "fichier" in requete:
                match_nom = re.search(r'(?:fichier|dans)\s+(\S+)', requete)
                match_contenu = re.search(r'écris\s+"([^"]+)"|écris\s+\'([^\']+)\'|contenu\s+"([^"]+)"|écris\s+(\S+)', requete)
                if match_nom:
                    nom = match_nom.group(1)
                    if match_contenu:
                        contenu = match_contenu.group(1) or match_contenu.group(2) or match_contenu.group(3) or match_contenu.group(4)
                        commande = f'echo "{contenu}" > {nom}'
                    else:
                        commande = f'touch {nom}'
                    resultat = executer_action(commande)
                    self._tracer(f"✅ ACTION : {commande} → ok", "action")
                    return {
                        "decision": "action",
                        "source": "action",
                        "message": resultat
                    }

            elif "liste" in requete or "ls" in requete:
                commande = "ls -la"
                match = re.search(r'(?:dossier|répertoire)\s+(\S+)', requete)
                if match:
                    commande += f" {match.group(1)}"
                resultat = executer_action(commande)
                self._tracer(f"✅ ACTION : {commande} → ok", "action")
                return {
                    "decision": "action",
                    "source": "action",
                    "message": resultat
                }

            elif "affiche" in requete or "montre" in requete or "cat" in requete:
                match = re.search(r'(?:cat|affiche|montre)\s+(\S+)', requete)
                if match:
                    commande = f"cat {match.group(1)}"
                    resultat = executer_action(commande)
                    self._tracer(f"✅ ACTION : {commande} → ok", "action")
                    return {
                        "decision": "action",
                        "source": "action",
                        "message": resultat
                    }

        # --- ÉTAPE 2.6 : ACTIONS AVANCÉES (via Qwen) ---
        if "commande" in requete or "exécute" in requete or "lance" in requete:
            self._tracer("ACTION : demande d'action avancée via Qwen", "action")
            messages = [
                {"role": "system", "content": "Tu es un assistant Linux. Réponds UNIQUEMENT avec la commande shell à exécuter, sans explication, sans markdown. Une seule ligne."},
                {"role": "user", "content": requete}
            ]
            reponse_modele = call_model(messages, temperature=0.2)
            commande = re.sub(r'^```\w*\n?', '', reponse_modele)
            commande = re.sub(r'\n```$', '', commande)
            commande = commande.strip().split('\n')[0]

            if "sudo" in commande or "rm -rf" in commande or "mkfs" in commande or "dd " in commande:
                self._tracer(f"ACTION : commande refusée → {commande}", "erreur")
                return {
                    "decision": "action",
                    "source": "action",
                    "message": f"Commande refusee pour securite : {commande}"
                }

            resultat = executer_action(commande)
            self._tracer(f"✅ ACTION AVANCÉE : {commande} → ok", "action")
            return {
                "decision": "action",
                "source": "action",
                "message": f"$ {commande}\n\n{resultat}"
            }

        # --- ÉTAPE 3 : APPELER LE MODÈLE ---
        self._tracer("MODÈLE : appel à Qwen...", "modele")
        debut = time.time()

        messages = [
            {"role": "system", "content": "Tu es Alice, une assistante IA. Réponds de manière claire, concise et surtout brève : idéalement 1 ou 2 phrases, jamais plus de 3."},
            {"role": "user", "content": requete}
        ]
        reponse_modele = call_model(messages)
        temps_ecoule = time.time() - debut

        self._tracer(f"MODÈLE : réponse reçue en {temps_ecoule:.2f}s", "succes")

        return {
            "decision": "modele",
            "source": "nouveau",
            "reponse": reponse_modele,
            "message": reponse_modele
        }

    def _nettoyer(self, texte):
        """Enlève les mots inutiles et normalise les accents (é→e, à→a...)."""
        mots_inutiles = ["peux-tu", "s'il te plaît", "pourrais-tu", "est-ce que"]
        for mot in mots_inutiles:
            texte = texte.replace(mot, "")
        # Normaliser les accents : é→e, è→e, ê→e, à→a, â→a, ç→c, ô→o, î→i, û→u, ù→u
        accents = {
            'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
            'à': 'a', 'â': 'a', 'ä': 'a',
            'ç': 'c',
            'ô': 'o', 'ö': 'o', 'ó': 'o', 'ò': 'o',
            'î': 'i', 'ï': 'i', 'í': 'i', 'ì': 'i',
            'û': 'u', 'ü': 'u', 'ú': 'u', 'ù': 'u',
            'É': 'e', 'È': 'e', 'Ê': 'e', 'Ë': 'e',
            'À': 'a', 'Â': 'a', 'Ä': 'a', 'Ç': 'c',
            'Ô': 'o', 'Ö': 'o', 'Ó': 'o', 'Ò': 'o',
            'Î': 'i', 'Ï': 'i', 'Í': 'i', 'Ì': 'i',
            'Û': 'u', 'Ü': 'u', 'Ú': 'u', 'Ù': 'u'
        }
        for origin, fin in accents.items():
            texte = texte.replace(origin, fin)
        # Garde seulement les lettres, chiffres, espaces et underscores
        texte = re.sub(r'[^a-zA-Z0-9_\s]', '', texte)
        return texte.strip().lower()

    def _consulter_carte(self, requete):
        """
        Alice regarde sa carte pour voir si elle connaît déjà la réponse.
        C'est comme chercher un mot dans le dictionnaire.
        """
        # Recharger la carte vivante à chaque appel (elle peut être mise à jour à chaud
# par ingestion). On lit le fichier configuré, sinon on garde la carte déjà chargée.
        carte = {}
        chemin_carte = getattr(self.carte, "chemin_carte", None)
        if chemin_carte is not None and Path(chemin_carte).exists():
            try:
                with open(chemin_carte, 'r', encoding='utf-8') as f:
                    carte = json.load(f)
            except Exception:
                carte = self.carte.carte if self.carte else {}
        else:
            carte = self.carte.carte if self.carte else {}

        # Alice parcourt toutes les zones et tous les noeuds de la carte
        # Elle cherche le MEILLEUR match (confiance en [0,1])
        meilleur_match = None
        meilleur_score = 0.0

        for zone in carte.get("zones", []):
            for noeud in zone.get("noeuds", []):
                # Ne matcher que les circuits et les outils (pas les patron, equipier, etc.)
                if noeud.get("type") not in ("circuit", "outil"):
                    continue

                mots_cles = noeud.get("mots_cles", [])
                nom_norm = self._nettoyer(noeud["nom"])

                # Confiance :
                #  - 1.0 si le nom complet du circuit est dans la requête
                #  - sinon, 1.0 si la requête contient un mot-clé *caractéristique*
                #    (chiffre ou mot rare, jamais un mot générique comme « procédure »)
                #  - sinon, la fraction des mots-clés caractéristiques retrouvés
                confiance = 0.0
                if nom_norm and nom_norm in requete:
                    confiance = 1.0
                elif mots_cles:
                    caracteristiques = [
                        self._nettoyer(m) for m in mots_cles
                        if self._nettoyer(m) and self._nettoyer(m) not in MOTS_GENERIQUES_CARTE
                    ]
                    correspondances = 0
                    for mot in caracteristiques:
                        if mot in requete:
                            correspondances += 1
                            # Mot-clé rare ou chiffré → intention forte
                            if any(c.isdigit() for c in mot) or len(mot) >= 6:
                                correspondances = len(caracteristiques)
                                break
                    if correspondances:
                        confiance = correspondances / max(1, len(caracteristiques))
                        if correspondances >= len(caracteristiques):
                            confiance = 1.0

                if confiance > 0:
                    self._tracer(f"CARTE : '{noeud['nom']}' → confiance {confiance:.2f}", "carte")

                if confiance > meilleur_score:
                    meilleur_score = confiance
                    meilleur_match = {"type": noeud["type"], "data": noeud}

        # Sélection du meilleur circuit
        if meilleur_match and meilleur_score >= SEUIL_CONFIANCE:
            self._tracer(f"CARTE : sélectionné {meilleur_match['data']['nom']} (score: {meilleur_score:.2f})", "carte")
            return meilleur_match
        else:
            self._tracer(f"CARTE : aucun circuit avec score >= {SEUIL_CONFIANCE} (meilleur: {meilleur_score:.2f})", "carte")
            return None

    def carte_stats(self):
        """Retourne des statistiques sur la carte."""
        noeuds = self.carte.get_tous_les_noeuds()
        zones = len(self.carte.carte.get("zones", []))
        return {
            "total_zones": zones,
            "total_noeuds": len(noeuds),
            "types": list(set(n["type"] for n in noeuds))
        }