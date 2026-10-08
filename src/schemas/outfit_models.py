from typing import List, Literal, Optional
from pydantic import BaseModel, Field

class OutfitItem(BaseModel):
    category: str = Field(
        ...,
        description="Type of garment/accessory (e.g., Top, Bottom, Footwear, Outerwear, Accessory)"
    )
    name: str = Field(
        ...,
        description="Description of the item (e.g., Navy Blue Linen Shirt)"
    )
    color: str = Field(
        ...,
        description="Primary color of the item"
    )
    is_from_wardrobe: bool = Field(
        default=True,
        description="True if picked from user's wardrobe, False if suggested buy"
    )

class OutfitRecommendation(BaseModel):
    occasion: str = Field(
        ...,
        description="The target event or dress code"
    )
    weather_summary: str = Field(
        ...,
        description="Summary of weather constraints factored into the choice"
    )
    items: List[OutfitItem] = Field(
        ...,
        min_length=1,
        description="List of garments composing the full outfit"
    )
    styling_tips: List[str] = Field(
        ...,
        description="Practical tips on layering, tucking, or pairing accessories"
    )
    reasoning: str = Field(
        ...,
        description="Explanation of why this combination fits the occasion and weather"
    )


class StylingTipPlan(BaseModel):
    action: Literal["layer", "tuck_in", "coordinate_colors"]
    items: List[OutfitItem] = Field(min_length=1, max_length=2)


class OutfitPlan(BaseModel):
    selected_items: List[OutfitItem] = Field(min_length=1)
    styling_tips: List[StylingTipPlan] = Field(default_factory=list)