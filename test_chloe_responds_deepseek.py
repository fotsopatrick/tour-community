import re
import requests

BASE = "http://127.0.0.1:8071"


def _odoo_session():
    """Session Odoo authentifiée.

    Pièges contournés :
    - tour_cookie_secure force `Secure` sur session_id => en HTTP local, requests
      ne renvoie jamais ce cookie. On porte donc le cookie en en-tête à la main.
    - La route chat exige un CSRF token lié à la session (lisible sur /web).
    """
    s = requests.Session()
    r = s.post(f"{BASE}/web/session/authenticate",
               json={"jsonrpc": "2.0", "id": None,
                     "params": {"db": "odoo", "login": "admin",
                                "password": "admin"}}, timeout=10)
    r.raise_for_status()
    assert r.json().get("result", {}).get("uid"), "authentification échouée"
    sid = s.cookies.get("session_id")
    headers = {"Cookie": f"session_id={sid}"}

    rp = s.get(f"{BASE}/web", headers=headers, timeout=10)
    m = re.search(r'csrf_token:\s*"([^"]+)"', rp.text)
    assert m, "csrf_token introuvable"
    return s, headers, m.group(1)


def test_chloe_responds():
    s, headers, token = _odoo_session()
    payload = {"texte": "Dis-moi bonjour en français."}
    r = s.post(f"{BASE}/community/chat/message",
               headers=headers,
               json={"jsonrpc": "2.0", "id": None,
                     "params": {**payload, "csrf_token": token}},
               timeout=20)
    assert r.status_code == 200, f"Erreur HTTP {r.status_code}"
    data = r.json()
    print("Réponse de Chloé:", data)
    result = data.get("result", data)
    assert isinstance(result, dict), f"réponse inattendue: {data}"
    if "erreur" in result:
        raise AssertionError(f"Chloé a renvoyé une erreur: {result['erreur']}")
    assert "reponse" in result or "message" in result, "format de réponse inattendu"
    print("✅ Chloé répond :", result.get("reponse") or result.get("message"))


if __name__ == "__main__":
    test_chloe_responds()
