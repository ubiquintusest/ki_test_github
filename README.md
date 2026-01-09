# DWD Weather

Dieses Projekt ruft tägliche Lufttemperaturen (TT_TU) von der nächstgelegenen DWD-Wetterstation ab.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Für Tests:

```bash
pip install -e .[test]
```

## Beispiel

```python
from dwd_weather import get_air_temperature_by_postal_code

result = get_air_temperature_by_postal_code("10115", "2024-01-01", "2024-01-07")
print(result)
```

Die Funktion liefert Station-Metadaten und eine Liste von Temperaturwerten je Tag.
