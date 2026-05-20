import httpx

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

WMO_CODES = {
    0: ("Klar", "☀️"), 1: ("Überwiegend klar", "🌤️"), 2: ("Teilweise bewölkt", "⛅"),
    3: ("Bewölkt", "☁️"), 45: ("Nebel", "🌫️"), 48: ("Raureif-Nebel", "🌫️"),
    51: ("Leichter Nieselregen", "🌦️"), 53: ("Nieselregen", "🌦️"), 55: ("Starker Nieselregen", "🌧️"),
    61: ("Leichter Regen", "🌧️"), 63: ("Regen", "🌧️"), 65: ("Starker Regen", "🌧️"),
    71: ("Leichter Schnee", "🌨️"), 73: ("Schnee", "🌨️"), 75: ("Starker Schnee", "❄️"),
    80: ("Regenschauer", "🌦️"), 81: ("Regenschauer", "🌧️"), 82: ("Starke Schauer", "⛈️"),
    95: ("Gewitter", "⛈️"), 96: ("Gewitter mit Hagel", "⛈️"), 99: ("Schweres Gewitter", "⛈️"),
}


async def get_weather(lat: float, lon: float) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max",
        "hourly": "temperature_2m,precipitation_probability,windspeed_10m",
        "forecast_days": 3,
        "timezone": "Europe/Berlin",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(OPEN_METEO_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    daily = data["daily"]
    days = []
    for i in range(3):
        code = daily["weathercode"][i]
        desc, icon = WMO_CODES.get(code, ("Unbekannt", "❓"))
        days.append({
            "date": daily["time"][i],
            "icon": icon,
            "description": desc,
            "temp_max": round(daily["temperature_2m_max"][i]),
            "temp_min": round(daily["temperature_2m_min"][i]),
            "precipitation_mm": daily["precipitation_sum"][i],
            "wind_kmh": round(daily["windspeed_10m_max"][i]),
            "good_for_cycling": _is_good(code, daily["precipitation_sum"][i], daily["windspeed_10m_max"][i]),
        })

    return {"days": days}


def _is_good(wmo_code: int, precip_mm: float, wind_kmh: float) -> bool:
    bad_codes = {55, 61, 63, 65, 71, 73, 75, 80, 81, 82, 95, 96, 99}
    return wmo_code not in bad_codes and precip_mm < 3 and wind_kmh < 35
