import json
from pathlib import Path
from typing import List

from src.schemas.outfit_models import OutfitItem


WARDROBE_STATE_PATH = Path(__file__).resolve().parents[2] / "data" / "wardrobe.json"


def _load_wardrobe(state_path: Path) -> List[OutfitItem]:
    if not state_path.exists():
        return []

    with state_path.open(encoding="utf-8") as state_file:
        wardrobe_data = json.load(state_file)

    if not isinstance(wardrobe_data, list):
        raise ValueError("Wardrobe state must contain a JSON array of clothing items")

    return [OutfitItem.model_validate(item) for item in wardrobe_data]


def get_wardrobe() -> List[OutfitItem]:
    """Retrieve and validate clothing items from the local wardrobe state file."""
    return _load_wardrobe(WARDROBE_STATE_PATH)