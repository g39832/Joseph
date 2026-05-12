"""
brain/weather.py
-----------------
Weather data for JOSEPH using Open-Meteo API.

Open-Meteo is completely FREE — no API key, no account needed.
It uses your IP address to determine location automatically,
or you can set coordinates in .env for accuracy.

Provides:
- Current conditions (temp, feels like, wind, humidity)
- Today's forecast (high/low, precipitation chance)
- Natural language weather summary for Joseph to speak
"""

import logging
from datetime import datetime
from typing import Optional

import requests

from configs.settings import settings

logger = logging.getLogger(__name__)

# Open-Meteo API — free, no key needed
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
IP_LOCATION_URL = "https://ipapi.co/json/"

# WMO weather code descriptions
WMO_CODES = {
    0: "clear sky",
    1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "icy fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "moderate rain", 65: "heavy rain",
    71: "light snow", 73: "moderate snow", 75: "heavy snow",
    77: "snow grains",
    80: "light showers", 81: "moderate showers", 82: "heavy showers",
    85: "light snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "severe thunderstorm",
}


class WeatherService:
    """
    Fetches weather data from Open-Meteo (free, no API key).

    Usage:
        weather = WeatherService()
        summary = weather.get_summary()
        print(summary)  # "Currently 72°F, partly cloudy..."
    """

    def __init__(self):
        self._location: Optional[dict] = None
        self._cache: Optional[dict] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_minutes = 30

    def get_location(self) -> Optional[dict]:
        """
        Get current location via IP geolocation.

        Returns:
            Dict with lat, lon, city, country — or None if failed.
        """
        if self._location:
            return self._location

        try:
            resp = requests.get(IP_LOCATION_URL, timeout=5)
            data = resp.json()
            self._location = {
                "lat": data.get("latitude"),
                "lon": data.get("longitude"),
                "city": data.get("city", "Unknown"),
                "region": data.get("region", ""),
                "country": data.get("country_name", ""),
            }
            logger.info(
                f"Location detected: {self._location['city']}, "
                f"{self._location['region']}"
            )
            return self._location

        except Exception as e:
            logger.warning(f"Location detection failed: {e}")
            return None

    def get_weather(self, force_refresh: bool = False) -> Optional[dict]:
        """
        Fetch current weather data.

        Args:
            force_refresh: Bypass cache and fetch fresh data.

        Returns:
            Weather dict or None if failed.
        """
        # Return cached data if fresh
        if (not force_refresh
                and self._cache
                and self._cache_time
                and (datetime.now() - self._cache_time).seconds < self._cache_ttl_minutes * 60):
            return self._cache

        location = self.get_location()
        if not location:
            return None

        try:
            params = {
                "latitude": location["lat"],
                "longitude": location["lon"],
                "current": [
                    "temperature_2m",
                    "apparent_temperature",
                    "relative_humidity_2m",
                    "weather_code",
                    "wind_speed_10m",
                    "precipitation",
                ],
                "daily": [
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_probability_max",
                    "weather_code",
                ],
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "forecast_days": 1,
                "timezone": "auto",
            }

            resp = requests.get(WEATHER_URL, params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()

            current = data.get("current", {})
            daily = data.get("daily", {})

            weather = {
                "location": f"{location['city']}, {location['region']}",
                "temp_f": round(current.get("temperature_2m", 0)),
                "feels_like_f": round(current.get("apparent_temperature", 0)),
                "humidity": current.get("relative_humidity_2m", 0),
                "wind_mph": round(current.get("wind_speed_10m", 0)),
                "condition": WMO_CODES.get(current.get("weather_code", 0), "unknown"),
                "high_f": round(daily.get("temperature_2m_max", [0])[0]),
                "low_f": round(daily.get("temperature_2m_min", [0])[0]),
                "precip_chance": daily.get("precipitation_probability_max", [0])[0],
                "fetched_at": datetime.now().strftime("%H:%M"),
            }

            self._cache = weather
            self._cache_time = datetime.now()
            logger.info(f"Weather fetched: {weather['temp_f']}°F, {weather['condition']}")
            return weather

        except Exception as e:
            logger.error(f"Weather fetch failed: {e}")
            return None

    def get_summary(self, brief: bool = False) -> str:
        """
        Get a natural language weather summary.

        Args:
            brief: If True, return a short one-liner.

        Returns:
            Weather description string.
        """
        weather = self.get_weather()
        if not weather:
            return "I couldn't get the weather right now. Check your internet connection."

        if brief:
            return (
                f"{weather['temp_f']}°F and {weather['condition']} "
                f"in {weather['location']}."
            )

        lines = [
            f"Currently {weather['temp_f']}°F in {weather['location']}, "
            f"with {weather['condition']}.",
            f"Feels like {weather['feels_like_f']}°F.",
            f"Today's high is {weather['high_f']}°F, low is {weather['low_f']}°F.",
        ]

        if weather["precip_chance"] > 30:
            lines.append(
                f"There's a {weather['precip_chance']}% chance of precipitation."
            )

        if weather["wind_mph"] > 15:
            lines.append(f"Wind is {weather['wind_mph']} mph.")

        return " ".join(lines)

    def get_briefing_weather(self) -> str:
        """Short weather line for the morning briefing."""
        return self.get_summary(brief=True)


# Module-level singleton
weather_service = WeatherService()
