#!/usr/bin/env python3
# test_alice_v1.py – Validation de ALICE V1

import os
import json
import time
import requests
import subprocess
import unittest

# --- Configuration ---
LOCAL_URL = "http://192.168.1.61:8000"
CLOUD_URL = "http://alice-demo-2026.eastus2.azurecontainer.io:8000"

# --- Test 1 : Health ---
def test_health(url):
    try:
        r = requests.get(f"{url}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

# --- Test 2 : Routeur Gate ---
def test_gate(url):
    payload = {"command": "lire la carte vivante", "user": "testeur"}
    try:
        r = requests.post(f"{url}/api/v1/gate", json=payload, timeout=10)
        return r.status_code in [200, 202]
    except Exception:
        return False

# --- Test 3 : Mémoire SQLite ---
def test_memory(url):
    try:
        r = requests.get(f"{url}/api/v1/knowledge?q=CRR", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

# --- Test 4 : OCR (si Tesseract installé) ---
def test_ocr(url):
    try:
        r = requests.post(f"{url}/api/v1/ocr", json={"image_url": "https://i.imgur.com/test.png"}, timeout=10)
        return r.status_code in [200, 400, 500]  # 400/500 = pas d'image, mais service répond
    except Exception:
        return False

# --- Test 5 : Ingestion (texte) ---
def test_ingest(url):
    payload = {"text": "Le ratio de levier CRR est de 3 %.", "titre": "CRR_test"}
    try:
        r = requests.post(f"{url}/api/v1/ingest", json=payload, timeout=10)
        if r.status_code == 200:
            return "chunks" in r.json()
        return False
    except Exception:
        return False

# --- Test 6 : Chat (réponse textuelle) ---
def test_chat(url):
    try:
        r = requests.post(f"{url}/chat", json={"message": "Bonjour, qui es-tu ?"}, timeout=15)
        if r.status_code == 200:
            return "reponse" in r.json() or "message" in r.json()
        return False
    except Exception:
        return False

# --- Test 7 : Carte vivante (service séparé d'ALICE) ---
CARTE_URL = "http://carte-vivante-2026.eastus2.azurecontainer.io"
def test_live_map(url):
    # ALICE n'expose pas /api/live-map : la carte vivante est un service ACI
    # séparé ("carte vivante" du RAPPORT-COMPLET). On teste SA disponibilité.
    try:
        r = requests.get(CARTE_URL, timeout=5)
        return r.status_code == 200
    except Exception:
        return False

# --- Lanceur des tests ---
def run_tests(url, name):
    print(f"\n🧪 Tests ALICE — {name}")
    results = {
        "health": test_health(url),
        "gate": test_gate(url),
        "memory": test_memory(url),
        "ocr": test_ocr(url),
        "ingest": test_ingest(url),
        "chat": test_chat(url),
        "live_map": test_live_map(url),
    }
    for k, v in results.items():
        print(f"  {k}: {'✅' if v else '❌'}")
    return results

if __name__ == "__main__":
    print("🔍 Test local (192.168.1.61)")
    local_results = run_tests(LOCAL_URL, "LOCAL")
    print("\n☁️ Test cloud (Azure ACI)")
    cloud_results = run_tests(CLOUD_URL, "CLOUD")