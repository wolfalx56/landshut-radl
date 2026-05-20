import httpx
import aiosqlite
import json
from pathlib import Path

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_HEADERS = {
    "User-Agent": "LandshutRadl/1.0 (contact: wolfalx@gmx.de)",
    "Content-Type": "application/x-www-form-urlencoded",
}
DB_PATH = Path("/app/data/cache/pois.db")

POI_CATEGORIES = {
    "biergarten": {
        "query": '["amenity"="biergarten"]',
        "icon": "🍺",
        "label": "Biergarten",
    },
    "restaurant": {
        "query": '["amenity"="restaurant"]',
        "icon": "🍽️",
        "label": "Restaurant",
    },
    "werkstatt": {
        "query": '["shop"="bicycle"]',
        "icon": "🔧",
        "label": "Fahrradwerkstatt",
    },
    "wasser": {
        "query": '["amenity"="drinking_water"]',
        "icon": "💧",
        "label": "Trinkwasser",
    },
    "toilette": {
        "query": '["amenity"="toilets"]["access"!="private"]',
        "icon": "🚻",
        "label": "Toilette",
    },
}


async def _ensure_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS poi_cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT,
                updated_at INTEGER DEFAULT (strftime('%s','now'))
            )
        """)
        await db.commit()


async def get_pois(lat: float, lon: float, radius_m: int) -> list[dict]:
    await _ensure_db()

    cache_key = f"{lat:.3f}_{lon:.3f}_{radius_m}"

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT data FROM poi_cache WHERE cache_key=? AND (strftime('%s','now') - updated_at) < 86400",
            (cache_key,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                return json.loads(row[0])

    # Cache miss → Overpass abfragen
    parts = []
    for cat in POI_CATEGORIES.values():
        parts.append(f'node{cat["query"]}(around:{radius_m},{lat},{lon});')

    query = f"[out:json][timeout:20];\n({chr(10).join(parts)});\nout body;"

    async with httpx.AsyncClient(timeout=25) as client:
        from urllib.parse import urlencode
        resp = await client.post(OVERPASS_URL, content=urlencode({"data": query}), headers=OVERPASS_HEADERS)
        resp.raise_for_status()
        data = resp.json()

    pois = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        category = _detect_category(tags)
        if not category:
            continue

        cat_info = POI_CATEGORIES[category]
        pois.append({
            "id": el["id"],
            "lat": el["lat"],
            "lon": el["lon"],
            "name": tags.get("name", cat_info["label"]),
            "category": category,
            "icon": cat_info["icon"],
            "label": cat_info["label"],
            "opening_hours": tags.get("opening_hours"),
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "website": tags.get("website") or tags.get("contact:website"),
        })

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO poi_cache (cache_key, data) VALUES (?,?)",
            (cache_key, json.dumps(pois))
        )
        await db.commit()

    return pois


def _detect_category(tags: dict) -> str | None:
    amenity = tags.get("amenity", "")
    shop = tags.get("shop", "")
    if amenity == "biergarten":
        return "biergarten"
    if amenity == "restaurant":
        return "restaurant"
    if shop == "bicycle":
        return "werkstatt"
    if amenity == "drinking_water":
        return "wasser"
    if amenity == "toilets":
        return "toilette"
    return None
