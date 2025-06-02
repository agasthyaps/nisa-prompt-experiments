import os
import random
import csv
from datetime import datetime
from typing import List, Dict
import itertools

import streamlit as st
from dotenv import load_dotenv
import openai

# Load env vars, especially OPENAI_API_KEY
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

st.set_page_config(page_title="LLM Arena – Side-by-Side", layout="wide")

# ----- Configurable section --------------------------------------------------
# Define models and system prompts independently, so any combination can be compared.

# Available language models
MODELS: List[Dict[str, str]] = [
    {"id": "GPT-4.1", "model": "gpt-4.1"},
    {"id": "GPT-4o", "model": "gpt-4o"},
]

# Available system prompts
SYSTEM_PROMPTS: List[Dict[str, str]] = [
    {"id": "Helpful", "system": "You are a helpful assistant."},
    {"id": "Creative", "system": "You are a creative storytelling assistant. Use vivid language."},
    {"id": "Precise", "system": "You are an expert consultant. Respond concisely and accurately."},
]

TEMPERATURE = 0.7
MAX_TOKENS = 512

DATA_DIR = "data"
VOTE_LOG = os.path.join(DATA_DIR, "votes.csv")

os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------------------------------------------------------


def generate_response(model: str, system_prompt: str, user_prompt: str) -> str:
    """Query the OpenAI chat completion endpoint and return the assistant message."""
    try:
        resp = openai.chat.completions.create(
            model=model,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        # Catch any error from the OpenAI SDK (or others) and surface it gracefully.
        return f"❌ Error from {model}: {e}"


def log_vote(prompt: str, left_id: str, right_id: str, choice: str) -> None:
    """Append a vote record to CSV."""
    header = [
        "timestamp",
        "prompt",
        "left_id",
        "right_id",
        "choice",
    ]
    exists = os.path.isfile(VOTE_LOG)
    with open(VOTE_LOG, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not exists:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "prompt": prompt,
                "left_id": left_id,
                "right_id": right_id,
                "choice": choice,
            }
        )


# Streamlit app UI ------------------------------------------------------------

st.title("🔀 Side-by-Side LLM Duel")

user_prompt = st.text_area(
    "Enter your prompt:",
    value="Explain the concept of blockchain to a 12-year-old.",
    height=120,
)

generate_btn = st.button("Generate Responses", disabled=not user_prompt.strip())

if generate_btn:
    # Build the Cartesian product of all (model, system prompt) combinations
    combos = list(itertools.product(MODELS, SYSTEM_PROMPTS))

    # Randomly pick two distinct combos
    (left_model, left_sys), (right_model, right_sys) = random.sample(combos, 2)

    # Optionally swap left/right randomly for extra entropy
    if random.random() < 0.5:
        left_model, right_model = right_model, left_model
        left_sys, right_sys = right_sys, left_sys

    # Build cfg dicts used downstream (must include id, model, system)
    cfg_left = {
        "id": f"{left_model['id']} + {left_sys['id']}",
        "model": left_model["model"],
        "system": left_sys["system"],
    }
    cfg_right = {
        "id": f"{right_model['id']} + {right_sys['id']}",
        "model": right_model["model"],
        "system": right_sys["system"],
    }

    with st.spinner("Generating responses…"):
        left_resp = generate_response(cfg_left["model"], cfg_left["system"], user_prompt)
        right_resp = generate_response(cfg_right["model"], cfg_right["system"], user_prompt)

    st.session_state["duel"] = {
        "prompt": user_prompt,
        "left": {"cfg": cfg_left, "resp": left_resp},
        "right": {"cfg": cfg_right, "resp": right_resp},
    }

# Existing duel in session?
if duel := st.session_state.get("duel"):
    cols = st.columns(2)
    with cols[0]:
        st.subheader("Left Response")
        st.markdown(duel["left"]["resp"])
    with cols[1]:
        st.subheader("Right Response")
        st.markdown(duel["right"]["resp"])

    st.markdown("---")
    st.write("### Which response do you prefer?")
    choice_col1, choice_col2, tie_col = st.columns([1, 1, 0.5])
    with choice_col1:
        if st.button("👍 Left", key="vote_left"):
            log_vote(duel["prompt"], duel["left"]["cfg"]["id"], duel["right"]["cfg"]["id"], "left")
            st.session_state["choice"] = "left"
    with choice_col2:
        if st.button("👍 Right", key="vote_right"):
            log_vote(duel["prompt"], duel["left"]["cfg"]["id"], duel["right"]["cfg"]["id"], "right")
            st.session_state["choice"] = "right"
    with tie_col:
        if st.button("🤝 Tie", key="vote_tie"):
            log_vote(duel["prompt"], duel["left"]["cfg"]["id"], duel["right"]["cfg"]["id"], "tie")
            st.session_state["choice"] = "tie"

    # Reveal identities once a choice is made
    if choice := st.session_state.get("choice"):
        st.markdown("## ✅ Thanks for voting!")
        st.info(
            f"Left: **{duel['left']['cfg']['id']}** | Right: **{duel['right']['cfg']['id']}** | Your choice: **{choice.capitalize()}**"
        )
        if st.button("Start a new duel"):
            for k in ("duel", "choice"):
                st.session_state.pop(k, None)
            st.rerun() 