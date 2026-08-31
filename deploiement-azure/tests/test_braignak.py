#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_braignak.py — Vérifie que Braignak (tour_community_braignak) est opérationnel.

1) Le module est installé dans la base.
2) La page /community/braignak répond et porte le nom de Braignak.
3) La route /community/braignak/observer répond (JSON-RPC authentifié).
   Sans clé DeepSeek configurée, elle renvoie le message « clé API non
   configurée » : preuve que la route, l'auth et le routage fonctionnent.
"""
import re
import requests

URL = "http://20.97.179.141"


def _login(s):
    r = s.get(URL + "/web/login", timeout=30)
    csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text).group(1)
    s.post(URL + "/web/login", data={
        "csrf_token": csrf, "login": "admin", "password": "admin",
        "redirect": "/web",
    }, timeout=30)


def _module_installe(s, nom):
    r = s.post(URL + "/web/dataset/call_kw", timeout=30, json={
        "jsonrpc": "2.0", "method": "call", "params": {
            "model": "ir.module.module",
            "method": "search_read",
            "args": [[["name", "=", nom]]],
            "kwargs": {"fields": ["name", "state"]},
        },
    })
    data = r.json().get("result") or []
    return any(x.get("name") == nom and x.get("state") == "installed" for x in data)


def test_braignak():
    s = requests.Session()
    _login(s)

    # 1. Module installé.
    assert _module_installe(s, "tour_community_braignak"), \
        "tour_community_braignak non installé dans la base"

    # 2. Page de Braignak accessible et identifiée.
    r = s.get(URL + "/community/braignak", timeout=30)
    assert r.status_code == 200, "GET /community/braignak -> HTTP %s" % r.status_code
    assert "Braignak" in r.text, "le nom de Braignak est absent de la page"

    # 3. Route d'observation répond (JSON-RPC, auth user).
    r = s.post(URL + "/community/braignak/observer", timeout=60, json={
        "jsonrpc": "2.0", "method": "call",
        "params": {"cible": "https://example.com"},
    })
    assert r.status_code == 200, \
        "POST /community/braignak/observer -> HTTP %s" % r.status_code
    result = r.json().get("result") or {}
    # Sans clé : erreur explicite = la route traite bien la demande.
    assert "erreur" in result or "reponse" in result, \
        "réponse inattendue : %s" % result

    print("OK — Braignak : module installé, page présente, route d'observation répond")
    print("    (réponse: %s)" % (result.get("erreur") or result.get("reponse") or "")[:60])


if __name__ == "__main__":
    test_braignak()
    print("test_braignak.py : PASS")