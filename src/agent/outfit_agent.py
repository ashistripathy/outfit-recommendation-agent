import asyncio
import json
import os
from typing import Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv
from pydantic_ai import Agent, PromptedOutput
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from src.schemas.outfit_models import OutfitItem, OutfitPlan, OutfitRecommendation
from src.tools.wardrobe_tool import get_wardrobe
from src.tools.weather_tool import CurrentWeather, get_current_weather


load_dotenv()

DEFAULT_MODEL_NAME = "qwen2.5:7b"
DEFAULT_MODEL_BASE_URL = "http://localhost:11434/v1"

AGENT_INSTRUCTIONS = (
    "Select a practical outfit for the requested occasion using only items from "
    "the supplied wardrobe. Copy each selected item's category, name, and color "
    "exactly from the wardrobe; do not invent garments. Styling tips must reference "
    "only selected wardrobe items and use only the allowed structured actions. "
    "Use layer with exactly two items, tuck_in with exactly one top, and "
    "coordinate_colors with exactly two items. Do not return free-text advice, "
    "weather, or reasoning."
)
_default_agent = None


def create_outfit_agent(model=None) -> Agent:
    """Create an agent using an injected PydanticAI model or local Ollama defaults."""
    if model is None:
        model = OpenAIChatModel(
            os.getenv("OUTFIT_AGENT_MODEL", DEFAULT_MODEL_NAME),
            provider=OpenAIProvider(
                base_url=os.getenv("OUTFIT_AGENT_BASE_URL", DEFAULT_MODEL_BASE_URL),
                api_key=os.getenv("OUTFIT_AGENT_API_KEY", "ollama"),
            ),
        )
    return Agent(
        model=model,
        output_type=PromptedOutput(OutfitPlan),
        instructions=AGENT_INSTRUCTIONS,
    )


def get_outfit_agent() -> Agent:
    """Get the lazily initialized default agent for reuse by application frontends."""
    global _default_agent
    if _default_agent is None:
        _default_agent = create_outfit_agent()
    return _default_agent


class EmptyWardrobeError(ValueError):
    """Raised when an outfit cannot be assembled because no wardrobe items exist."""


class InvalidOutfitPlanError(ValueError):
    """Raised when the model returns invalid wardrobe references or styling actions."""


def _item_identity(item: OutfitItem) -> Tuple[str, str, str]:
    return tuple(value.strip().casefold() for value in (item.category, item.name, item.color))


async def recommend_outfit(
    occasion: str,
    location: str,
    *,
    agent: Optional[Agent] = None,
) -> OutfitRecommendation:
    """Build a validated outfit recommendation from local wardrobe and live weather."""
    if not occasion or not occasion.strip():
        raise ValueError("Occasion must not be empty")
    if not location or not location.strip():
        raise ValueError("Location must not be empty")

    wardrobe = await asyncio.to_thread(get_wardrobe)
    if not wardrobe:
        raise EmptyWardrobeError(
            "Your wardrobe is empty. Add at least one clothing item before requesting an outfit."
        )

    weather = await asyncio.to_thread(get_current_weather, location.strip())
    prompt = _build_prompt(occasion.strip(), wardrobe, weather)
    result = await (agent or get_outfit_agent()).run(prompt)
    plan = result.output

    wardrobe_by_identity = {_item_identity(item): item for item in wardrobe}
    selected_identities = [_item_identity(item) for item in plan.selected_items]
    if len(set(selected_identities)) != len(selected_identities):
        raise InvalidOutfitPlanError("The outfit plan selected a wardrobe item more than once")
    if any(identity not in wardrobe_by_identity for identity in selected_identities):
        raise InvalidOutfitPlanError("The outfit plan refers to an item outside the wardrobe")

    selected_identity_set = set(selected_identities)
    recommended_items = [
        wardrobe_by_identity[identity].model_copy(update={"is_from_wardrobe": True})
        for identity in selected_identities
    ]
    styling_tips = _render_styling_tips(plan, selected_identity_set, wardrobe_by_identity)
    selected_names = ", ".join(item.name for item in recommended_items)
    reasoning = (
        f"Selected {selected_names} from your wardrobe for {occasion.strip()}. "
        f"Current conditions in {weather.location}: {weather.summary}."
    )

    return OutfitRecommendation.model_validate(
        {
            "occasion": occasion.strip(),
            "weather_summary": weather.summary,
            "items": recommended_items,
            "styling_tips": styling_tips,
            "reasoning": reasoning,
        }
    )


def _render_styling_tips(
    plan: OutfitPlan,
    selected_identities: Set[Tuple[str, str, str]],
    wardrobe_by_identity: Dict[Tuple[str, str, str], OutfitItem],
) -> List[str]:
    rendered_tips = []
    for tip in plan.styling_tips:
        identities = [_item_identity(item) for item in tip.items]
        if len(set(identities)) != len(identities):
            raise InvalidOutfitPlanError("A styling tip cannot reference the same item more than once")
        if any(identity not in wardrobe_by_identity for identity in identities):
            raise InvalidOutfitPlanError("A styling tip refers to an item outside the wardrobe")
        if any(identity not in selected_identities for identity in identities):
            raise InvalidOutfitPlanError("A styling tip refers to an item not selected for the outfit")

        items = [wardrobe_by_identity[identity] for identity in identities]
        if tip.action == "layer":
            if len(items) != 2:
                raise InvalidOutfitPlanError("The layer action requires exactly two selected items")
            rendered_tips.append(f"Layer {items[0].name} with {items[1].name} for a versatile outfit.")
        elif tip.action == "tuck_in":
            if len(items) != 1 or items[0].category.casefold() != "top":
                raise InvalidOutfitPlanError("The tuck_in action requires exactly one top")
            rendered_tips.append(f"Tuck in the {items[0].name} for a more polished look.")
        elif tip.action == "coordinate_colors":
            if len(items) != 2:
                raise InvalidOutfitPlanError("The coordinate_colors action requires exactly two selected items")
            rendered_tips.append(
                f"The {items[0].color} {items[0].category.lower()} and "
                f"{items[1].color} {items[1].category.lower()} create a coordinated look."
            )
    return rendered_tips


def _build_prompt(
    occasion: str,
    wardrobe: List[OutfitItem],
    weather: CurrentWeather,
) -> str:
    wardrobe_json = json.dumps(
        [item.model_dump() for item in wardrobe],
        ensure_ascii=True,
    )
    return (
        f"Occasion: {occasion}\n"
        f"Location: {weather.location}\n"
        f"Current weather: {weather.summary}\n"
        f"Weather observation time: {weather.observed_at} ({weather.timezone})\n"
        f"Available wardrobe items (JSON): {wardrobe_json}\n"
        "Return selected_items by copying each category, name, and color exactly from "
        "the wardrobe. Return styling_tips as structured actions referencing those same "
        "item objects: layer uses two selected items, tuck_in uses one selected top, "
        "and coordinate_colors uses two selected items. "
        "Do not generate item descriptions, purchase suggestions, or free-text advice."
    )