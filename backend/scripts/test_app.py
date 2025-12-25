import requests
import pytest

BASE_URL = "http://localhost:5000"


def _api_available() -> bool:
    try:
        res = requests.get(f"{BASE_URL}/blockchain", timeout=2)
        return res.ok
    except requests.RequestException:
        return False


def get_blockchain():
    resp = requests.get(f"{BASE_URL}/blockchain", timeout=5)
    resp.raise_for_status()
    return resp.json()


def get_wallet_info():
    resp = requests.get(f"{BASE_URL}/wallet/info", timeout=5)
    resp.raise_for_status()
    return resp.json()


pytestmark = pytest.mark.skipif(
    not _api_available(),
    reason="HTTP API not running at localhost:5000; start backend.app to run this smoke test"
)


def test_api_smoke():
    chain = get_blockchain()
    assert isinstance(chain, list)

    info = get_wallet_info()
    assert isinstance(info, dict)
    assert "address" in info
    assert "balance" in info
