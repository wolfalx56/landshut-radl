import httpx
import math
import random
from typing import Any
import json
import aiosqlite
from pathlib import Path

# Landshut Zentrum als Fallback-Startpunkt
LANDSHUT_LAT = 48.5369
LANDSHUT_LON = 12.1525

# Overpass: Interessante Ziele im Umkreis finden

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
OVERPASS_HEADERS = {
    "User-Agent": "LandshutRadl/1.0 (contact: wolfalx@gmx.de)",
    "Content-Type": "application/x-www-form-urlencoded",
}

# BRouter: spezialisierter Fahrrad-Router, meidet Hauptstraßen, liefert Höhenprofil
BROUTER_URL = "https://brouter.de/brouter"
BROUTER_PROFILE = "safety"  # Freizeitradeln, meidet Bundesstraßen/Hauptstraßen ohne Radweg sehr aggressiv

# Modus-abhaengige Einstellungen: Profil, Schnitt-Tempo, max. Zielentfernung
MODES = {
    "bike":  {"profile": "safety",      "speed_kmh": 15.0, "max_dest_km": 40.0},
    "hike":  {"profile": "hiking-beta", "speed_kmh": 4.0,  "max_dest_km": 15.0},
}

# km/h Durchschnitt für Zeitschätzung (gemütliches Radeln)
AVG_SPEED_KMH = 15.0

DEST_DB_PATH = Path("/app/data/cache/destinations.db")


async def _ensure_dest_db():
    DEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DEST_DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dest_cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT,
                updated_at INTEGER DEFAULT (strftime('%s','now'))
            )
        """)
        await db.commit()

async def find_destinations(lat: float, lon: float, min_km: float, max_km: float) -> list[dict]:
    """Sucht interessante Radel-Ziele im gewünschten Entfernungsradius via Overpass."""
    await _ensure_dest_db()
    cache_key = f"{lat:.3f}_{lon:.3f}_{int(max_km)}"

    async with aiosqlite.connect(DEST_DB_PATH) as db:
        async with db.execute(
            "SELECT data FROM dest_cache WHERE cache_key=? AND (strftime('%s','now') - updated_at) < 604800",
            (cache_key,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                return json.loads(row[0])

    min_m = min_km * 1000
    max_m = max_km * 1000

    query = f"""
    [out:json][timeout:55];
    (
      node["natural"="peak"](around:{max_m},{lat},{lon});
      node["tourism"="viewpoint"](around:{max_m},{lat},{lon});
      node["natural"="water"]["water"="lake"](around:{max_m},{lat},{lon});
      node["amenity"="biergarten"](around:{max_m},{lat},{lon});
      node["historic"="castle"](around:{max_m},{lat},{lon});
      node["historic"="ruins"](around:{max_m},{lat},{lon});
      node["tourism"="picnic_site"](around:{max_m},{lat},{lon});
    );
    out 50;
    """

    from urllib.parse import urlencode
    payload = urlencode({"data": query})
    data = None
    last_error = None
    async with httpx.AsyncClient(timeout=60) as client:
        for url in OVERPASS_URLS:
            try:
                resp = await client.post(url, content=payload, headers=OVERPASS_HEADERS)
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_error = f"{resp.status_code} von {url}"
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_error = str(e)
                continue

    if data is None:
        async with aiosqlite.connect(DEST_DB_PATH) as db:
            async with db.execute(
                "SELECT data FROM dest_cache WHERE cache_key=?", (cache_key,)
            ) as cur:
                row = await cur.fetchone()
                if row:
                    return json.loads(row[0])
        raise RuntimeError(f"Overpass nicht erreichbar: {last_error}")

    destinations = []
    for el in data.get("elements", []):
        el_lat = el.get("lat")
        el_lon = el.get("lon")
        if not el_lat or not el_lon:
            continue

        dist = _haversine_km(lat, lon, el_lat, el_lon)
        if dist < min_km:
            continue

        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        if not name:
            continue  # Ziele ohne echten Namen überspringen

        website = (
            tags.get("website") or
            tags.get("contact:website") or
            tags.get("url") or
            tags.get("contact:url")
        )
        description = tags.get("description") or tags.get("note")

        destinations.append({
            "name": name,
            "lat": el_lat,
            "lon": el_lon,
            "dist_km": round(dist, 1),
            "type": _type_label(tags),
            "website": website,
            "description": description,
        })

    async with aiosqlite.connect(DEST_DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO dest_cache (cache_key, data) VALUES (?,?)",
            (cache_key, json.dumps(destinations))
        )
        await db.commit()

    return destinations

async def get_route(from_lat: float, from_lon: float, to_lat: float, to_lon: float,
                    mode: str = "bike") -> dict | None:
    """Holt Route via BRouter. mode=bike -> safety-Profil, mode=hike -> hiking-beta."""
    cfg = MODES.get(mode, MODES["bike"])
    params = {
        "lonlats": f"{from_lon},{from_lat}|{to_lon},{to_lat}|{from_lon},{from_lat}",
        "profile": cfg["profile"],
        "alternativeidx": "1",
        "format": "geojson",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(BROUTER_URL, params=params)
            if resp.status_code != 200:
                return None
            data = resp.json()
        except Exception:
            return None

    features = data.get("features")
    if not features:
        return None

    feature = features[0]
    props = feature.get("properties", {})

    distance_m = float(props.get("track-length", 0))
    time_s = float(props.get("total-time", 0))

    if distance_m == 0:
        return None

    distance_km = distance_m / 1000
    # BRouter-Zeit ist optimistisch — eigene Schätzung als Untergrenze
    duration_min = max(int(time_s / 60), int(distance_km / cfg["speed_kmh"] * 60))

    return {
        "geometry": feature["geometry"],  # enthält Höhendaten als 3. Koordinate
        "distance_km": round(distance_km, 1),
        "duration_min": duration_min,
    }


async def generate_tour_options(lat: float, lon: float, duration_min: int,
                                mode: str = "bike") -> list[dict]:
    """
    Generiert 3 Tour-Optionen mit unterschiedlichen Zielen.
    Ziel-Distanz wird aus der gewünschten Dauer und dem Modus berechnet.
    """
    cfg = MODES.get(mode, MODES["bike"])

    # Ziel-Distanz (Hinweg = halbe Gesamtdistanz)
    total_km = (duration_min / 60) * cfg["speed_kmh"]
    half_km = total_km / 2

    # Suchradius: ±40% um die Halbstrecke
    min_km = max(1.0 if mode == "hike" else 2.0, half_km * 0.6)
    max_km = min(cfg["max_dest_km"], half_km * 1.4)

    destinations = await find_destinations(lat, lon, min_km, max_km)

    if not destinations:
        raise ValueError(f"Keine Ziele zwischen {min_km:.0f} und {max_km:.0f} km gefunden.")

    # Mische und nehme bis zu 6 Kandidaten
    random.shuffle(destinations)
    candidates = destinations[:6]

    tours = []
    for dest in candidates:
        route = await get_route(lat, lon, dest["lat"], dest["lon"], mode)
        if not route:
            continue

        tours.append({
            "mode": mode,
            "destination": dest["name"],
            "destination_type": dest["type"],
            "destination_lat": dest["lat"],
            "destination_lon": dest["lon"],
            "destination_website": dest.get("website"),
            "destination_description": dest.get("description"),
            "distance_km": route["distance_km"],
            "duration_min": route["duration_min"],
            "geometry": route["geometry"],
        })

        if len(tours) >= 3:
            break

    return tours


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def _type_label(tags: dict) -> str:
    mapping = {
        "peak": "Gipfel",
        "viewpoint": "Aussichtspunkt",
        "lake": "See",
        "biergarten": "Biergarten",
        "castle": "Burg/Schloss",
        "ruins": "Ruine",
        "nature_reserve": "Naturschutzgebiet",
        "picnic_site": "Picknickplatz",
    }
    for key, label in mapping.items():
        if tags.get("natural") == key or tags.get("tourism") == key or tags.get("amenity") == key or tags.get("historic") == key or tags.get("leisure") == key:
            return label
    return "Sehenswürdigkeit"
