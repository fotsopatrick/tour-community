#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_chloe.py — Vérifie que Chloé (tour_community_chat) est opérationnelle.

1) Le module est installé dans la base.
2) La page /community/chat répond et porte le nom de Chloé.
3) La route de chat /community/chat/message répond (JSON-RPC authentifié).
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


def test_chloe():
    s = requests.Session()
    _login(s)

    # 1. Module installé.
    assert _module_installe(s, "tour_community_chat"), \
        "tour_community_chat non installé dans la base"

    # 2. Page de Chloé accessible et identifiée.
    r = s.get(URL + "/community/chat", timeout=30)
    assert r.status_code == 200, "GET /community/chat -> HTTP %s" % r.status_code
    assert "Chloé" in r.text, "le nom de Chloé est absent de la page"

    # 3. Route de message répond (JSON-RPC, auth user).
    r = s.post(URL + "/community/chat/message", timeout=60, json={
        "jsonrpc": "2.0", "method": "call",
        "params": {"texte": "bonjour", "historique": []},
    })
    assert r.status_code == 200, "POST /community/chat/message -> HTTP %s" % r.status_code
    result = r.json().get("result") or {}
    # Sans clé : erreur explicite = la route traite bien la demande.
    assert "erreur" in result or "reponse" in result, \
        "réponse inattendue : %s" % result

    print("OK — Chloé : module installé, page présente, route de chat répond")
    print("    (réponse: %s)" % (result.get("erreur") or result.get("reponse") or "")[:60])


if __name__ == "__main__":
    test_chloe()
    print("test_chloe.py : PASS")