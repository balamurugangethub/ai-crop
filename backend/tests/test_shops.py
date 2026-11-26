import pytest

from app import shops


def test_haversine_known_distance():
    # Chennai Central to Madurai Junction is roughly 420 km in a straight line
    d = shops.haversine_m(13.0827, 80.2752, 9.9195, 78.1193)
    assert 410_000 < d < 430_000


def test_invalid_coordinates(client):
    r = client.get("/api/shops?lat=200&lon=10")
    assert r.status_code == 422 and r.json()["detail"] == "invalid_coordinates"


def test_unreachable_service_reports_error_not_fake_data(client, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "OVERPASS_URLS", ["https://127.0.0.1:9/api/interpreter"])
    monkeypatch.setattr(config, "NOMINATIM_URL", "https://127.0.0.1:9")  # fallback also down
    shops._cache.clear()
    r = client.get("/api/shops?lat=10.78&lon=79.13&radius=5000")
    assert r.status_code == 503 and r.json()["detail"] == "shop_service_unavailable"


def test_geocode_validation(client):
    assert client.get("/api/geocode?q=a").json()["detail"] == "invalid_location_query"


@pytest.mark.network
def test_live_geocode_tamil_nadu_town():
    res = shops.geocode("Thanjavur, Tamil Nadu")
    assert res and 10 < res[0]["lat"] < 11.5 and 78.5 < res[0]["lon"] < 80


@pytest.mark.network
def test_live_shop_search_returns_only_osm_data():
    res = shops.search_shops(13.0827, 80.2707, 20000)  # Chennai
    assert res["source"].startswith("OpenStreetMap")
    for s in res["shops"]:
        assert s["osm_url"].startswith("https://www.openstreetmap.org/")
        assert s["stock_status"] == "unconfirmed"
        assert s["distance_m"] <= 20000 * 1.05
