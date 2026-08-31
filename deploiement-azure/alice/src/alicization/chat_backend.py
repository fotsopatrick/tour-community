#!/usr/bin/env python3
# chat_backend.py - API Alice :8002 - avec LIVE GNS3 pour 8003
import sys
sys.path.insert(0, '/home/alice/alicization')
sys.path.insert(0, '/home/alice')

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import uuid, time, threading, json, os

app = Flask(__name__)
CORS(app)

try:
    from routeur import Routeur
    routeur = Routeur(chemin_carte="/home/alice/carte-vivante/cartes.json", chemin_db="/home/alice/alicization/state/alicization.db")
except Exception as e:
    print(f"Impossible de charger Routeur: {e}", file=sys.stderr)
    from routeur_avec_carte import Routeur as Routeur2
    routeur = Routeur2(chemin_carte="/home/alice/carte-vivante/cartes.json", chemin_db="/home/alice/alicization/state/alicization.db")

_donjon_etat = {}
_donjon_lock = threading.Lock()
_donjon_messages = {}

# LIVE GNS3 - etat du paquet en cours
_live_lock = threading.Lock()
_live = {
    "id": None,
    "message": "",
    "chemin": ["client","c-api","routeur","adaptateur-carte","memoire","outil-ocr","moteur-qwen","c-llama","c-api","client"],
    "position": -1,
    "etape": "idle",
    "source": "",
    "ts": 0
}
CHEMIN_DEFAUT = ["client","c-api","routeur","adaptateur-carte","memoire","outil-ocr","moteur-qwen","c-llama","c-api","client"]
LIVE_JSON = "/home/alice/carte-vivante/live.json"

def _set_live(position, etape, message="", source=""):
    with _live_lock:
        _live["position"] = position
        _live["etape"] = etape
        if message: _live["message"] = message[:80]
        if source: _live["source"] = source
        _live["ts"] = time.time()
        # ecrire aussi pour 8003 (meme origine)
        try:
            os.makedirs(os.path.dirname(LIVE_JSON), exist_ok=True)
            with open(LIVE_JSON, "w", encoding="utf-8") as f:
                json.dump(_live, f, ensure_ascii=False)
        except: pass

def _observer_action(description):
    d = description.lower()
    if "droite" in d or "right" in d: return {"type": "move", "direction": "right"}
    if "gauche" in d or "left" in d: return {"type": "move", "direction": "left"}
    if "porte" in d or "door" in d or "open" in d: return {"type": "open", "direction": None}
    if not d.strip(): return None
    if "mur" in d or "vide" in d or "piece" in d:
        if "droite" in d: return {"type": "move", "direction": "right"}
        if "gauche" in d: return {"type": "move", "direction": "left"}
        return {"type": "wait", "direction": None}
    return {"type": "wait", "direction": None}

@app.route('/', methods=['GET'])
def index():
    return send_from_directory('/home/alice/alicization', 'chat.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

@app.route('/live', methods=['GET'])
def live():
    with _live_lock:
        return jsonify(dict(_live))

@app.route('/metrics', methods=['GET'])
def metrics():
    return jsonify({"alice_donjon_requetes_total": len(_donjon_messages)})

@app.route('/chat', methods=['GET','POST'])
def chat():
    if request.method=='GET':
        message = request.args.get('message') or request.args.get('q') or request.args.get('requete')
        if not message:
            if 'text/html' in request.headers.get('Accept',''):
                return send_from_directory('/home/alice/alicization', 'chat.html')
            return jsonify({'usage':'POST /chat {"message":"bonjour"} ou GET /chat?message=bonjour','exemples':['712','bonjour','ocr'],'health':'/health','carte':'/carte_donjon','live':'/live','status':'ok'}), 200
        data = {'message': message}
    else:
        data = request.get_json(force=True, silent=True) or {}
        message = data.get('message') or data.get('requete') or data.get('text') or ""
    if not message:
        return jsonify({"error": "message manquant"}), 400

    # LIVE: debut
    mid = str(uuid.uuid4())[:6]
    _set_live(0, "client -> API", message, "")
    # petit delai pour que la carte voie le depart (GNS3)
    time.sleep(0.25)
    _set_live(1, "Routeur", message, "")
    time.sleep(0.25)

    msg_low = message.lower()
    if "parcours le donjon" in msg_low and "trouve la sortie" in msg_low:
        _set_live(3, "mission_donjon", message, "mission_donjon")
        time.sleep(0.3)
        _set_live(len(CHEMIN_DEFAUT)-1, "retour chat", message, "mission_donjon")
        return jsonify({"reponse": "Mission recue : je parcours le donjon et trouve la sortie. A droite, a gauche, une porte devant...", "source": "mission_donjon", "decision": "mission"})

    # lancer thread d'animation pendant que routeur travaille (pour modele long)
    stop_anim = threading.Event()
    def animate():
        pos = 2
        etapes = ["Carte","Memoire","Outils","Modele Qwen","Retour"]
        idx=0
        while not stop_anim.is_set() and pos < len(CHEMIN_DEFAUT)-1:
            _set_live(pos, etapes[idx % len(etapes)], message, "")
            pos+=1
            idx+=1
            time.sleep(0.6)
    t_anim = threading.Thread(target=animate, daemon=True)
    t_anim.start()

    try:
        # instrumentation fine: on intercepte les etapes via _tracer en patchant temporairement
        # plus simple: on laisse routeur faire son travail et on met a jour live selon le resultat
        _set_live(2, "Carte", message, "")
        res = routeur.router(message)
        stop_anim.set()
        src = res.get("source","")
        # position finale selon source
        if src == "carte":
            _set_live(3, "Carte trouve", message, src)
        elif src == "memoire":
            _set_live(4, "Memoire trouve", message, src)
        elif src in ("outil_ocr","action"):
            _set_live(5, "Outils", message, src)
        elif src == "nouveau":
            _set_live(6, "Modele Qwen", message, src)
        else:
            _set_live(5, src, message, src)
        time.sleep(0.4)
        _set_live(len(CHEMIN_DEFAUT)-1, "retour chat", message, src)
        # garder visible 4s puis idle
        def reset_live():
            time.sleep(30)
            _set_live(-1, "idle", "", "")
        threading.Thread(target=reset_live, daemon=True).start()
        return jsonify({
            "reponse": res.get("message") or res.get("reponse") or "",
            "source": res.get("source"),
            "decision": res.get("decision"),
            "info": res.get("info"),
            "etapes": res.get("etapes"),
            "resultat": res.get("resultat")
        })
    except Exception as e:
        stop_anim.set()
        _set_live(len(CHEMIN_DEFAUT)-1, "erreur", message, "erreur")
        return jsonify({"reponse": f"Erreur routeur: {e}", "source": "erreur"}), 500
    finally:
        stop_anim.set()

@app.route('/ingest', methods=['POST'])
def ingest():
    """Ingestion de connaissance : fichier (PDF->circuits cartes.json) ou
    texte (->procedures SQLite). Filtre l'upload : extensions whitelist,
    taille max (25 Mo), magic bytes PDF. Retourne un journal JSON."""
    import io as _io
    import contextlib
    doses = 25 * 1024 * 1024  # 25 Mo max par fichier
    ext_ok = {".pdf", ".txt", ".md", ".markdown"}
    dossier = "/home/alice/alicization/ingest/intake"
    try:
        os.makedirs(dossier, exist_ok=True)
    except Exception:
        pass

    fichier = request.files.get('file')
    texte = None
    source = None
    if fichier and fichier.filename:
        source = os.path.basename(fichier.filename)
        ext = os.path.splitext(source)[1].lower()
        if ext not in ext_ok:
            return jsonify({"error": f"extension '{ext}' refusee (autorisé: .pdf .txt .md)"}), 415
        if (request.content_length or 0) > doses:
            return jsonify({"error": "fichier trop grand (max 25 Mo)"}), 413
        chemin = os.path.join(dossier, f"{uuid.uuid4().hex[:10]}{ext}")
        fichier.save(chemin)
        if os.path.getsize(chemin) > doses:
            try:
                os.remove(chemin)
            except OSError:
                pass
            return jsonify({"error": "fichier trop grand (max 25 Mo)"}), 413
        if ext == '.pdf':
            try:
                with open(chemin, 'rb') as f:
                    si = f.read(5)
                if not si.startswith(b'%PDF'):
                    try:
                        os.remove(chemin)
                    except OSError:
                        pass
                    return jsonify({"error": "le fichier .pdf ne commence pas par %PDF — PDF invalide ou fichier renomme"}), 415
            except Exception:
                pass
            try:
                from ingesteur_qwen import ingerer_document
            except ImportError:
                return jsonify({"error": "ingesteur_qwen.py introuvable"}), 500
            buf = _io.StringIO()
            with contextlib.redirect_stdout(buf):
                ingerer_document(chemin)
            return jsonify({"ok": True, "type": "pdf", "fichier": source, "log": buf.getvalue()[-3000:]})
        # txt / md -> procédures SQLite
        try:
            texte = open(chemin, encoding='utf-8', errors='ignore').read()
        except Exception as e:
            return jsonify({"error": f"lecture {source}: {e}"}), 500
    else:
        data = request.get_json(force=True, silent=True) or {}
        texte = data.get('text') or data.get('texte') or data.get('contenu') or ""
        source = source or (data.get('nom') or "texte colle")

    if not texte or not texte.strip():
        return jsonify({"error": "fichier ou texte requis"}), 400

    try:
        from ingesteur import extraire_procedures_texte
        from memory import Memoire
        procs = extraire_procedures_texte(texte)
        if not procs:
            return jsonify({"ok": True, "type": "texte", "procedures": [], "nombre": 0,
                            "source": source, "erreur": "aucune procedure detectee (titre + etapes numerotees necessaires)"})
        m = Memoire("/home/alice/alicization/state/alicization.db")
        ajoutes = []
        for p in procs:
            m.ajouter(p["titre"][:80], p["etapes"], f"Ingere via /ingest depuis {source}", p["mots_cles"])
            ajoutes.append(p["titre"])
        return jsonify({"ok": True, "type": "texte", "procedures": ajoutes, "nombre": len(ajoutes), "source": source})
    except Exception as e:
        return jsonify({"error": f"ingestion texte: {e}"}), 500

@app.route('/donjon/observer', methods=['POST'])
def donjon_observer():
    data = request.get_json(force=True, silent=True) or {}
    desc = data.get('description', '')
    if 'description' not in data:
        return jsonify({"error": "description manquante"}), 400
    act = _observer_action(desc)
    if act is None:
        return jsonify({"error": "description vide"}), 400
    try:
        from outils.care_hacking import envelopper, detecter_humeur
        humeur = detecter_humeur(desc)
        msg_base = {"move": "Je me deplace", "open": "J'ouvre la porte", "wait": "J'attends"}.get(act["type"], "Action")
        mid = str(uuid.uuid4())[:8]
        texte = f"{msg_base} - {humeur}"
        _donjon_messages[mid] = {"message": texte, "pret": True, "humeur": humeur}
    except:
        mid = str(uuid.uuid4())[:8]
        _donjon_messages[mid] = {"message": "Action decidee", "pret": True}
    act["id"] = mid
    return jsonify({"action": act})

@app.route('/donjon/message/<mid>', methods=['GET'])
def donjon_message(mid):
    m = _donjon_messages.get(mid)
    if not m:
        return jsonify({"prêt": False, "message": None})
    return jsonify({"prêt": True, "message": m["message"], "pret": True})

@app.route('/donjon/etat', methods=['GET', 'POST'])
def donjon_etat():
    if request.method == 'POST':
        data = request.get_json(force=True, silent=True) or {}
        with _donjon_lock:
            _donjon_etat.update(data)
            _donjon_etat["_ts"] = time.time()
        return jsonify({"ok": True})
    else:
        with _donjon_lock:
            return jsonify(_donjon_etat if _donjon_etat else {})

@app.route('/carte_donjon', methods=['GET'])
def carte_donjon():
    return send_from_directory('/home/alice/alicization', 'carte_donjon.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002, threaded=True)
