#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ALICE GATE — API :8000
  POST /api/v1/gate            {command, user} -> 202 {job_id, status}
  GET  /api/v1/gate/<job_id>   -> {status, result}
  POST /api/v1/ocr             {image_url}     -> {text}
  POST /api/v1/ingest          {text} | {url} | multipart {file}
                               -> {status, chunks, source, titre}
  POST /api/v1/knowledge       {q, n}          -> chunks pertinents   (recherche)
  GET  /api/v1/knowledge       ?q=             -> chunks pertinents
  GET  /connaissances                           -> liste des documents
  DELETE /connaissances/<doc_key> et  DELETE /connaissances
  POST /chat                   {message}       -> réponse directe (UI)
  GET  /                       -> chat.html (interface)

Reutilise le routeur d'Alice (carte -> memoire -> outils -> modele).
La mémoire longue (ingest) est un backend SQLite local ou PostgreSQL
(env ALICE_DB_URL) pour la persistance cloud.
"""
import sys
import os

# Chemins robustes (machine d'Alice / conteneur / copies locales) :
_HERE = os.path.dirname(os.path.abspath(__file__))
for _chemin in (os.path.join(_HERE, "alicization"),
                os.path.join(_HERE, "..", "src", "alicization"),
                "/home/alice/alicization", "/home/alice", _HERE):
    if _chemin not in sys.path:
        sys.path.insert(0, _chemin)

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from routeur import Routeur, call_model
from knowledge import Connaissance

app = Flask(__name__)
CORS(app)

# Chemins configurables pour le cloud (env) ; par défaut la machine d'Alice.
_CARTE = os.environ.get(
    "ALICE_CARTE", "/home/alice/carte-vivante/cartes.json")
_DB = os.environ.get(
    "ALICE_DB", "/home/alice/alicization/state/alicization.db")
_DB_URL = os.environ.get("ALICE_DB_URL", "")

if os.path.dirname(_DB):
    os.makedirs(os.path.dirname(_DB), exist_ok=True)
if not os.path.exists(_CARTE):
    os.makedirs(os.path.dirname(_CARTE), exist_ok=True)
    with open(_CARTE, "w", encoding="utf-8") as _f:
        _f.write('{"zones": []}')

routeur = Routeur(chemin_carte=_CARTE, chemin_db=_DB)
connaissance = Connaissance(url_bdd=_DB_URL or None, chemin_db=_DB)

_jobs = {}
_jobs_lock = __import__("threading").Lock()

# Réponses brèves et donc rapides sur le moteur de raisonnement.
SYSTEME_RAPIDE = (
    "Tu es Alice, une assistante IA. Réponds de manière claire et très concise : "
    "une seule phrase, jamais plus de deux."
)

# Extensions autorisées pour l'upload (http ingest)
_EXT_OK = {".txt", ".md", ".markdown", ".pdf"}
_TAILLE_MAX = 25 * 1024 * 1024  # 25 Mo


def _creer_job(command):
    import uuid as _uuid
    import time as _time
    job_id = _uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {"status": "running", "command": command,
                         "created": _time.time(), "result": None,
                         "durée_s": None}
    return job_id


def _executer_job(job_id, command):
    import time as _time
    t0 = _time.time()
    try:
        resultat = routeur.router(command)
        if resultat.get("decision") == "modele":
            courte = call_model([
                {"role": "system", "content": SYSTEME_RAPIDE},
                {"role": "user", "content": command},
            ], temperature=0.2, max_tokens=128)
            resultat["reponse"] = courte
            resultat["message"] = courte
        payload = {
            "job_id": job_id,
            "decision": resultat.get("decision"),
            "source": resultat.get("source"),
            "message": resultat.get("message") or resultat.get("reponse"),
            "resultat": resultat.get("resultat"),
        }
        etat = "done"
    except Exception as e:
        payload = {"job_id": job_id, "decision": "erreur",
                   "source": "erreur", "message": f"Erreur: {e}"}
        etat = "error"
    with _jobs_lock:
        _jobs[job_id]["status"] = etat
        _jobs[job_id]["result"] = payload
        _jobs[job_id]["durée_s"] = round(_time.time() - t0, 3)


# ------------------------------------------------------------------ gate

@app.route("/api/v1/gate", methods=["POST"])
def gate():
    data = request.get_json(force=True, silent=True) or {}
    command = (data.get("command") or data.get("message") or "").strip()
    user = data.get("user") or "anonyme"
    if not command:
        return jsonify({"error": "champ 'command' manquant"}), 400

    job_id = _creer_job(command)
    import threading as _threading
    _threading.Thread(target=_executer_job, args=(job_id, command),
                      daemon=True).start()
    return jsonify({"job_id": job_id, "status": "running",
                    "message": f"demande reçue de {user}"}), 202


@app.route("/api/v1/gate/<job_id>", methods=["GET"])
def gate_status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"error": "job inconnu"}), 404
    rep = {"job_id": job_id, "status": job["status"],
           "durée_s": job["durée_s"]}
    if job["result"] is not None:
        rep["result"] = job["result"]
    return jsonify(rep), (200 if job["status"] != "error" else 500)


# ------------------------------------------------------------------ ingest

@app.route("/api/v1/ingest", methods=["POST"])
def ingest():
    """Ingère de la connaissance : {text} | {url} | fichier multipart 'file'.

    Découpe le contenu en chunks (ALICE_CHUNK_SIZE / ALICE_CHUNK_OVERLAP),
    stocke dans la table `knowledge` (SQLite ou PostgreSQL) et indexe.
    """
    import uuid as _uuid
    import tempfile as _tempfile

    data = request.get_json(force=True, silent=True) or {}
    fichier = request.files.get("file")
    source = data.get("source") or "manuel"

    # 1. fichier uploadé
    if fichier and fichier.filename:
        source = os.path.basename(fichier.filename)
        ext = os.path.splitext(source)[1].lower()
        if ext not in _EXT_OK:
            return jsonify({"error": f"extension '{ext}' refusée"
                                     " (autorisé: .txt .md .pdf)"}), 415
        if (request.content_length or 0) > _TAILLE_MAX:
            return jsonify({"error": "fichier trop grand (max 25 Mo)"}), 413
        tmp = _tempfile.mktemp(suffix=ext)
        fichier.save(tmp)
        try:
            if os.path.getsize(tmp) > _TAILLE_MAX:
                raise ValueError("fichier trop grand (max 25 Mo)")
            titre = os.path.splitext(source)[0]
            resultat = connaissance.ingerer_fichier(tmp, source=source)
            resultat["titre"] = titre
            return jsonify({"status": "ok", **resultat}), 200
        except Exception as e:
            return jsonify({"error": f"ingestion fichier: {e}"}), 500
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    # 2. URL à scraper
    url = data.get("url") or (data.get("source") or "").startswith("http")
    url = (data.get("url") or "").strip()
    if url:
        try:
            resultat = connaissance.ingerer_url(url, titre=data.get("titre"))
            return jsonify({"status": "ok", **resultat}), 200
        except Exception as e:
            return jsonify({"error": f"ingestion url: {e}"}), 500

    # 3. texte brut
    texte = data.get("text") or data.get("texte") or data.get("contenu") or ""
    if not texte.strip():
        return jsonify({"error": "fournir 'text', 'url', ou un fichier 'file'"}), 400
    try:
        resultat = connaissance.ingerer_contenu(
            texte, source=source, titre=data.get("titre"))
        return jsonify({"status": "ok", **resultat}), 200
    except Exception as e:
        return jsonify({"error": f"ingestion texte: {e}"}), 500


@app.route("/api/v1/knowledge", methods=["GET", "POST"])
def knowledge_search():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        q = data.get("q") or data.get("requete") or ""
    else:
        q = request.args.get("q") or request.args.get("requete") or ""
    if not q.strip():
        return jsonify({"error": "paramètre 'q' manquant"}), 400
    try:
        n = int(request.args.get("n") or (request.get_json(
            force=True, silent=True) or {}).get("n") or 5)
    except (TypeError, ValueError):
        n = 5
    resultats = connaissance.chercher(q, n=n)
    return jsonify({"requete": q, "n": len(resultats),
                    "resultats": resultats}), 200


@app.route("/connaissances", methods=["GET", "DELETE"])
def connaissances():
    if request.method == "DELETE":
        connaissance.vider()
        return jsonify({"status": "ok", "action": "tout_vide"}), 200
    return jsonify({"documents": connaissance.lister_documents()}), 200


@app.route("/connaissances/<doc_key>", methods=["DELETE"])
def connaissances_delete(doc_key):
    try:
        connaissance.supprimer_document(doc_key)
        return jsonify({"status": "ok", "supprime": doc_key}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------------------------------------------------------ chat (UI)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or data.get("requete")
               or data.get("text") or "").strip()
    if not message:
        return jsonify({"error": "message manquant"}), 400
    try:
        res = routeur.router(message)
        if res.get("decision") == "modele":
            # RAG : injecte la connaissance ingérée (table knowledge) utile à la
            # question, pour qu'ALICE réponde avec sa mémoire et non de mémoire
            # (sinon elle hallucine : l'ingest remplit la table, le chat l'ignore).
            resultats = connaissance.chercher(message, n=3)
            systeme = SYSTEME_RAPIDE
            if resultats:
                extraits = "\n\n".join(
                    f"[{r.get('titre') or 'doc'}] {r['contenu']}"
                    for r in resultats)
                systeme += (f"\n\nContexte (connaissance ingérée, source fiable) :\n"
                            f"{extraits}\n"
                            f"Réponds en t'appuyant sur ce contexte si pertinent.")
            res["reponse"] = call_model([
                {"role": "system", "content": systeme},
                {"role": "user", "content": message},
            ], temperature=0.2, max_tokens=1024)
            res["message"] = res["reponse"]
            res["source"] = "connaissance" if (resultats
                                               or res.get("resultat")) \
                else res.get("source")
        return jsonify({
            "reponse": res.get("message") or res.get("reponse") or "",
            "source": res.get("source"),
            "decision": res.get("decision"),
            "etapes": res.get("etapes"),
            "resultat": res.get("resultat"),
        }), 200
    except Exception as e:
        return jsonify({"reponse": f"Erreur routeur: {e}",
                        "source": "erreur"}), 500


@app.route("/", methods=["GET"])
def index():
    if "text/html" in (request.headers.get("Accept", "") or ""):
        try:
            return send_from_directory(os.path.dirname(os.path.abspath(__file__)),
                                       "alicization/chat.html")
        except Exception:
            return send_from_directory(os.path.dirname(os.path.abspath(__file__)),
                                       "chat.html")
    return jsonify({"usage": "POST /api/v1/gate {command} ; POST /api/v1/ingest"
                             " {text|url|file} ; GET /api/v1/knowledge?q= ;"
                             " GET /connaissances ; POST /chat ; UI: /"})


# ------------------------------------------------------------------ divers

@app.route("/api/v1/ocr", methods=["POST"])
def ocr():
    """Lit une image distante (image_url) avec Tesseract."""
    import urllib.request as _urllib
    import tempfile as _tempfile
    data = request.get_json(force=True, silent=True) or {}
    image_url = data.get("image_url") or data.get("url") or ""
    if not image_url:
        return jsonify({"error": "champ 'image_url' manquant"}), 400
    try:
        suffix = os.path.splitext(_urllib.urlparse(image_url).path)[1] or ".png"
        if suffix.lower() not in (".png", ".jpg", ".jpeg", ".ppm", ".pgm",
                                  ".bmp", ".tif", ".tiff", ".webp"):
            suffix = ".png"
        tmp_path = _tempfile.mktemp(suffix=suffix)
        try:
            with _urllib.urlopen(image_url, timeout=10) as r:
                contenu = r.read()
        except Exception as e:
            return jsonify({"error": f"telechargement image: {e}"}), 500
        with open(tmp_path, "wb") as f:
            f.write(contenu)
        try:
            from outils.ocr import extraire_texte
        except ImportError:
            return jsonify({"error": "outil OCR introuvable"}), 500
        texte = extraire_texte(tmp_path)
        if texte:
            return jsonify({"text": texte, "source": image_url}), 200
        return jsonify({"error": "rien lu dans l'image",
                        "source": image_url}), 500
    except Exception as e:
        return jsonify({"error": f"OCR échoué: {e}"}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "alice-gate",
                    "memoire": connaissance.statistiques()})


if __name__ == "__main__":
    try:
        os.makedirs("/home/alice/alicization/logs", exist_ok=True)
    except Exception:
        pass
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")),
            threaded=True)