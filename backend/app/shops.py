"""Real agricultural-shop discovery using OpenStreetMap.

* Geocoding of a typed village/town: Nominatim.
* Shop search: Overpass API. We query
    - shop=agrarian (OSM tag for agricultural supplies: seeds, fertiliser, pesticides, tools)
    - shop=garden_centre / shop=farm with seed/fertiliser related tags
    - any shop/craft/office whose name contains agri / agro / fertiliser / seeds /
      pesticide / krishi / உரம் / விதை etc. (marked "matched by name").
Only data returned by OpenStreetMap is shown. Distance is computed from the
coordinates. Stock / availability is never known and is always reported as
unconfirmed.
"""
import math
import re
import time
from urllib.parse import quote

import httpx

from . import config

NAME_PATTERN = ("agri|agro|fertili[sz]er|fertili[sz]ers|seeds?|pesticide|krishi|kisan|"
                "farm supply|farm supplies|உரம்|உரக்கடை|விதை|வேளாண்|பூச்சிக்கொல்லி|खाद|बीज|कृषि")

_cache: dict = {}
_last_nominatim = [0.0]


class ShopServiceError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.code = code
        self.detail = detail


def _client() -> httpx.Client:
    return httpx.Client(timeout=config.HTTP_TIMEOUT_S,
                        headers={"User-Agent": config.HTTP_USER_AGENT, "Accept-Language": "en,ta"})


def _cached(key, ttl, fn):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (now, val)
    return val


def geocode(query: str) -> list[dict]:
    query = (query or "").strip()
    if not (2 <= len(query) <= 200):
        raise ShopServiceError("invalid_location_query")

    def run():
        # Nominatim policy: max 1 request per second
        wait = 1.0 - (time.time() - _last_nominatim[0])
        if wait > 0:
            time.sleep(wait)
        _last_nominatim[0] = time.time()
        try:
            with _client() as c:
                r = c.get(f"{config.NOMINATIM_URL}/search",
                          params={"q": query, "format": "jsonv2", "limit": 5, "countrycodes": "in",
                                  "addressdetails": 0})
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPError as e:
            raise ShopServiceError("geocoding_unavailable", str(e))
        return [{"name": d.get("display_name"), "lat": float(d["lat"]), "lon": float(d["lon"]),
                 "type": d.get("type")} for d in data]

    return _cached(("geo", query.lower()), 24 * 3600, run)


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _overpass_query(lat, lon, radius):
    around = f"(around:{radius},{lat:.6f},{lon:.6f})"
    return f"""
[out:json][timeout:15];
(
  nwr["shop"="agrarian"]{around};
  nwr["shop"~"^(garden_centre|farm|hardware)$"]["name"~"{NAME_PATTERN}",i]{around};
  nwr["shop"]["name"~"{NAME_PATTERN}",i]{around};
  nwr["craft"="agricultural_engines"]{around};
  nwr["office"="government"]["name"~"agricultur|krishi|வேளாண்",i]{around};
);
out center tags;
"""


def _address(tags: dict) -> str | None:
    if tags.get("addr:full"):
        return tags["addr:full"]
    parts = [tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:place"),
             tags.get("addr:suburb"), tags.get("addr:village"), tags.get("addr:city"),
             tags.get("addr:district"), tags.get("addr:postcode")]
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else None


def _categories(tags: dict) -> list[str]:
    text = " ".join(str(v).lower() for k, v in tags.items()
                    if k in ("name", "name:en", "name:ta", "description", "agrarian", "shop", "trade"))
    cats = []
    for cat, words in {"seeds": ("seed", "விதை"), "fertilizer": ("fertili", "உரம்", "manure"),
                       "pesticide": ("pesticide", "agrochemical", "பூச்சிக்கொல்லி"),
                       "tools": ("tools", "machinery", "engine", "equipment", "tractor"),
                       "feed": ("feed", "fodder")}.items():
        if any(w in text for w in words):
            cats.append(cat)
    return cats


NOMINATIM_QUERIES = ("[shop=agrarian]", "fertilizer", "seeds", "agro", "உரம்")
_NOMINATIM_ADDR = {"road": "addr:street", "suburb": "addr:suburb", "village": "addr:village",
                   "town": "addr:city", "city": "addr:city", "state_district": "addr:district",
                   "postcode": "addr:postcode"}


def _nominatim_get(c, params):
    wait = 1.0 - (time.time() - _last_nominatim[0])  # usage policy: max 1 request / second
    if wait > 0:
        time.sleep(wait)
    _last_nominatim[0] = time.time()
    r = c.get(f"{config.NOMINATIM_URL}/search", params=params)
    r.raise_for_status()
    return r.json()


def _nominatim_search(lat, lon, radius_m):
    dlat = radius_m / 111_320
    dlon = radius_m / (111_320 * max(math.cos(math.radians(lat)), 0.01))
    viewbox = f"{lon - dlon},{lat + dlat},{lon + dlon},{lat - dlat}"
    elements, failures = {}, 0
    with _client() as c:
        for q in NOMINATIM_QUERIES:
            try:
                rows = _nominatim_get(c, {"q": q, "format": "jsonv2", "viewbox": viewbox, "bounded": 1,
                                          "limit": 50, "extratags": 1, "addressdetails": 1})
            except (httpx.HTTPError, ValueError):
                failures += 1
                continue
            for row in rows:
                if row.get("category") not in ("shop", "office", "craft"):
                    continue
                if row.get("category") == "office" and not re.search("agri|krishi|வேளாண்", row.get("name") or "", re.I):
                    continue
                if row.get("category") == "shop" and row.get("type") != "agrarian" and \
                        not re.search(NAME_PATTERN, row.get("name") or "", re.I):
                    continue
                tags = dict(row.get("extratags") or {})
                if row.get("name"):
                    tags.setdefault("name", row["name"])
                tags[row["category"]] = row["type"]
                for k, tag in _NOMINATIM_ADDR.items():
                    v = (row.get("address") or {}).get(k)
                    if v and tag not in tags:
                        tags[tag] = v
                osm_type = {"N": "node", "W": "way", "R": "relation"}.get(row.get("osm_type", "")[:1].upper(),
                                                                          row.get("osm_type"))
                elements[(osm_type, row["osm_id"])] = {
                    "type": osm_type, "id": row["osm_id"], "lat": float(row["lat"]), "lon": float(row["lon"]),
                    "tags": tags}
    if failures == len(NOMINATIM_QUERIES):
        raise ShopServiceError("shop_service_unavailable", "all nominatim queries failed")
    out = []
    for el in elements.values():
        if el["type"] != "node":
            el["center"] = {"lat": el.pop("lat"), "lon": el.pop("lon")}
        out.append(el)
    return {"elements": out, "_server": f"{config.NOMINATIM_URL} (fallback)"}


def search_shops(lat: float, lon: float, radius_m: int = 10000) -> dict:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ShopServiceError("invalid_coordinates")
    radius_m = int(max(1000, min(radius_m, config.SHOP_SEARCH_MAX_RADIUS_M)))
    key = ("shops", round(lat, 3), round(lon, 3), radius_m)

    def run():
        query = _overpass_query(lat, lon, radius_m)
        errors = []
        with _client() as c:
            for url in config.OVERPASS_URLS:
                try:
                    r = c.get(url, params={"data": query}, timeout=config.OVERPASS_TIMEOUT_S)
                    if r.status_code in (429, 504):
                        errors.append(f"{url}: busy HTTP {r.status_code}")
                        continue
                    r.raise_for_status()
                    data = r.json()
                    data["_server"] = url
                    return data
                except (httpx.HTTPError, ValueError) as e:
                    errors.append(f"{url}: {type(e).__name__}")
        # Fallback: Nominatim tag / keyword search inside the bounding box (still real OSM data)
        try:
            return _nominatim_search(lat, lon, radius_m)
        except ShopServiceError as e:
            errors.append(f"nominatim: {e.detail}")
        code = "shop_service_busy" if errors and all("busy" in e for e in errors) else "shop_service_unavailable"
        raise ShopServiceError(code, "; ".join(errors))

    data = _cached(key, 15 * 60, run)
    shops, seen = [], set()
    for el in data.get("elements", []):
        tags = el.get("tags") or {}
        name = tags.get("name") or tags.get("name:en") or tags.get("name:ta")
        if el["type"] == "node":
            slat, slon = el.get("lat"), el.get("lon")
        else:
            center = el.get("center") or {}
            slat, slon = center.get("lat"), center.get("lon")
        if slat is None or slon is None:
            continue
        if haversine_m(lat, lon, slat, slon) > radius_m * 1.05:
            continue
        uid = f"{el['type']}/{el['id']}"
        if uid in seen:
            continue
        seen.add(uid)
        dist = haversine_m(lat, lon, slat, slon)
        match = "agrarian_tag" if tags.get("shop") == "agrarian" else (
            "government_office" if tags.get("office") == "government" else "name_match")
        shops.append({
            "id": uid,
            "name": name,  # may be None: OSM has the shop but no name
            "name_ta": tags.get("name:ta"),
            "lat": slat, "lon": slon,
            "distance_m": round(dist),
            "address": _address(tags),
            "phone": tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile"),
            "opening_hours": tags.get("opening_hours"),
            "website": tags.get("website") or tags.get("contact:website"),
            "osm_type": tags.get("shop") or tags.get("office") or tags.get("craft"),
            "categories": _categories(tags),
            "match_reason": match,
            "stock_status": "unconfirmed",
            "osm_url": f"https://www.openstreetmap.org/{uid}",
            "directions": {
                "google": f"https://www.google.com/maps/dir/?api=1&destination={slat},{slon}",
                "osm": (f"https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route="
                        f"{lat}%2C{lon}%3B{slat}%2C{slon}"),
            },
        })
    shops.sort(key=lambda s: s["distance_m"])
    return {
        "center": {"lat": lat, "lon": lon},
        "radius_m": radius_m,
        "count": len(shops),
        "shops": shops,
        "source": "OpenStreetMap contributors via Overpass API (ODbL)",
        "server": data.get("_server"),
        "attribution_url": "https://www.openstreetmap.org/copyright",
        "query_maps_link": f"https://www.google.com/maps/search/{quote('agricultural fertilizer shop')}/@{lat},{lon},13z",
    }
