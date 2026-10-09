import unittest
from unittest.mock import Mock, patch

import httpx

from src.tools.weather_tool import (
    CurrentWeather,
    WeatherLookupError,
    get_current_weather,
)


def make_response(payload):
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class GetCurrentWeatherTests(unittest.TestCase):
    @patch("src.tools.weather_tool.httpx.get")
    def test_resolves_location_and_returns_current_conditions(self, get):
        get.side_effect = [
            make_response(
                {
                    "results": [
                        {
                            "name": "Seattle",
                            "admin1": "Washington",
                            "country": "United States",
                            "latitude": 47.6062,
                            "longitude": -122.3321,
                        }
                    ]
                }
            ),
            make_response(
                {
                    "timezone": "America/Los_Angeles",
                    "current": {
                        "time": "2026-10-08T10:00",
                        "temperature_2m": 16.5,
                        "apparent_temperature": 15.8,
                        "relative_humidity_2m": 72,
                        "precipitation": 0.0,
                        "weather_code": 2,
                        "wind_speed_10m": 8.4,
                    },
                }
            ),
        ]

        weather = get_current_weather("Seattle")

        self.assertIsInstance(weather, CurrentWeather)
        self.assertEqual(weather.location, "Seattle, Washington, United States")
        self.assertEqual(weather.condition, "Partly cloudy")
        self.assertIn("16.5 C", weather.summary)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args_list[0].kwargs["params"]["name"], "Seattle")
        self.assertEqual(get.call_args_list[1].kwargs["params"]["timezone"], "auto")

    @patch("src.tools.weather_tool.httpx.get")
    def test_raises_for_unknown_location(self, get):
        get.return_value = make_response({"results": []})

        with self.assertRaises(WeatherLookupError):
            get_current_weather("No Such City")

        get.assert_called_once()

    @patch("src.tools.weather_tool.httpx.get")
    def test_wraps_network_timeout(self, get):
        get.side_effect = httpx.TimeoutException("request timed out")

        with self.assertRaises(WeatherLookupError):
            get_current_weather("Seattle")

    @patch("src.tools.weather_tool.httpx.get")
    def test_rejects_blank_location_without_requesting_api(self, get):
        with self.assertRaises(ValueError):
            get_current_weather("  ")

        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()