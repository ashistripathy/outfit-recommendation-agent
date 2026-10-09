import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.schemas.outfit_models import OutfitItem, OutfitRecommendation


class OutfitStudioAppTests(unittest.TestCase):
    def test_initial_page_shows_inputs_and_empty_state(self):
        app = AppTest.from_file("app.py").run()

        self.assertEqual(len(app.text_input), 2)
        self.assertEqual(app.text_input[0].label, "Occasion")
        self.assertEqual(app.text_input[1].label, "Location")
        self.assertTrue(any("Enter an occasion and location" in item.value for item in app.info))
        self.assertEqual(len(app.exception), 0)

    def test_blank_form_shows_input_validation_message(self):
        app = AppTest.from_file("app.py").run()
        app.button[0].click().run()

        self.assertTrue(any("Enter both an occasion and a location" in item.value for item in app.error))
        self.assertEqual(len(app.exception), 0)

    def test_location_uses_single_free_text_input(self):
        app = AppTest.from_file("app.py").run()
        self.assertEqual(len(app.text_input), 2)
        self.assertEqual(app.text_input[1].label, "Location")
        self.assertIn("Bengaluru or Bangalore", app.text_input[1].placeholder)
        self.assertEqual(len(app.selectbox), 0)
        self.assertEqual(len(app.exception), 0)

    def test_displays_recommendation_items_tips_and_reasoning(self):
        app = AppTest.from_file("app.py").run()
        app.session_state["recommendation"] = OutfitRecommendation(
            occasion="Smart casual",
            weather_summary="Partly cloudy, 16 C",
            items=[OutfitItem(category="Top", name="White Oxford Shirt", color="White")],
            styling_tips=["Tuck in the White Oxford Shirt for a polished look."],
            reasoning="The shirt is suitable for the occasion and weather.",
        )
        app.run()

        rendered = "\n".join(element.value for element in app.markdown)
        self.assertIn("White Oxford Shirt", rendered)
        self.assertIn("Partly cloudy, 16 C", rendered)
        self.assertIn("Tuck in the White Oxford Shirt", rendered)
        self.assertIn("suitable for the occasion", rendered)
        self.assertEqual(len(app.exception), 0)

    def test_displays_friendly_empty_wardrobe_error(self):
        app = AppTest.from_file("app.py").run()
        app.session_state["recommendation_error"] = (
            "Your wardrobe is empty. Add clothing items to data/wardrobe.json and try again."
        )
        app.run()

        self.assertTrue(any("Your wardrobe is empty" in item.value for item in app.error))
        self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()