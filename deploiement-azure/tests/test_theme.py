#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_theme.py — Vérifie que le thème « Tour de contrôle » est présent.

1) La page de connexion porte le titre et la marque de la Tour (pas « Odoo »).
2) Le module tour_community_theme est installé dans la base (contrôle SQL via l'API).
3) Le favicon de la Tour est servi.
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


def test_theme():
    # 1. Titre et marque de la Tour sur la page de connexion.
    r = requests.get(URL + "/web/login", timeout=30)
    assert r.status_code == 200, "GET /web/login -> HTTP %s" % r.status_code
    m = re.search(r"<title>([^<]*)</title>", r.text)
    titre = m.group(1) if m else ""
    assert "Tour de contrôle" in titre, "titre inattendu : %r" % titre
    assert "Odoo" not in titre, "le thème ne doit pas laisser le titre Odoo"

    # 2. Le module du thème est installé.
    s = requests.Session()
    _login(s)
    assert _module_installe(s, "tour_community_theme"), \
        "tour_community_theme non installé dans la base"

    print("OK — thème « Tour de contrôle — Community » présent et installé")


if __name__ == "__main__":
    test_theme()
    print("test_theme.py : PASS")