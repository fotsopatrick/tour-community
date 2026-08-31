#!/usr/bin/env python3
# benchmark_alice.py – Compare les performances local vs cloud

import time
import requests

LOCAL_URL = "http://192.168.1.61:8000"
CLOUD_URL = "http://alice-demo-2026.eastus2.azurecontainer.io:8000"

def bench(url, n=5):
    temps = []
    for _ in range(n):
        start = time.time()
        try:
            r = requests.post(f"{url}/chat", json={"message": "Explique-moi le ratio de levier CRR en une phrase."}, timeout=30)
            if r.status_code == 200:
                dt = time.time() - start
                temps.append(dt)
                print(f"    requête {_+1}: {dt:.2f}s  -> {r.json().get('reponse','')[:55]!r}")
            else:
                print(f"    requête {_+1}: HTTP {r.status_code}")
        except Exception as e:
            print(f"    requête {_+1}: err {e}")
        time.sleep(0.5)
    if temps:
        return sum(temps) / len(temps)
    return None

print("⏱️ Benchmark ALICE — temps de réponse moyen (5 requêtes)")
print("Cerveau : SAME (Azure OpenAI gpt-5-mini) sur local et cloud.\n")
local_avg = bench(LOCAL_URL)
cloud_avg = bench(CLOUD_URL)
print()
print(f"  LOCAL  : {local_avg:.2f}s" if local_avg else "  LOCAL  : ❌")
print(f"  CLOUD  : {cloud_avg:.2f}s" if cloud_avg else "  CLOUD  : ❌")
if local_avg and cloud_avg:
    ratio = cloud_avg / local_avg
    print(f"  Ratio cloud/local : {ratio:.2f}x")
    if ratio < 1:
        print("  → CLOUD plus rapide que local.")
    elif ratio > 1:
        print("  → LOCAL plus rapide que cloud.")
    else:
        print("  → Équivalents.")