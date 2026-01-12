from __future__ import annotations

import csv
import io
import json
import math
import ssl
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DWD_STATION_LIST_URL = (
    "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
    "daily/kl/recent/KL_Tageswerte_Beschreibung_Stationen.txt"
)
DWD_DAILY_KL_BASE_URL = (
    "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
    "daily/kl/recent"
)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


@dataclass(frozen=True)
class Station:
    station_id: str
    name: str
    latitude: float
    longitude: float
    distance_km: float


def get_air_temperature_by_postal_code(
    postleitzahl: str,
    von: date | str,
    bis: date | str,
    *,
    verify_ssl: bool = True,
) -> dict:
    """
    Fetch daily air temperatures (TT_TU) from the nearest DWD station.

    Args:
        postleitzahl: German postal code.
        von: Start date (inclusive) as date or ISO string YYYY-MM-DD.
        bis: End date (inclusive) as date or ISO string YYYY-MM-DD.

    Returns:
        Dict with station metadata and list of temperature entries.
    """

    start_date = _ensure_date(von)
    end_date = _ensure_date(bis)
    if start_date > end_date:
        raise ValueError("'von' must be before or equal to 'bis'")

    ssl_context = _create_ssl_context(verify_ssl)
    location = _geocode_postal_code(postleitzahl, ssl_context)
    stations = _fetch_stations(ssl_context)
    nearest = _find_nearest_station(location[0], location[1], stations)

    temps = _fetch_temperatures(
        nearest.station_id, start_date, end_date, ssl_context
    )

    return {
        "station": {
            "id": nearest.station_id,
            "name": nearest.name,
            "latitude": nearest.latitude,
            "longitude": nearest.longitude,
            "distance_km": round(nearest.distance_km, 3),
        },
        "temperatures": temps,
    }


def _ensure_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def _geocode_postal_code(
    postleitzahl: str, ssl_context: ssl.SSLContext
) -> tuple[float, float]:
    payload = _http_get_json(
        NOMINATIM_URL,
        params={
            "postalcode": postleitzahl,
            "country": "Germany",
            "format": "json",
            "limit": 1,
        },
        headers={"User-Agent": "dwd-weather/0.1"},
        ssl_context=ssl_context,
    )
    if not payload:
        raise ValueError(f"No location found for postal code {postleitzahl}")
    lat = float(payload[0]["lat"])
    lon = float(payload[0]["lon"])
    return lat, lon


def _fetch_stations(ssl_context: ssl.SSLContext) -> list[dict]:
    text = _http_get_text(DWD_STATION_LIST_URL, ssl_context=ssl_context)
    lines = text.splitlines()
    stations = []
    for line in lines:
        if not line.strip() or line.startswith("Stations_id"):
            continue
        station = _parse_station_line(line)
        if station:
            stations.append(station)
    if not stations:
        raise ValueError("No stations found in DWD station list")
    return stations


def _parse_station_line(line: str) -> dict | None:
    parts = line.split()
    if len(parts) < 7:
        return None
    station_id = parts[0].zfill(5)
    try:
        latitude = float(parts[3])
        longitude = float(parts[4])
    except ValueError:
        return None
    name = " ".join(parts[6:])
    return {
        "station_id": station_id,
        "name": name,
        "latitude": latitude,
        "longitude": longitude,
    }


def _find_nearest_station(
    latitude: float, longitude: float, stations: Iterable[dict]
) -> Station:
    nearest_station: Station | None = None
    for station in stations:
        distance = _haversine_km(
            latitude,
            longitude,
            station["latitude"],
            station["longitude"],
        )
        candidate = Station(
            station_id=station["station_id"],
            name=station["name"],
            latitude=station["latitude"],
            longitude=station["longitude"],
            distance_km=distance,
        )
        if nearest_station is None or candidate.distance_km < nearest_station.distance_km:
            nearest_station = candidate
    if nearest_station is None:
        raise ValueError("No stations available to determine nearest station")
    return nearest_station


def _fetch_temperatures(
    station_id: str,
    start_date: date,
    end_date: date,
    ssl_context: ssl.SSLContext,
) -> list[dict]:
    zip_name = f"tageswerte_KL_{station_id}_akt.zip"
    url = f"{DWD_DAILY_KL_BASE_URL}/{zip_name}"
    content = _http_get_bytes(url, ssl_context=ssl_context)

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        data_name = next(
            (
                name
                for name in zf.namelist()
                if name.startswith("produkt_klima_tag") and name.endswith(".txt")
            ),
            None,
        )
        if not data_name:
            raise ValueError("Temperature data file not found in DWD archive")
        with zf.open(data_name) as handle:
            content_stream = io.TextIOWrapper(handle, encoding="utf-8")
            reader = csv.DictReader(content_stream, delimiter=";")
            results = []
            for row in reader:
                date_value = datetime.strptime(row["MESS_DATUM"], "%Y%m%d").date()
                if date_value < start_date or date_value > end_date:
                    continue
                temp_raw = row.get("TT_TU")
                if temp_raw in (None, "", "-999"):
                    continue
                results.append(
                    {
                        "date": date_value.isoformat(),
                        "temperature_c": float(temp_raw),
                    }
                )
            return results


def _http_get_json(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    ssl_context: ssl.SSLContext | None = None,
):
    payload = _http_get_bytes(
        url, params=params, headers=headers, ssl_context=ssl_context
    )
    return json.loads(payload.decode("utf-8"))


def _http_get_text(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    ssl_context: ssl.SSLContext | None = None,
) -> str:
    payload = _http_get_bytes(
        url, params=params, headers=headers, ssl_context=ssl_context
    )
    return payload.decode("utf-8")


def _http_get_bytes(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    ssl_context: ssl.SSLContext | None = None,
) -> bytes:
    final_url = url
    if params:
        final_url = f"{url}?{urlencode(params)}"
    request = Request(final_url, headers=headers or {})
    with urlopen(request, timeout=30, context=ssl_context) as response:
        return response.read()


def _create_ssl_context(verify_ssl: bool) -> ssl.SSLContext:
    if verify_ssl:
        return ssl.create_default_context()
    return ssl._create_unverified_context()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(
        dlon / 2
    ) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c
