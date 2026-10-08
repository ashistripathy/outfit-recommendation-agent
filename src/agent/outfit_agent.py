import asyncio
import json
import os
from typing import List, Optional, Set, Tuple

from dotenv import load_dotenv
from pydantic_ai import Agent, PromptedOutput
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from src.schemas.outfit_models import OutfitItem, OutfitRecommendation
from src.tools.wardrobe_tool import get_wardrobe
from src.tools.weather_tool import CurrentWeather, get_current_weather


load_dotenv()

DEFAULT_MODEL_NAME = "qwen2.5:7b"
DEFAULT_MODEL_BASE_URL = "http://localhost:11434/v1"

AGENT_INSTRUCTIONS = (
    "Recommend a practical outfit for the requested occasion using the supplied "
    "weather and wardrobe. Prefer supplied wardrobe items. Only describe an item "
    "as wardrobe-owned when it exactly matches a supplied item; mark new purchase "
    "suggestions with is_from_wardrobe=false. Include a complete outfit, useful "
    "styling tips, and concise reasoning. Write all user-facing text in clear, "
    "natural English. Do not invent weather data."
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
        output_type=PromptedOutput(OutfitRecommendation),
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

    wardrobe_items: Set[Tuple[str, str, str]] = {_item_identity(item) for item in wardrobe}
    recommended_items = [
        item.model_copy(update={"is_from_wardrobe": _item_identity(item) in wardrobe_items})
        for item in result.output.items
    ]

    return OutfitRecommendation.model_validate(
        {
            **result.output.model_dump(),
            "occasion": occasion.strip(),
            "weather_summary": weather.summary,
            "items": recommended_items,
        }
    )


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
        "Create one complete recommendation. Prefer the available wardrobe and do not "
        "claim unavailable items are owned. Any suggested purchase must be marked "
        "is_from_wardrobe=false."
    )