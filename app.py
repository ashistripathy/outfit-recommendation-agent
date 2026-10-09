import asyncio
from html import escape

import streamlit as st

from src.agent.outfit_agent import (
    EmptyWardrobeError,
    InvalidOutfitPlanError,
    recommend_outfit,
)
from src.schemas.outfit_models import OutfitRecommendation
from src.tools.weather_tool import WeatherLookupError


st.set_page_config(
    page_title="Outfit Studio",
    page_icon="O",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');

    :root {
        --ink: #202521;
        --muted: #68716b;
        --paper: #f4f6f2;
        --line: #dce2da;
        --forest: #285c48;
        --coral: #c8664f;
        --mist: #e7eee8;
    }
    .stApp { background: var(--paper); color: var(--ink); }
    [data-testid="stHeader"] { background: transparent; }
    .block-container { max-width: 900px; padding-top: 2.5rem; padding-bottom: 4rem; }
    .brand-row { display:flex; align-items:center; gap:12px; margin-bottom:1.6rem; }
    .brand-mark { display:grid; place-items:center; width:38px; height:38px; border-radius:50%; background:var(--forest); color:white; font-family:'DM Mono',monospace; font-size:17px; }
    .brand-name { color:var(--ink); font:600 12px 'DM Mono',monospace; letter-spacing:.08em; text-transform:uppercase; }
    .status { margin-left:auto; color:var(--forest); font:500 11px 'DM Mono',monospace; text-transform:uppercase; }
    .hero { border-top:1px solid var(--line); padding:1.45rem 0 1.2rem; }
    .eyebrow { color:var(--coral); font:500 11px 'DM Mono',monospace; text-transform:uppercase; letter-spacing:.08em; }
    .hero h1 { color:var(--ink); font:700 38px/1.12 'Playfair Display',Georgia,serif; margin:.45rem 0 .35rem; }
    .hero p { color:var(--muted); font:400 15px 'DM Sans',sans-serif; margin:0; }
    .section-label { color:var(--muted); font:500 11px 'DM Mono',monospace; text-transform:uppercase; letter-spacing:.08em; }
    .result-head { border-top:1px solid var(--line); padding-top:1.35rem; margin-top:1.5rem; }
    .weather-band { background:var(--mist); border-left:3px solid var(--forest); padding:14px 17px; border-radius:2px; color:var(--ink); margin:.9rem 0 1.3rem; }
    .weather-location { color:var(--muted); font:500 11px 'DM Mono',monospace; text-transform:uppercase; }
    .weather-summary { font:600 15px 'DM Sans',sans-serif; margin-top:4px; }
    .wardrobe-row { display:grid; grid-template-columns:110px 1fr auto; align-items:center; gap:14px; padding:13px 4px; border-bottom:1px solid var(--line); }
    .item-category { color:var(--forest); font:500 10px 'DM Mono',monospace; text-transform:uppercase; }
    .item-name { color:var(--ink); font:600 14px 'DM Sans',sans-serif; }
    .item-color { color:var(--muted); font:400 12px 'DM Sans',sans-serif; }
    .detail-panel { background:#fff; border:1px solid var(--line); border-radius:3px; padding:17px 18px; height:100%; }
    .detail-panel h3 { color:var(--ink); font:600 13px 'DM Mono',monospace; text-transform:uppercase; letter-spacing:.05em; margin:0 0 10px; }
    .detail-panel p { color:var(--ink); font:400 14px/1.55 'DM Sans',sans-serif; margin:0 0 8px; }
    .detail-panel p:last-child { margin-bottom:0; }
    div[data-testid="stFormSubmitButton"] button { background:var(--forest); border-color:var(--forest); color:white; border-radius:3px; min-height:44px; font-weight:600; }
    div[data-testid="stFormSubmitButton"] button:hover { background:#1f4938; border-color:#1f4938; color:white; }
    div[data-testid="stTextInput"] input { border-radius:3px; }
    @media (max-width: 640px) {
        .block-container { padding:1.4rem 1rem 3rem; }
        .hero h1 { font-size:31px; }
        .wardrobe-row { grid-template-columns:78px 1fr; gap:7px 12px; }
        .item-color { grid-column:2; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _friendly_error_message(error: Exception) -> str:
    if isinstance(error, EmptyWardrobeError):
        return "Your wardrobe is empty. Add clothing items to data/wardrobe.json and try again."
    if isinstance(error, WeatherLookupError):
        return "Weather could not be retrieved. Check the location and your internet connection, then try again."
    if isinstance(error, InvalidOutfitPlanError):
        return "The model returned an outfit that could not be matched to your wardrobe. Please try again."
    if isinstance(error, ValueError):
        return str(error)
    return "The recommendation could not be generated. Check that Ollama is running with the configured model, then try again."


def _get_recommendation(occasion: str, location: str) -> OutfitRecommendation:
    return asyncio.run(recommend_outfit(occasion, location))


def _render_recommendation(recommendation: OutfitRecommendation) -> None:
    st.markdown('<div class="result-head"><div class="section-label">Your recommendation</div></div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='weather-band'>"
        "<div class='weather-location'>{}</div>"
        "<div class='weather-summary'>{}</div></div>".format(
            escape(recommendation.occasion),
            escape(recommendation.weather_summary),
        ),
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-label">Selected from your wardrobe</div>', unsafe_allow_html=True)
    for item in recommendation.items:
        st.markdown(
            "<div class='wardrobe-row'>"
            "<div class='item-category'>{}</div>"
            "<div class='item-name'>{}</div>"
            "<div class='item-color'>{}</div></div>".format(
                escape(item.category),
                escape(item.name),
                escape(item.color),
            ),
            unsafe_allow_html=True,
        )

    tips = "".join("<p>{}</p>".format(escape(tip)) for tip in recommendation.styling_tips)
    st.markdown("<div class='detail-panel'><h3>Styling</h3>{}</div>".format(tips or "<p>No styling tips for this outfit.</p>"), unsafe_allow_html=True)
    st.markdown(
        "<div class='detail-panel' style='margin-top:12px'><h3>Why this works</h3><p>{}</p></div>".format(
            escape(recommendation.reasoning)
        ),
        unsafe_allow_html=True,
    )


st.markdown(
    "<div class='brand-row'><div class='brand-mark'>O</div>"
    "<div class='brand-name'>Outfit Studio</div>"
    "<div class='status'>Ollama · Live weather</div></div>"
    "<div class='hero'><div class='eyebrow'>Daily styling</div>"
    "<h1>A good outfit starts with what you own.</h1>"
    "<p>Choose an occasion and location to get a weather-aware look from your wardrobe.</p></div>",
    unsafe_allow_html=True,
)

if "recommendation" not in st.session_state:
    st.session_state.recommendation = None
if "recommendation_error" not in st.session_state:
    st.session_state.recommendation_error = None
with st.form("recommendation_form"):
    st.markdown('<div class="section-label">Plan your outfit</div>', unsafe_allow_html=True)
    occasion_column, location_column = st.columns(2)
    with occasion_column:
        occasion = st.text_input("Occasion", placeholder="e.g. Smart casual, office day", key="occasion")
    with location_column:
        location = st.text_input(
            "Location",
            placeholder="e.g. Bengaluru or Bangalore",
            key="location",
        )
    submitted = st.form_submit_button(
        "Get outfit recommendation",
        type="primary",
        use_container_width=True,
    )

if submitted:
    st.session_state.recommendation = None
    st.session_state.recommendation_error = None
    if not occasion.strip() or not location.strip():
        st.session_state.recommendation_error = "Enter both an occasion and a location to continue."
    else:
        try:
            with st.spinner("Checking your wardrobe and current weather…"):
                st.session_state.recommendation = _get_recommendation(occasion.strip(), location.strip())
        except Exception as error:
            st.session_state.recommendation_error = _friendly_error_message(error)

if st.session_state.recommendation_error:
    st.error(st.session_state.recommendation_error)
elif st.session_state.recommendation is not None:
    _render_recommendation(st.session_state.recommendation)
else:
    st.info("Enter an occasion and location to build your recommendation.")