import os
import sqlite3
import requests
import json
import subprocess

# Test 1 - ALICE mémoire SQLite

def test_alice_memory():
    memory_path = "/home/alice/state/alicization.db"
    assert os.path.exists(memory_path), f"Fichier {memory_path} introuvable"
    conn = sqlite3.connect(memory_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='procedures_memoire'")
    table = cursor.fetchone()
    assert table is not None, "Table 'procedures_memoire' manquante"
    conn.close()
    print("✅ Test ALICE mémoire OK")

# Test 2 - ALICE routeur santé

def test_alice_routeur_health():
    try:
        r = requests.get("http://192.168.1.61:8000/health", timeout=5)
        assert r.status_code == 200
        print("✅ ALICE health OK")
    except Exception as e:
        assert False, f"ALICE ne répond pas : {e}"

# Test 5 - ALICE carte vivante

def test_alice_carte():
    carte_path = "/home/alice/carte-vivante/cartes.json"
    assert os.path.exists(carte_path), f"Carte introuvable : {carte_path}"
    with open(carte_path, "r") as f:
        data = json.load(f)
    assert "zones" in data or "noeuds" in data, "Carte mal formée"
    print("✅ Carte vivante OK")

# Test 6 - ALICE OCR

def test_alice_ocr():
    try:
        result = subprocess.run(["tesseract", "--version"], capture_output=True, text=True, timeout=5)
        assert result.returncode == 0
        print("✅ Tesseract OK")
    except Exception as e:
        assert False, f"Tesseract manquant : {e}"


if __name__ == "__main__":
    test_alice_memory()
    test_alice_routeur_health()
    test_alice_carte()
    test_alice_ocr()
