from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, ValidationError


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_SECONDS = 10.0

WEATHER_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class WeatherLookupError(RuntimeError):
    """Raised when a location or current weather cannot be retrieved."""


class LocationSuggestion(BaseModel):
    name: str
    latitude: float
    longitude: float
    admin1: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None

    @property
    def label(self) -> str:
        parts = [self.name]
        if self.admin1 and self.admin1.casefold() != self.name.casefold():
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


class CurrentWeather(BaseModel):
    location: str
    temperature_c: float
    feels_like_c: float
    relative_humidity_percent: int
    precipitation_mm: float
    wind_speed_kmh: float
    condition: str
    observed_at: str
    timezone: str

    @property
    def summary(self) -> str:
        return (
            f"{self.condition}, {self.temperature_c:.1f} C "
            f"(feels like {self.feels_like_c:.1f} C); "
            f"humidity {self.relative_humidity_percent}%, "
            f"precipitation {self.precipitation_mm:.1f} mm, "
            f"wind {self.wind_speed_kmh:.1f} km/h"
        )


def _get_json(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        response = httpx.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise WeatherLookupError("Unable to retrieve weather data from Open-Meteo") from error

    if not isinstance(data, dict):
        raise WeatherLookupError("Open-Meteo returned an invalid response")
    return data


def _get_location_candidates(query: str) -> List[LocationSuggestion]:
    """Search Open-Meteo for places matching a city or region name."""
    if not query or len(query.strip()) < 3:
        return []

    try:
        search_queries = [query.strip()]
        if "bangalore" in query.casefold():
            search_queries.append("Bengaluru")

        suggestions = []
        seen_coordinates = set()
        for search_query in search_queries:
            geocoding_data = _get_json(
                GEOCODING_URL,
                {"name": search_query, "count": 8, "language": "en", "format": "json"},
            )
            results = geocoding_data.get("results", [])
            if not isinstance(results, list):
                raise WeatherLookupError("Open-Meteo returned invalid location suggestions")
            for result in results:
                suggestion = LocationSuggestion.model_validate(result)
                coordinates = (suggestion.latitude, suggestion.longitude)
                if coordinates not in seen_coordinates:
                    suggestions.append(suggestion)
                    seen_coordinates.add(coordinates)
        return suggestions
    except ValidationError as error:
        raise WeatherLookupError("Open-Meteo returned incomplete location suggestions") from error


def _resolve_location(location: str) -> LocationSuggestion:
    query = location.strip()
    if not query:
        raise ValueError("Location must not be empty")

    normalized_query = query.casefold()
    if normalized_query in {"karnataka", "karnataka, india"}:
        search_query = "Bengaluru"
    else:
        search_query = query

    suggestions = _get_location_candidates(search_query)
    if not suggestions:
        raise WeatherLookupError(
            "Could not find that location. Enter a city name, for example Bengaluru or Bengaluru, Karnataka, India."
        )

    if "bangalore" in normalized_query or normalized_query in {"karnataka", "karnataka, india"}:
        india_city = next(
            (
                suggestion
                for suggestion in suggestions
                if suggestion.country_code == "IN"
                and suggestion.name.casefold() in {"bengaluru", "bangalore"}
            ),
            None,
        )
        if india_city is not None:
            return india_city

    return suggestions[0]


def get_current_weather(location: str) -> CurrentWeather:
    """Retrieve current conditions, resolving ambiguous city names automatically."""
    if not location or not location.strip():
        raise ValueError("Location must not be empty")
    place = _resolve_location(location)
    resolved_location = place.label

    try:
        latitude = place.latitude
        longitude = place.longitude
    except (AttributeError, TypeError) as error:
        raise WeatherLookupError("Open-Meteo returned incomplete location data") from error

    forecast_data = _get_json(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "precipitation,weather_code,wind_speed_10m"
            ),
            "timezone": "auto",
        },
    )
    current = forecast_data.get("current")
    if not isinstance(current, dict):
        raise WeatherLookupError("Open-Meteo response does not contain current conditions")

    try:
        return CurrentWeather(
            location=resolved_location,
            temperature_c=current["temperature_2m"],
            feels_like_c=current["apparent_temperature"],
            relative_humidity_percent=current["relative_humidity_2m"],
            precipitation_mm=current["precipitation"],
            wind_speed_kmh=current["wind_speed_10m"],
            condition=WEATHER_DESCRIPTIONS.get(current["weather_code"], "Unknown conditions"),
            observed_at=current["time"],
            timezone=forecast_data["timezone"],
        )
    except (KeyError, TypeError, ValidationError) as error:
        raise WeatherLookupError("Open-Meteo returned incomplete current conditions") from error