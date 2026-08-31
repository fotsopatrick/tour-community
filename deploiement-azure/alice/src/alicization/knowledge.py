#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CONNAISSANCE — la mémoire longue d'ALICE (module ingest).

Ingère du texte (brut, page web ou fichier .txt/.md/.pdf), le découpe en
chunks (taille et chevauchement configurables), le stocke dans la table
`knowledge` et l'indexe pour la recherche.

Deux backends au choix (aucune autre modification de code) :
  - SQLite   : via ALICE_DB  (chemin du fichier, défaut local / cloud éphémère)
  - PostgreSQL : via ALICE_DB_URL (postgresql://user:pass@hôte:5432/bdd) —
                 utilisé en cloud (Cloud SQL / Azure DB for PostgreSQL) pour
                 une mémoire PERSISTANTE.

Index = « embedding simple » par mots-clés : chaque chunk stocke ses termes
significatifs (>= 4 lettres, sans accents, hors mots banalisés). La recherche
compte les termes communs avec la requête et renvoie les meilleurs chunks.
"""
import os
import re
import hashlib
import urllib.request
from datetime import datetime

# ------------------------------------------------------------------ réglages

_BANALS = {
    "la", "le", "les", "un", "une", "de", "du", "des", "et", "ou", "avec",
    "pour", "faire", "sur", "dans", "comment", "quelle", "quel", "qui",
    "que", "quoi", "donne", "moi", "toi", "sais", "savoir", "procedure",
    "procedures", "etape", "etapes", "liste", "affiche", "trouver", "chercher",
    "voici", "cela", "cette", "lire", "creer", "nouvelle", "nouveau",
}

_ACCENTS = str.maketrans("àâäéèêëîïôöûüùçÀÂÄÉÈÊËÎÏÔÖÛÜÙÇ",
                         "aaaeeeeiioouuucAAAEEEEIIOOUUUC")


def _cle(texte):
    if not texte:
        return ""
    return re.sub(r"[^a-z0-9]", "", texte.translate(_ACCENTS).lower())


def mots_significatifs(texte):
    """Termes significatifs d'un texte (>= 4 lettres, hors mots banalisés)."""
    if not texte:
        return set()
    normalise = texte.translate(_ACCENTS).lower()
    return {m for m in re.findall(r"[a-z0-9]+", normalise)
            if len(m) >= 4 and m not in _BANALS}


# ------------------------------------------------------------------ découpage

def decouper(texte, taille=900, chevauchement=120):
    """Découpe un texte en chunks (taille + chevauchement configurables).

    Priorité aux frontières de phrase/paragraphe pour ne pas couper un mot.
    """
    taille = max(int(taille), 200)
    chevauchement = max(int(chevauchement), 0)
    texte = re.sub(r"[ \t]+", " ", texte or "")
    texte = re.sub(r"\n{3,}", "\n\n", texte)
    if len(texte) <= taille:
        return [texte.strip()] if texte.strip() else []

    # Sépare d'abord en blocs de phrases (garde le sens).
    blocs = re.split(r"(?<=[.!?\n])\s+", texte)
    chunks, courant = [], ""
    for bloc in blocs:
        if len(courant) + len(bloc) <= taille:
            courant = (courant + " " + bloc).strip()
            continue
        if courant:
            chunks.append(courant)
        if len(bloc) > taille:
            # gros bloc unique : découpe brute avec chevauchement
            pas = taille - chevauchement
            for i in range(0, len(bloc), pas):
                chunks.append(bloc[i:i + taille])
            courant = ""
        else:
            courant = bloc
    if courant:
        chunks.append(courant)

    # Recolle un chevauchement entre chunks successifs (contexte).
    if chevauchement and len(chunks) > 1:
        recolles = [chunks[0]]
        for c in chunks[1:]:
            queue = recolles[-1][-chevauchement:]
            if not c.startswith(queue):
                c = queue + " " + c
            recolles.append(c.strip())
        chunks = recolles
    return [c.strip() for c in chunks if c.strip()]


# ------------------------------------------------------------- sources texte

def url_vers_texte(url):
    """Récupère une page web et en extrait le texte (HTML grossièrement netoyé)."""
    with urllib.request.urlopen(url, timeout=30) as rep:
        brut = rep.read().decode("utf-8", errors="ignore")
    # bascule : si ce n'est pas du HTML, on garde brut
    if "<" not in brut or "</" not in brut:
        return brut
    brut = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", brut)
    brut = re.sub(r"(?i)<br\s*/?>", "\n", brut)
    brut = re.sub(r"(?i)</p|</div|</li|</h[1-6]>", "\n", brut)
    brut = re.sub(r"(?s)<[^>]+>", " ", brut)
    from html import unescape
    brut = unescape(brut)
    brut = re.sub(r"[ \t]+", " ", brut)
    brut = re.sub(r"\n\s*\n+", "\n\n", brut)
    return brut.strip()


# Moteur d'extraction PDF : "pypdf" (primauté, pure Python, aucun binaire
# système requis) -> "pdftotext" (poppler-utils, si présent) -> "none".
# Les moteurs accessibles à l'exécution sont découverts dynamiquement.
_PDF_ENGINE = "auto"


def _lire_pdf_pypdf(chemin):
    """Extrait le texte d'un PDF avec pypdf (aucune dépendance système)."""
    from pypdf import PdfReader
    try:
        reader = PdfReader(chemin)
    except Exception as e:
        raise RuntimeError("pypdf n'a pas pu ouvrir ce PDF : %s" % e)
    texte = []
    for page in reader.pages:
        try:
            texte.append(page.extract_text() or "")
        except Exception as e:
            raise RuntimeError("pypdf a échoué sur une page : %s" % e)
    return "\n".join(texte).strip()


def _lire_pdf_pdftotext(chemin):
    """Extrait le texte d'un PDF via pdftotext (poppler-utils)."""
    import shutil
    import subprocess
    if shutil.which("pdftotext") is None:
        raise RuntimeError("'pdftotext' (poppler-utils) absent : impossible"
                           " d'extraire le PDF via poppler sur ce conteneur")
    res = subprocess.run(["pdftotext", chemin, "-"],
                         capture_output=True, timeout=180)
    if res.returncode != 0:
        raise RuntimeError("pdftotext a échoué sur ce PDF")
    return res.stdout.decode("utf-8", errors="ignore").strip()


def fichier_vers_texte(chemin):
    """Lit un fichier local : .txt/.md brut ; .pdf via pypdf (ou pdftotext)."""
    ext = os.path.splitext(chemin)[1].lower()
    if ext == ".pdf":
        from importlib import import_module
        import shutil
        if _PDF_ENGINE in ("auto", "pypdf"):
            try:
                import_module("pypdf")
                return _lire_pdf_pypdf(chemin)
            except ImportError:
                pass  # pypdf absent -> fallback pdftotext
            except RuntimeError:
                if _PDF_ENGINE == "pypdf":
                    raise
                # auto : poppler peut réussir là où pypdf échoue -> on tente.
        if shutil.which("pdftotext") is not None:
            return _lire_pdf_pdftotext(chemin)
        raise RuntimeError("aucun extracteur PDF disponible : installé pypdf"
                           " dans l'image ou poppler-utils (pdftotext)")
    with open(chemin, encoding="utf-8", errors="ignore") as f:
        return f.read()


# ---------------------------------------------------------------- stockage

class Connaissance:
    """Stockage des connaissances : chunks + documents, SQLite ou PostgreSQL."""

    def __init__(self, url_bdd=None, chemin_db=None,
                 chunk_size=None, chevauchement=None):
        self.url_bdd = url_bdd
        self.chemin_db = chemin_db
        self.chunk_size = int(chunk_size or int(os.environ.get(
            "ALICE_CHUNK_SIZE", "900")))
        self.chevauchement = int(chevauchement or int(os.environ.get(
            "ALICE_CHUNK_OVERLAP", "120")))
        if url_bdd:
            import psycopg2
            self._psycopg2 = psycopg2
            self.connexion = None
        else:
            self._psycopg2 = None
            if chemin_db and os.path.dirname(chemin_db):
                os.makedirs(os.path.dirname(chemin_db), exist_ok=True)
            import sqlite3
            self.connexion = sqlite3.connect(
                chemin_db or "state/alice.db", check_same_thread=False)
        self._creer_schema()

    # ---- connexions

    def _creer_schema(self):
        if self._psycopg2:
            with self._psycopg2.connect(self.url_bdd) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS documents (
                            id BIGSERIAL PRIMARY KEY,
                            doc_key TEXT UNIQUE,
                            titre TEXT,
                            source TEXT,
                            nb_chunks INTEGER DEFAULT 0,
                            date_ingestion TIMESTAMPTZ DEFAULT now())""")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS knowledge (
                            id BIGSERIAL PRIMARY KEY,
                            doc_key TEXT,
                            contenu TEXT NOT NULL,
                            source TEXT,
                            titre TEXT,
                            numero_chunk INTEGER DEFAULT 1,
                            tokens TEXT DEFAULT '',
                            date_ingestion TIMESTAMPTZ DEFAULT now())""")
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_knowledge_tokens
                        ON knowledge (doc_key)""")
        else:
            self.connexion.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_key TEXT UNIQUE,
                    titre TEXT,
                    source TEXT,
                    nb_chunks INTEGER DEFAULT 0,
                    date_ingestion TEXT)""")
            self.connexion.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_key TEXT,
                    contenu TEXT NOT NULL,
                    source TEXT,
                    titre TEXT,
                    numero_chunk INTEGER DEFAULT 1,
                    tokens TEXT DEFAULT '',
                    date_ingestion TEXT)""")
            self.connexion.commit()

    # ---- écriture

    def ingerer_contenu(self, texte, source="manuel", titre=None):
        """Découpe, stocke et indexe le texte. Retourne {titre, source, chunks}."""
        texte = (texte or "").strip()
        if not texte:
            raise ValueError("aucun contenu à ingérer")
        titre = (titre or source).strip()[:200]
        doc_key = hashlib.sha1(
            ("%s|%s|%s" % (titre, source, datetime.now().isoformat()))
            .encode("utf-8")).hexdigest()[:16]
        chunks = decouper(texte, self.chunk_size, self.chevauchement)
        date = datetime.now().isoformat()
        tokens = " ".join(sorted(mots_significatifs(texte)))[:4000]

        if self._psycopg2:
            with self._psycopg2.connect(self.url_bdd) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO documents (doc_key, titre, source, nb_chunks, date_ingestion)"
                        " VALUES (%s, %s, %s, %s, %s)",
                        (doc_key, titre, source, len(chunks), date))
                    for i, c in enumerate(chunks, 1):
                        cur.execute(
                            "INSERT INTO knowledge (doc_key, contenu, source, titre,"
                            " numero_chunk, tokens, date_ingestion)"
                            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            (doc_key, c, source, titre, i,
                             " ".join(sorted(mots_significatifs(c))), date))
        else:
            for i, c in enumerate(chunks, 1):
                self.connexion.execute(
                    "INSERT INTO knowledge (doc_key, contenu, source, titre,"
                    " numero_chunk, tokens, date_ingestion)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (doc_key, c, source, titre, i,
                     " ".join(sorted(mots_significatifs(c))), date))
            self.connexion.execute(
                "INSERT INTO documents (doc_key, titre, source, nb_chunks, date_ingestion)"
                " VALUES (?, ?, ?, ?, ?)",
                (doc_key, titre, source, len(chunks), date))
            self.connexion.commit()

        return {"titre": titre, "source": source, "chunks": len(chunks)}

    def ingerer_url(self, url, titre=None):
        texte = url_vers_texte(url)
        return self.ingerer_contenu(
            texte, source="url:%s" % url, titre=titre or url)

    def ingerer_fichier(self, chemin, source=None):
        texte = fichier_vers_texte(chemin)
        return self.ingerer_contenu(
            texte, source=source or os.path.basename(chemin),
            titre=os.path.splitext(os.path.basename(chemin))[0])

    # ---- lecture / recherche

    def chercher(self, requete, n=5):
        """Index simple : choisit les chunks qui partagent le plus de termes
        significatifs avec la requête (mêmes règles que la mémoire court terme)."""
        if self._psycopg2:
            with self._psycopg2.connect(self.url_bdd) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT contenu, source, titre, tokens FROM knowledge")
                    lignes = cur.fetchall()
        else:
            lignes = self.connexion.execute(
                "SELECT contenu, source, titre, tokens FROM knowledge").fetchall()
        requete_bas = requete.translate(_ACCENTS).lower()
        mots = mots_significatifs(requete_bas)
        if not mots:
            return []
        scores = []
        for contenu, source, titre, tokens in lignes:
            tokens_set = set((tokens or "").split())
            inter = len(mots & tokens_set)
            if inter:
                scores.append((inter, contenu, source, titre))
        scores.sort(key=lambda x: -x[0])
        return [{"score": s, "contenu": c, "source": src, "titre": t}
                for s, c, src, t in scores[:int(n)]]

    def lister_documents(self, limite=100):
        if self._psycopg2:
            with self._psycopg2.connect(self.url_bdd) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, doc_key, titre, source, nb_chunks, date_ingestion
                        FROM documents ORDER BY id DESC LIMIT %s""", (int(limite),))
                    return [{"id": r[0], "doc_key": r[1], "titre": r[2],
                             "source": r[3], "nb_chunks": r[4],
                             "date": r[5]} for r in cur.fetchall()]
        return [{"id": r[0], "doc_key": r[1], "titre": r[2], "source": r[3],
                 "nb_chunks": r[4], "date": r[5]}
                for r in self.connexion.execute(
                    "SELECT id, doc_key, titre, source, nb_chunks, date_ingestion"
                    " FROM documents ORDER BY id DESC LIMIT ?", (int(limite),))]

    def supprimer_document(self, doc_key):
        if self._psycopg2:
            with self._psycopg2.connect(self.url_bdd) as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM knowledge WHERE doc_key=%s", (doc_key,))
                    cur.execute("DELETE FROM documents WHERE doc_key=%s", (doc_key,))
            return
        self.connexion.execute("DELETE FROM knowledge WHERE doc_key=?", (doc_key,))
        self.connexion.execute("DELETE FROM documents WHERE doc_key=?", (doc_key,))
        self.connexion.commit()

    def vider(self):
        if self._psycopg2:
            with self._psycopg2.connect(self.url_bdd) as conn:
                with conn.cursor() as cur:
                    cur.execute("TRUNCATE knowledge, documents RESTART IDENTITY")
            return
        self.connexion.execute("DELETE FROM knowledge")
        self.connexion.execute("DELETE FROM documents")
        self.connexion.commit()

    def statistiques(self):
        return {"chunks": self._compter("knowledge"),
                "documents": self._compter("documents")}

    def _compter(self, table):
        if self._psycopg2:
            with self._psycopg2.connect(self.url_bdd) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM %s" % table)
                    return cur.fetchone()[0]
        lignes = self.connexion.execute("SELECT COUNT(*) FROM %s" % table).fetchone()
        return lignes[0]