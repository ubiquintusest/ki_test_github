import io
import zipfile
from datetime import date
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from dwd_weather.client import get_air_temperature_by_postal_code


class FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _build_station_list() -> str:
    return (
        "Stations_id von_datum bis_datum geoBreite geoLaenge Stationshoehe Stationsname Bundesland\n"
        "00001 20200101 20250101 52.5200 13.4050 34.0 Berlin-Mitte Berlin\n"
        "00002 20200101 20250101 48.1372 11.5756 520.0 Muenchen Bayern\n"
    )


def _build_zip_payload(station_id: str) -> bytes:
    content = (
        "STATIONS_ID;MESS_DATUM;QN_3;FX;FM;QN_4;RSK;RSKF;SDK;SHK_TAG;NM;VPM;PM;TMK;UPM;TXK;TNK;TGK;TNK_G;TXK_G;RSKF_G;SDK_G;SHK_TAG_G;NM_G;VPM_G;PM_G;TMK_G;UPM_G;TXK_G;TNK_G;TT_TU\n"
        f"{station_id};20240101;3;0;0;3;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;1.5\n"
        f"{station_id};20240102;3;0;0;3;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;2.5\n"
        f"{station_id};20240103;3;0;0;3;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;0;-999\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"produkt_klima_tag_{station_id}.txt", content)
    return buffer.getvalue()


def _fake_urlopen(request, timeout=30, context=None):
    parsed = urlparse(request.full_url)
    if parsed.netloc == "nominatim.openstreetmap.org":
        query = parse_qs(parsed.query)
        if query.get("postalcode", [""])[0] == "10115":
            payload = b'[{"lat": "52.5208", "lon": "13.4095"}]'
            return FakeResponse(payload)
    if parsed.path.endswith("KL_Tageswerte_Beschreibung_Stationen.txt"):
        return FakeResponse(_build_station_list().encode("utf-8"))
    if parsed.path.endswith("tageswerte_KL_00001_akt.zip"):
        return FakeResponse(_build_zip_payload("00001"))
    raise AssertionError(f"Unexpected URL requested: {request.full_url}")


def test_get_air_temperature_by_postal_code_returns_nearest_station_and_data():
    with patch("dwd_weather.client.urlopen", side_effect=_fake_urlopen):
        result = get_air_temperature_by_postal_code(
            "10115", date(2024, 1, 1), date(2024, 1, 3)
        )

    assert result["station"]["id"] == "00001"
    assert result["station"]["name"] == "Berlin-Mitte Berlin"
    assert result["temperatures"] == [
        {"date": "2024-01-01", "temperature_c": 1.5},
        {"date": "2024-01-02", "temperature_c": 2.5},
    ]


def test_get_air_temperature_by_postal_code_allows_disabling_ssl_verification():
    with patch("dwd_weather.client.urlopen", side_effect=_fake_urlopen):
        with patch(
            "dwd_weather.client.ssl._create_unverified_context",
            wraps=lambda: object(),
        ) as create_unverified:
            result = get_air_temperature_by_postal_code(
                "10115", date(2024, 1, 1), date(2024, 1, 2), verify_ssl=False
            )

    assert create_unverified.called
    assert len(result["temperatures"]) == 2
