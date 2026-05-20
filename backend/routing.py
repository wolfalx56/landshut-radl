import httpx
import math
import random
from typing import Any

# Landshut Zentrum als Fallback-Startpunkt
LANDSHUT_LAT = 48.5369
LANDSHUT_LON = 12.1525

# Overpass: Interessante Ziele im Umkreis finden
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_HEADERS = {
    "User-Agent": "LandshutRadl/1.0 (contact: wolfalx@gmx.de)",
    "Content-Type": "application/x-www-form-urlencoded",
}

# BRouter: spezialisierter Fahrrad-Router, meidet Hauptstraßen, liefert Höhenprofil
BROUTER_URL = "https://brouter.de/brouter"
BROUTER_PROFILE = "safety"  # Freizeitradeln, meidet Bundesstraßen/Hauptstraßen ohne Radweg sehr aggressiv

# km/h Durchschnitt für Zeitschätzung (gemütliches Radeln)
AVG_SPEED_KMH = 15.0


async def find_destinations(lat: float, lon: float, min_km: float, max_km: float) -> list[dict]:
    """Sucht interessante Radel-Ziele im gewünschten Entfernungsradius via Overpass."""
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

    async with httpx.AsyncClient(timeout=60) as client:
        from urllib.parse import urlencode
        resp = await client.post(OVERPASS_URL, content=urlencode({"data": query}), headers=OVERPASS_HEADERS)
        resp.raise_for_status()
        data = resp.json()

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

    return destinations


async def get_route(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> dict | None:
    """Holt Fahrradroute via BRouter (safety-Profil: meidet Bundesstraßen/Hauptstraßen ohne Radweg, hat Höhenprofil)."""
    params = {
        "lonlats": f"{from_lon},{from_lat}|{to_lon},{to_lat}|{from_lon},{from_lat}",
        "profile": BROUTER_PROFILE,
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
    duration_min = max(int(time_s / 60), int(distance_km / AVG_SPEED_KMH * 60))

    return {
        "geometry": feature["geometry"],  # enthält Höhendaten als 3. Koordinate
        "distance_km": round(distance_km, 1),
        "duration_min": duration_min,
    }


async def generate_tour_options(lat: float, lon: float, duration_min: int) -> list[dict]:
    """
    Generiert 3 Tour-Optionen mit unterschiedlichen Zielen.
    Ziel-Distanz wird aus der gewünschten Dauer berechnet.
    """
    # Ziel-Distanz (Hinweg = halbe Gesamtdistanz)
    total_km = (duration_min / 60) * AVG_SPEED_KMH
    half_km = total_km / 2

    # Suchradius: ±40% um die Halbstrecke
    min_km = max(2.0, half_km * 0.6)
    max_km = min(40.0, half_km * 1.4)

    destinations = await find_destinations(lat, lon, min_km, max_km)

    if not destinations:
        raise ValueError(f"Keine Ziele zwischen {min_km:.0f} und {max_km:.0f} km gefunden.")

    # Mische und nehme bis zu 6 Kandidaten
    random.shuffle(destinations)
    candidates = destinations[:6]

    tours = []
    for dest in candidates:
        route = await get_route(lat, lon, dest["lat"], dest["lon"])
        if not route:
            continue

        tours.append({
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
