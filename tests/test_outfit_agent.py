import json
import unittest
from unittest.mock import patch

from pydantic_ai.models.test import TestModel

from src.agent.outfit_agent import EmptyWardrobeError, create_outfit_agent, recommend_outfit
from src.schemas.outfit_models import OutfitItem
from src.tools.weather_tool import CurrentWeather


class RecommendOutfitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.wardrobe = [
            OutfitItem(category="Top", name="White Oxford Shirt", color="White"),
            OutfitItem(category="Bottom", name="Navy Chinos", color="Navy"),
        ]
        self.weather = CurrentWeather(
            location="Seattle, Washington, United States",
            temperature_c=16.5,
            feels_like_c=15.8,
            relative_humidity_percent=72,
            precipitation_mm=0.0,
            wind_speed_kmh=8.4,
            condition="Partly cloudy",
            observed_at="2026-10-08T10:00",
            timezone="America/Los_Angeles",
        )

    async def test_combines_context_and_corrects_wardrobe_provenance(self):
        model = TestModel(
            custom_output_text=json.dumps(
                {
                    "occasion": "Model changed this",
                    "weather_summary": "Model invented this",
                    "items": [
                        {
                            "category": "Top",
                            "name": "White Oxford Shirt",
                            "color": "White",
                            "is_from_wardrobe": False,
                        },
                        {
                            "category": "Outerwear",
                            "name": "Yellow Raincoat",
                            "color": "Yellow",
                            "is_from_wardrobe": True,
                        },
                    ],
                    "styling_tips": ["Bring a light layer."],
                    "reasoning": "The shirt works for this occasion.",
                }
            )
        )
        test_agent = create_outfit_agent(model)

        with patch("src.agent.outfit_agent.get_wardrobe", return_value=self.wardrobe):
            with patch(
                "src.agent.outfit_agent.get_current_weather",
                return_value=self.weather,
            ) as get_weather:
                recommendation = await recommend_outfit(
                    "Smart casual",
                    "Seattle",
                    agent=test_agent,
                )

        self.assertEqual(recommendation.occasion, "Smart casual")
        self.assertEqual(recommendation.weather_summary, self.weather.summary)
        self.assertTrue(recommendation.items[0].is_from_wardrobe)
        self.assertFalse(recommendation.items[1].is_from_wardrobe)
        get_weather.assert_called_once_with("Seattle")

    async def test_empty_wardrobe_fails_before_weather_or_model_call(self):
        with patch("src.agent.outfit_agent.get_wardrobe", return_value=[]):
            with patch("src.agent.outfit_agent.get_current_weather") as get_weather:
                with self.assertRaises(EmptyWardrobeError):
                    await recommend_outfit("Office", "Seattle")

        get_weather.assert_not_called()

    async def test_rejects_blank_occasion_before_loading_wardrobe(self):
        with patch("src.agent.outfit_agent.get_wardrobe") as get_wardrobe:
            with self.assertRaises(ValueError):
                await recommend_outfit("  ", "Seattle")

        get_wardrobe.assert_not_called()


if __name__ == "__main__":
    unittest.main()