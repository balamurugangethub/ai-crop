"""End-to-end diagnosis through the HTTP API with the real trained model and
real held-out images (see tests/images/ATTRIBUTION.md)."""
import pytest

from conftest import IMAGES

SUPPORTED = sorted(p for p in IMAGES.glob("*___*.jpg"))
# Known, documented model error (see README "Known limitations"): this held-out early
# blight leaf is confidently predicted as late blight. strict=True makes the test
# fail loudly if a retrained model stops making this mistake, so the list stays true.
KNOWN_ERRORS = {"Tomato___Early_blight": "confidently misclassified as Tomato___Late_blight (0.985)"}
PARAMS = [pytest.param(p, marks=pytest.mark.xfail(reason=KNOWN_ERRORS[p.stem], strict=True))
          if p.stem in KNOWN_ERRORS else p for p in SUPPORTED]


def post(client, headers, path, lang="en"):
    with open(path, "rb") as f:
        return client.post("/api/diagnose", headers=headers, data={"lang": lang},
                           files={"image": (path.name, f, "image/jpeg")})


def test_model_info(client):
    info = client.get("/api/model").json()
    assert len(info["classes"]) == 13
    assert info["test_accuracy_supported_classes"] > 0.9


@pytest.mark.parametrize("path", PARAMS, ids=lambda p: p.stem)
def test_held_out_leaf_images(client, auth_headers, path):
    r = post(client, auth_headers, path)
    assert r.status_code == 200, r.text
    res = r.json()
    expected = path.stem.replace("Spider_mites_Two", "Spider_mites Two")
    # Honest check: the model must either be right, or say it is unsure. A confident
    # wrong answer counts as a failure.
    if res["status"] == "ok":
        assert res["disease"]["class_id"] == expected, (res["disease"]["class_id"], res["confidence"])
        assert res["confidence"] >= res["min_confidence"]
    else:
        assert res["status"] in ("uncertain", "unsupported")
        assert res["disease"] is None


def test_most_held_out_leaves_are_confidently_correct(client, auth_headers):
    ok = 0
    for path in SUPPORTED:
        res = post(client, auth_headers, path).json()
        expected = path.stem.replace("Spider_mites_Two", "Spider_mites Two")
        ok += res["status"] == "ok" and res["disease"]["class_id"] == expected
    assert ok >= 11, f"only {ok}/13 confidently correct"


def test_unsupported_tulip_photo_gets_no_disease(client, auth_headers):
    res = post(client, auth_headers, IMAGES / "ood_tulip.jpg").json()
    assert res["status"] == "unsupported"
    assert res["disease"] is None and res["candidates"] == []


def test_tamil_result_and_history(client, auth_headers):
    res = post(client, auth_headers, IMAGES / "Tomato___Late_blight.jpg", lang="ta").json()
    assert res["status"] == "ok"
    assert res["disease"]["language"] == "ta"
    assert "இலைக்கருகல்" in res["disease"]["name"]
    rid = res["report_id"]
    hist = client.get("/api/reports?lang=en", headers=auth_headers).json()
    assert hist[0]["id"] == rid and hist[0]["name"] == "Late blight"
    again = client.get(f"/api/reports/{rid}?lang=en", headers=auth_headers).json()
    assert again["disease"]["name"] == "Late blight"
    token = auth_headers["Authorization"].split()[1]
    img = client.get(f"/api/reports/{rid}/image?token={token}")
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    assert client.delete(f"/api/reports/{rid}", headers=auth_headers).status_code == 200
    assert client.get(f"/api/reports/{rid}", headers=auth_headers).status_code == 404


def test_rejected_upload_returns_reason(client, auth_headers):
    r = client.post("/api/diagnose", headers=auth_headers, files={"image": ("x.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 422 and r.json()["message"] == "not_an_image"


def test_other_users_cannot_see_reports(client, auth_headers):
    rid = post(client, auth_headers, IMAGES / "Potato___healthy.jpg").json()["report_id"]
    other = client.post("/api/auth/register", json={"name": "B", "phone": "9123456789", "pin": "9999"}).json()
    h2 = {"Authorization": f"Bearer {other['token']}"}
    assert client.get(f"/api/reports/{rid}", headers=h2).status_code == 404
