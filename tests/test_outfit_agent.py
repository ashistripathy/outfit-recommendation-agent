import json
import unittest
from unittest.mock import patch

from pydantic_ai.models.test import TestModel

from src.agent.outfit_agent import (
    EmptyWardrobeError,
    InvalidOutfitPlanError,
    _build_prompt,
    create_outfit_agent,
    recommend_outfit,
)
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

    def test_prompt_includes_actual_wardrobe_records(self):
        prompt = _build_prompt("Smart casual", self.wardrobe, self.weather)

        self.assertIn("White Oxford Shirt", prompt)
        self.assertIn("Navy Chinos", prompt)
        self.assertNotIn("{wardrobe_json}", prompt)

    async def test_combines_context_and_corrects_wardrobe_provenance(self):
        model = TestModel(
            custom_output_text=json.dumps(
                {
                    "selected_items": [
                        {"category": "top", "name": "white oxford shirt", "color": "white"},
                        {"category": "bottom", "name": "navy chinos", "color": "navy"},
                    ],
                    "styling_tips": [
                        {
                            "action": "tuck_in",
                            "items": [{"category": "Top", "name": "White Oxford Shirt", "color": "White"}],
                        },
                        {
                            "action": "coordinate_colors",
                            "items": [
                                {"category": "Top", "name": "White Oxford Shirt", "color": "White"},
                                {"category": "Bottom", "name": "Navy Chinos", "color": "Navy"},
                            ],
                        },
                    ],
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
        self.assertTrue(recommendation.items[1].is_from_wardrobe)
        self.assertEqual(
            [item.name for item in recommendation.items],
            [item.name for item in self.wardrobe],
        )
        self.assertEqual(
            recommendation.styling_tips,
            [
                "Tuck in the White Oxford Shirt for a more polished look.",
                "The White top and Navy bottom create a coordinated look.",
            ],
        )
        self.assertNotIn("Outerwear", recommendation.reasoning)
        get_weather.assert_called_once_with("Seattle")

    async def _recommend_using_plan(self, plan):
        test_agent = create_outfit_agent(TestModel(custom_output_text=json.dumps(plan)))
        with patch("src.agent.outfit_agent.get_wardrobe", return_value=self.wardrobe):
            with patch("src.agent.outfit_agent.get_current_weather", return_value=self.weather):
                return await recommend_outfit("Office", "Seattle", agent=test_agent)

    async def test_rejects_unmatched_wardrobe_item(self):
        with self.assertRaises(InvalidOutfitPlanError):
            await self._recommend_using_plan(
                {
                    "selected_items": [
                        {"category": "Accessory", "name": "Gold Watch", "color": "Gold"}
                    ],
                    "styling_tips": [],
                }
            )

    async def test_rejects_duplicate_wardrobe_items(self):
        oxford_shirt = {"category": "Top", "name": "White Oxford Shirt", "color": "White"}
        with self.assertRaises(InvalidOutfitPlanError):
            await self._recommend_using_plan(
                {"selected_items": [oxford_shirt, oxford_shirt], "styling_tips": []}
            )

    async def test_rejects_tip_referencing_unselected_wardrobe_item(self):
        from src.agent.outfit_agent import InvalidOutfitPlanError

        plan = {
            "selected_items": [
                {"category": "Bottom", "name": "Navy Chinos", "color": "Navy"}
            ],
            "styling_tips": [
                {
                    "action": "tuck_in",
                    "items": [
                        {"category": "Top", "name": "White Oxford Shirt", "color": "White"}
                    ],
                }
            ],
        }
        with self.assertRaises(InvalidOutfitPlanError):
            await self._recommend_using_plan(plan)

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

    async def test_free_text_location_is_sent_to_weather_resolution(self):
        test_agent = create_outfit_agent(
            TestModel(
                custom_output_text=json.dumps(
                    {
                        "selected_items": [
                            {"category": "Top", "name": "White Oxford Shirt", "color": "White"}
                        ],
                        "styling_tips": [],
                    }
                )
            )
        )

        with patch("src.agent.outfit_agent.get_wardrobe", return_value=self.wardrobe):
            with patch(
                "src.agent.outfit_agent.get_current_weather",
                return_value=self.weather,
            ) as get_weather:
                await recommend_outfit(
                    "Work",
                    "Bangalore",
                    agent=test_agent,
                )

            get_weather.assert_called_once_with("Bangalore")


if __name__ == "__main__":
    unittest.main()