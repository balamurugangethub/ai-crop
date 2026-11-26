import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
IMAGES = Path(__file__).resolve().parent / "images"

# Isolated database / upload folder per test session
_tmp = tempfile.mkdtemp(prefix="cropdoctor-test-")
os.environ["CROP_DOCTOR_DATA_DIR"] = _tmp
os.environ["CROP_DOCTOR_DB"] = str(Path(_tmp) / "test.sqlite3")
os.environ["CROP_DOCTOR_FRONTEND_DIST"] = str(Path(_tmp) / "no-frontend")


def pytest_addoption(parser):
    parser.addoption("--network", action="store_true", help="run tests that call live OpenStreetMap services")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--network"):
        return
    skip = pytest.mark.skip(reason="needs --network (live OpenStreetMap)")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


_counter = [0]


@pytest.fixture
def auth_headers(client):
    _counter[0] += 1
    phone = f"9{_counter[0]:09d}"
    r = client.post("/api/auth/register", json={"name": "Test Farmer", "phone": phone, "pin": "1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
