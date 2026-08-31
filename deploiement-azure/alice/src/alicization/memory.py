# ============================================================
# MÉMOIRE — le carnet de notes d'Alice
# Elle stocke les procédures qu'Alice a apprises.
# ============================================================

import sqlite3
import json
import re
from datetime import datetime

class Memoire:
    """
    La mémoire est comme un carnet de notes.
    Alice écrit dedans ce qu'elle apprend, et elle peut le relire plus tard.
    """

    # Mots trop génériques pour servir de correspondance (évite les faux positifs :
    # « donne moi la procedure pour faire un gateau » ne doit pas renvoyer une procédure
    # simplement parce qu'elle contient le mot « procedure »).
    _BANALS = {
        "la", "le", "les", "un", "une", "de", "du", "des", "et", "ou", "avec",
        "donne", "moi", "toi", "pour", "faire", "sur", "dans", "comment",
        "procedure", "procedures", "etape", "etapes", "creer", "configurer",
        "configuration", "lire", "verifier", "apprendre", "nouvelle", "nouveau",
        "operation", "operations", "liste", "affiche", "cherche", "trouver",
    }

    _ACCENTS = str.maketrans("àâäéèêëîïôöûüùçÀÂÄÉÈÊËÎÏÔÖÛÜÙÇ",
                             "aaaeeeeiioouuucAAAEEEEIIOOUUUC")

    @staticmethod
    def _cle(texte):
        """Minuscules, sans accents ni séparateurs : clé de comparaison (a-z0-9)."""
        if not texte:
            return ""
        return re.sub(r"[^a-z0-9]", "", texte.translate(Memoire._ACCENTS).lower())

    @staticmethod
    def _mots(texte):
        """Mots significatifs (>= 4 lettres, hors mots banalisés) d'un texte."""
        if not texte:
            return set()
        normalise = texte.translate(Memoire._ACCENTS).lower()
        return {m for m in re.findall(r"[a-z0-9]+", normalise)
                if len(m) >= 4 and m not in Memoire._BANALS}

    def __init__(self, chemin_db="state/alicization.db"):
        self.chemin_db = chemin_db
        self.table = self._creer_table()

    def _creer_table(self):
        """Crée la table des procédures si elle n'existe pas.

        Si une table nommée `procedures` existe déjà avec un autre schéma
        (ex: celle du RL qui stocke steps_json/status), on utilise une table
        dédiée `procedures_memoire` pour ne pas écraser les données RL.
        Retourne le nom de la table utilisée.
        """
        nom_table = "procedures"
        with sqlite3.connect(self.chemin_db) as conn:
            colonnes = {
                r[0] for r in conn.execute("PRAGMA table_info(procedures)").fetchall()
            }
            if colonnes and "nom" not in colonnes:
                nom_table = "procedures_memoire"
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {nom_table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom TEXT UNIQUE,
                    etapes TEXT,
                    description TEXT,
                    mots_cles TEXT,
                    date_creation TEXT,
                    utilisation INTEGER DEFAULT 0
                )
            """)
        return nom_table

    def ajouter(self, nom, etapes, description="", mots_cles=None):
        """Ajoute une nouvelle procédure dans le carnet."""
        date = datetime.now().isoformat()
        with sqlite3.connect(self.chemin_db) as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO {self.table} (nom, etapes, description, mots_cles, date_creation) VALUES (?, ?, ?, ?, ?)",
                (nom, json.dumps(etapes), description, json.dumps(mots_cles or []), date)
            )

    def chercher(self, requete):
        """Cherche une procédure par son nom ou ses mots-clés.

        Correspondances (par ordre de force) :
          1. nom exact (après normalisation accents, minuscules, séparateurs) ;
          2. nom entier contenu dans la requête (ex: « procedure anti regression ») ;
          3. au moins un mot significatif commun entre le nom et la requête ;
          4. un mot-clé explicite (>= 4 lettres, hors mots banalisés) présent entier.
        Les mots génériques (« procedure », « la », « faire »...) ne suffisent plus
        à déclencher une correspondance → fin des faux positifs.
        """
        with sqlite3.connect(self.chemin_db) as conn:
            lignes = conn.execute(
                f"SELECT nom, etapes, mots_cles FROM {self.table}"
            ).fetchall()

            cle_requete = self._cle(requete)
            mots_requete = self._mots(requete)

            for nom, etapes_json, mots_cles_json in lignes:
                cle_nom = self._cle(nom)
                # 1. Nom exact
                if cle_nom and cle_nom == cle_requete:
                    return {"nom": nom, "etapes": json.loads(etapes_json), "type": "exact"}
                # 2. Nom entier présent dans la requête
                if cle_nom and len(cle_nom) >= 4 and cle_nom in cle_requete:
                    return {"nom": nom, "etapes": json.loads(etapes_json), "type": "lexical"}
                # 3. Au moins un mot significatif commun
                commun = self._mots(nom) & mots_requete
                if commun:
                    return {"nom": nom, "etapes": json.loads(etapes_json), "type": "lexical"}
                # 4. Mots-clés explicites (entiers, significatifs)
                if mots_cles_json:
                    try:
                        for mc in json.loads(mots_cles_json):
                            mc_cle = self._cle(mc)
                            if len(mc_cle) >= 4 and mc_cle not in self._BANALS:
                                if re.search(r"\b" + re.escape(mc_cle) + r"\b", cle_requete):
                                    return {"nom": nom, "etapes": json.loads(etapes_json), "type": "mots_cles"}
                    except (json.JSONDecodeError, TypeError):
                        pass

            return None

    def get_stats(self):
        """Retourne le nombre de procédures dans le carnet."""
        with sqlite3.connect(self.chemin_db) as conn:
            curseur = conn.execute(f"SELECT COUNT(*) FROM {self.table}")
            return {"total": curseur.fetchone()[0]}

    # Alias pour compatibilité avec les anciens tests
    def stocker(self, nom, description, mots_cles, etapes, source="apprise"):
        """Alias de ajouter pour compatibilité."""
        self.ajouter(nom, etapes, description, mots_cles)

    def compter(self):
        """Alias pour compter le nombre de procédures."""
        return self.get_stats()["total"]