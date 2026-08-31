import requests

BASE = "http://127.0.0.1:8071"


def _odoo_session():
    """Retourne une session Odoo authentifiée via JSON-RPC."""
    session = requests.Session()
    r = session.post(
        f"{BASE}/web/session/authenticate",
        json={
            "jsonrpc": "2.0",
            "id": None,
            "params": {
                "db": "odoo",
                "login": "admin",
                "password": "admin",
            },
        },
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    result = data.get("result") or {}
    # uid présent = authentification réussie
    assert result.get("uid"), f"Authentification échouée : {data}"
    return session


def test_tour_dashboard():
    try:
        r = requests.get(f"{BASE}/tour/dashboard", timeout=5)
        assert r.status_code == 200
        print("✅ Tour dashboard OK")
    except Exception as e:
        assert False, f"Tour Community ne répond pas : {e}"


def test_chloe_responds():
    session = _odoo_session()

    payload = {"texte": "Dis-moi bonjour"}
    r = session.post(
        f"{BASE}/community/chat/message",
        json={"jsonrpc": "2.0", "id": None, "params": payload},
        timeout=15,
    )
    assert r.status_code == 200, f"Chloé HTTP {r.status_code}"
    data = r.json()
    print("Réponse JSON reçue:", data)
    result = data.get("result", data)
    assert isinstance(result, dict), f"Réponse inattendue : {data}"
    assert (
        "reponse" in result or "message" in result or "response" in result
        or "reponse" in data or "message" in data
    ), f"Chloé n'a pas répondu : {data}"
    print("✅ Chloé répond")


if __name__ == "__main__":
    test_tour_dashboard()
    test_chloe_responds()
