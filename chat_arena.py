import os
import random
import csv
import base64
import mimetypes
from datetime import datetime
from typing import List, Dict
import itertools
import concurrent.futures
import queue
import time

import streamlit as st
from dotenv import load_dotenv
import openai
from prompts import nisa_a, nisa_b, nisa_c

# -----------------------------------------------------------------------------
# Environment & API setup
# -----------------------------------------------------------------------------
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
MODELS: List[Dict[str, str]] = [
    {"id": "GPT-4.1", "model": "gpt-4.1"},
    {"id": "GPT-4o", "model": "gpt-4o"},
]

SYSTEM_PROMPTS: List[Dict[str, str]] = [
    {"id": "NISA A [OG]", "system": nisa_a},
    {"id": "NISA B [Core Actions w Examples]", "system": nisa_b},
    {"id": "NISA C [Basic Teacher Moves]", "system": nisa_c},
]

TEMPERATURE = 0.7
MAX_TOKENS = 512

DATA_DIR = "data"
VOTE_LOG = os.path.join(DATA_DIR, "votes.csv")

os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

def file_to_data_url(file) -> str:
    """Convert an uploaded image file to a base64 data URL accepted by OpenAI Vision."""
    mime = mimetypes.guess_type(file.name)[0] or "image/png"
    b64 = base64.b64encode(file.read()).decode()
    return f"data:{mime};base64,{b64}"


def stream_model_response(model: str, messages: List[Dict]):
    """Yield tokens from a streaming chat completion."""
    response_stream = openai.chat.completions.create(
        model=model,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        messages=messages,
        stream=True,
    )
    for chunk in response_stream:
        token = chunk.choices[0].delta.content or ""
        if token:
            yield token


def log_vote(turns: List[Dict], left_id: str, right_id: str, choice: str) -> None:
    """Append a vote record to CSV file."""
    header = ["timestamp", "conversation", "left_id", "right_id", "choice"]
    exists = os.path.isfile(VOTE_LOG)
    with open(VOTE_LOG, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not exists:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "conversation": turns,
                "left_id": left_id,
                "right_id": right_id,
                "choice": choice,
            }
        )

# -----------------------------------------------------------------------------
# Streamlit UI & State management
# -----------------------------------------------------------------------------

st.set_page_config(page_title="LLM Chat Duel", layout="wide")

# --- Utility to initialise / reset a duel -----------------------------------

def init_duel():
    """Create new assistant configs and reset conversation state."""
    combos = list(itertools.product(MODELS, SYSTEM_PROMPTS))
    (left_model, left_sys), (right_model, right_sys) = random.sample(combos, 2)
    st.session_state["duel"] = {
        "left_cfg": {
            "id": f"{left_model['id']} + {left_sys['id']}",
            "model": left_model["model"],
            "system": left_sys["system"],
        },
        "right_cfg": {
            "id": f"{right_model['id']} + {right_sys['id']}",
            "model": right_model["model"],
            "system": right_sys["system"],
        },
    }
    st.session_state["history_left"] = [
        {"role": "system", "content": st.session_state["duel"]["left_cfg"]["system"]}
    ]
    st.session_state["history_right"] = [
        {"role": "system", "content": st.session_state["duel"]["right_cfg"]["system"]}
    ]
    st.session_state["turns"] = []
    st.session_state["vote_stage"] = False
    st.session_state["chosen"] = None


# Initialise duel if not present
if "duel" not in st.session_state:
    st.subheader("Configure your duel")
    prompt_ids = [p["id"] for p in SYSTEM_PROMPTS]
    cfg_cols = st.columns(2)
    with cfg_cols[0]:
        left_choice = st.selectbox("Left assistant – system prompt", prompt_ids, key="left_sys_choice")
    with cfg_cols[1]:
        right_choice = st.selectbox("Right assistant – system prompt", prompt_ids, index=1, key="right_sys_choice")

    if st.button("Start Duel", type="primary"):
        left_sys = next(p for p in SYSTEM_PROMPTS if p["id"] == left_choice)
        right_sys = next(p for p in SYSTEM_PROMPTS if p["id"] == right_choice)
        left_model = random.choice(MODELS)
        right_model = random.choice(MODELS)

        st.session_state["duel"] = {
            "left_cfg": {
                "id": f"{left_model['id']} + {left_sys['id']}",
                "model": left_model["model"],
                "system": left_sys["system"],
            },
            "right_cfg": {
                "id": f"{right_model['id']} + {right_sys['id']}",
                "model": right_model["model"],
                "system": right_sys["system"],
            },
        }
        st.session_state["history_left"] = [{"role": "system", "content": left_sys["system"]}]
        st.session_state["history_right"] = [{"role": "system", "content": right_sys["system"]}]
        st.session_state["turns"] = []
        st.session_state["vote_stage"] = False
        st.session_state["chosen"] = None
        st.rerun()

    # Prevent the rest of the app from executing until the duel is configured.
    st.stop()

# --- Utility to fully reset Streamlit session state for a fresh duel -------

def reset_duel_state():
    """Remove all duel-related keys so the app starts from a clean slate."""
    for key in (
        "duel",
        "history_left",
        "history_right",
        "turns",
        "vote_stage",
        "chosen",
    ):
        st.session_state.pop(key, None)
    st.rerun()

# Title
st.title("🤖🔀 Chat-based LLM Duel")

# Display current chat turns
cols = st.columns(2)
with cols[0]:
    st.subheader("Left Assistant")
    for t in st.session_state["turns"]:
        st.chat_message("user").markdown(t["user_display"])
        st.chat_message("assistant").markdown(t["left_resp"])
with cols[1]:
    st.subheader("Right Assistant")
    for t in st.session_state["turns"]:
        st.chat_message("user").markdown(t["user_display"])
        st.chat_message("assistant").markdown(t["right_resp"])

# If voting stage, skip chat input
if not st.session_state["vote_stage"]:
    with st.form("user_input_form", clear_on_submit=True):
        user_text = st.text_input("Your message")
        uploaded_files = st.file_uploader(
            "Upload image(s) (optional)",
            type=["png", "jpg", "jpeg"],
            accept_multiple_files=True,
        )
        submitted = st.form_submit_button("Send")

    if submitted and (user_text.strip() or uploaded_files):
        # Build content for OpenAI vision capable messages
        content_blocks = []
        if user_text.strip():
            content_blocks.append({"type": "text", "text": user_text})
        for f in uploaded_files or []:
            content_blocks.append({"type": "image_url", "image_url": {"url": file_to_data_url(f)}})

        user_message = {"role": "user", "content": content_blocks}
        # Append to histories
        st.session_state["history_left"].append(user_message)
        st.session_state["history_right"].append(user_message)

        # Display user message in both columns
        user_display = user_text if user_text.strip() else "(Image)"
        if uploaded_files:
            user_display += " (with image)"

        # Placeholders for streaming
        left_ph = cols[0].chat_message("assistant").empty()
        right_ph = cols[1].chat_message("assistant").empty()

        # Stream both assistants in parallel so their responses appear simultaneously
        def _collect_tokens(model_name, history, q):
            for tok in stream_model_response(model_name, history):
                q.put(tok)
            q.put(None)  # Sentinel to indicate completion

        # Create queues to communicate tokens back to main thread
        left_q: queue.Queue[str | None] = queue.Queue()
        right_q: queue.Queue[str | None] = queue.Queue()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            pool.submit(
                _collect_tokens,
                st.session_state["duel"]["left_cfg"]["model"],
                st.session_state["history_left"],
                left_q,
            )
            pool.submit(
                _collect_tokens,
                st.session_state["duel"]["right_cfg"]["model"],
                st.session_state["history_right"],
                right_q,
            )

            left_resp_collected = ""
            right_resp_collected = ""
            left_done = right_done = False

            # Loop until both sides have finished streaming
            while not (left_done and right_done):
                # Process left queue
                try:
                    tok = left_q.get_nowait()
                    if tok is None:
                        left_done = True
                    else:
                        left_resp_collected += tok
                        left_ph.markdown(left_resp_collected + "▌")
                except queue.Empty:
                    pass

                # Process right queue
                try:
                    tok = right_q.get_nowait()
                    if tok is None:
                        right_done = True
                    else:
                        right_resp_collected += tok
                        right_ph.markdown(right_resp_collected + "▌")
                except queue.Empty:
                    pass

                time.sleep(0.01)

            # Final render without cursor
            left_ph.markdown(left_resp_collected)
            right_ph.markdown(right_resp_collected)

        # Commit responses to history
        st.session_state["history_left"].append(
            {"role": "assistant", "content": left_resp_collected}
        )
        st.session_state["history_right"].append(
            {"role": "assistant", "content": right_resp_collected}
        )

        # Add to turns for future display
        st.session_state["turns"].append(
            {
                "user_display": user_display,
                "left_resp": left_resp_collected,
                "right_resp": right_resp_collected,
            }
        )

    st.divider()
    if st.button("Vote Now / Finish Chat", type="primary", disabled=len(st.session_state["turns"]) == 0):
        st.session_state["vote_stage"] = True
        st.rerun()

# Voting interface
if st.session_state["vote_stage"] and st.session_state["chosen"] is None:
    st.markdown("## Which assistant performed better overall?")
    vote_cols = st.columns([1, 1, 0.6])
    with vote_cols[0]:
        if st.button("👍 Left", key="vote_left_final"):
            st.session_state["chosen"] = "left"
    with vote_cols[1]:
        if st.button("👍 Right", key="vote_right_final"):
            st.session_state["chosen"] = "right"
    with vote_cols[2]:
        if st.button("🤝 Tie", key="vote_tie_final"):
            st.session_state["chosen"] = "tie"

    # Insert reset option before a vote is cast
    st.markdown("---")
    if st.button("🔄 Start a new duel", key="restart_before_vote"):
        reset_duel_state()

    if st.session_state["chosen"] is not None:
        log_vote(
            st.session_state["turns"],
            st.session_state["duel"]["left_cfg"]["id"],
            st.session_state["duel"]["right_cfg"]["id"],
            st.session_state["chosen"],
        )
        st.success("Thank you for voting!")
        st.info(
            f"Left: **{st.session_state['duel']['left_cfg']['id']}** | "
            f"Right: **{st.session_state['duel']['right_cfg']['id']}** | "
            f"Your choice: **{st.session_state['chosen'].capitalize()}**"
        )
        if st.button("Start a new duel"):
            reset_duel_state() 