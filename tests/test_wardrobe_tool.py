import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.schemas.outfit_models import OutfitItem
from src.tools.wardrobe_tool import get_wardrobe


class GetWardrobeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp_dir.name) / "wardrobe.json"
        self.path_patch = patch("src.tools.wardrobe_tool.WARDROBE_STATE_PATH", self.state_path)
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.temp_dir.cleanup()

    def test_missing_state_returns_empty_wardrobe(self):
        self.assertEqual(get_wardrobe(), [])

    def test_loads_and_validates_wardrobe_items(self):
        self.state_path.write_text(
            json.dumps([{"category": "Top", "name": "Oxford shirt", "color": "White"}]),
            encoding="utf-8",
        )

        wardrobe = get_wardrobe()

        self.assertEqual(len(wardrobe), 1)
        self.assertIsInstance(wardrobe[0], OutfitItem)
        self.assertEqual(wardrobe[0].name, "Oxford shirt")

    def test_rejects_non_array_state(self):
        self.state_path.write_text("{}", encoding="utf-8")

        with self.assertRaises(ValueError):
            get_wardrobe()


if __name__ == "__main__":
    unittest.main()