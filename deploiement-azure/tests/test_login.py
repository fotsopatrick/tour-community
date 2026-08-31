#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_login.py — Vérifie la connexion Odoo de la Tour (parcours navigateur).

Parcours réel : GET /web/login (jeton CSRF) -> POST login -> redirection 303
vers /web -> page d'accueil authentifiée -> droits administrateur.
"""
import re
import sys
import requests

URL = "http://20.97.179.141"
LOGIN = "admin"
PASSWORD = "admin"


def test_login():
    s = requests.Session()

    # 1. La page de connexion répond et porte le jeton CSRF.
    r = s.get(URL + "/web/login", timeout=30)
    assert r.status_code == 200, "GET /web/login -> HTTP %s" % r.status_code
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
    assert m, "jeton CSRF introuvable dans la page de connexion"
    csrf = m.group(1)

    # 2. Le formulaire se soumet avec la session (cookies) et redirige.
    r = s.post(URL + "/web/login", data={
        "csrf_token": csrf,
        "login": LOGIN,
        "password": PASSWORD,
        "redirect": "/web",
    }, timeout=30, allow_redirects=False)
    assert r.status_code == 303, "POST /web/login -> HTTP %s" % r.status_code
    assert "/web" in r.headers.get("Location", ""), "redirection inattendue"

    # 3. La redirection mène à la page d'accueil authentifiée.
    r = s.get(URL + "/web", timeout=30)
    assert r.status_code == 200, "GET /web -> HTTP %s" % r.status_code
    assert "Mitchell Admin" in r.text, "nom de l'utilisateur absent de la session"
    assert '"uid": 2' in r.text, "uid 2 (admin) absent de la session"

    # 4. Les droits administrateur sont actifs.
    assert '"is_admin": true' in r.text, "is_admin absent de la session"

    print("OK — connexion admin reussie, redirection vers /web, droits admin actifs")
    return s


if __name__ == "__main__":
    test_login()
    print("test_login.py : PASS")