import requests


def test_azure_vm_responds():
    try:
        r = requests.get("http://20.97.179.141", timeout=10)
        assert r.status_code == 200, f"Code HTTP {r.status_code}"
        print("✅ VM Azure répond (Tour accessible)")
    except Exception as e:
        assert False, f"VM Azure injoignable : {e}"


if __name__ == "__main__":
    test_azure_vm_responds()
