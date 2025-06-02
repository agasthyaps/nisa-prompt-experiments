import os
import json
import random
import base64
import mimetypes
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import hashlib

import streamlit as st
from dotenv import load_dotenv
import openai

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Constants
DATA_DIR = "data"
PROMPTS_FILE = os.path.join(DATA_DIR, "system_prompts.json")
VOTES_FILE = os.path.join(DATA_DIR, "votes.json")
SETTINGS_PASSWORD = "admin123"  # Hardcoded password for settings access

# Model configurations
MODELS = [
    {"id": "gpt-4.1", "name": "GPT-4.1"},
    {"id": "gpt-4.5", "name": "GPT-4.5"},
    {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini"},
]

# Default system prompts if file doesn't exist
DEFAULT_PROMPTS = [
    {
        "id": "helpful_assistant",
        "name": "!Saved Prompts Didn't Load",
        "prompt": "You are a helpful, harmless, and honest AI assistant."
    },
]

# Create data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------

def load_system_prompts() -> List[Dict[str, str]]:
    """Load system prompts from file, creating default if doesn't exist."""
    if not os.path.exists(PROMPTS_FILE):
        save_system_prompts(DEFAULT_PROMPTS)
        return DEFAULT_PROMPTS
    
    try:
        with open(PROMPTS_FILE, 'r') as f:
            return json.load(f)
    except:
        return DEFAULT_PROMPTS


def save_system_prompts(prompts: List[Dict[str, str]]) -> None:
    """Save system prompts to file."""
    with open(PROMPTS_FILE, 'w') as f:
        json.dump(prompts, f, indent=2)


def hash_password(password: str) -> str:
    """Simple password hashing for comparison."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str) -> bool:
    """Verify if the provided password matches the settings password."""
    return password == SETTINGS_PASSWORD


def file_to_data_url(file) -> str:
    """Convert an uploaded image file to a base64 data URL."""
    mime = mimetypes.guess_type(file.name)[0] or "image/png"
    b64 = base64.b64encode(file.read()).decode()
    return f"data:{mime};base64,{b64}"


def stream_chat_completion(model: str, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 1000):
    """Stream chat completion from OpenAI."""
    try:
        stream = openai.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"Error: {str(e)}"


def save_vote(conversation: List[Dict], left_config: Dict, right_config: Dict, winner: str) -> None:
    """Save voting data to file."""
    votes = []
    if os.path.exists(VOTES_FILE):
        try:
            with open(VOTES_FILE, 'r') as f:
                votes = json.load(f)
        except:
            votes = []
    
    vote_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "conversation": conversation,
        "left": left_config,
        "right": right_config,
        "winner": winner
    }
    
    votes.append(vote_data)
    
    with open(VOTES_FILE, 'w') as f:
        json.dump(votes, f, indent=2)


# -----------------------------------------------------------------------------
# Streamlit App
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Chat Arena v2",
    page_icon="🤖",
    layout="wide"
)

# Initialize session state
if "authenticated_settings" not in st.session_state:
    st.session_state.authenticated_settings = False

if "show_settings" not in st.session_state:
    st.session_state.show_settings = False

if "conversation_started" not in st.session_state:
    st.session_state.conversation_started = False

if "messages_left" not in st.session_state:
    st.session_state.messages_left = []

if "messages_right" not in st.session_state:
    st.session_state.messages_right = []

if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

if "voting_phase" not in st.session_state:
    st.session_state.voting_phase = False

if "left_config" not in st.session_state:
    st.session_state.left_config = None

if "right_config" not in st.session_state:
    st.session_state.right_config = None

# Header with settings button
col1, col2 = st.columns([1, 20])
with col1:
    if st.button("⚙️", help="Settings"):
        st.session_state.show_settings = not st.session_state.show_settings

with col2:
    st.title("🤖 Chat Arena v2")

# Settings Panel
if st.session_state.show_settings:
    with st.sidebar:
        st.header("⚙️ Settings")
        
        if not st.session_state.authenticated_settings:
            password = st.text_input("Enter password to access settings:", type="password")
            if st.button("Unlock Settings"):
                if verify_password(password):
                    st.session_state.authenticated_settings = True
                    st.rerun()
                else:
                    st.error("Incorrect password")
        else:
            st.success("Settings unlocked!")
            
            # Load current prompts
            prompts = load_system_prompts()
            
            st.subheader("System Prompts")
            
            # Display and edit existing prompts
            updated_prompts = []
            for i, prompt in enumerate(prompts):
                with st.expander(f"{prompt['name']} ({prompt['id']})"):
                    name = st.text_input("Name", value=prompt['name'], key=f"name_{i}")
                    prompt_text = st.text_area("Prompt", value=prompt['prompt'], key=f"prompt_{i}", height=100)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Update", key=f"update_{i}"):
                            prompt['name'] = name
                            prompt['prompt'] = prompt_text
                            st.success("Updated!")
                    
                    with col2:
                        if st.button("Delete", key=f"delete_{i}"):
                            st.session_state[f"confirm_delete_{i}"] = True
                    
                    if st.session_state.get(f"confirm_delete_{i}", False):
                        st.warning("Are you sure you want to delete this prompt?")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("Yes, delete", key=f"confirm_yes_{i}"):
                                continue  # Skip adding this prompt to updated_prompts
                        with col2:
                            if st.button("Cancel", key=f"confirm_no_{i}"):
                                st.session_state[f"confirm_delete_{i}"] = False
                    
                    if not st.session_state.get(f"confirm_delete_{i}", False):
                        updated_prompts.append({
                            "id": prompt['id'],
                            "name": name,
                            "prompt": prompt_text
                        })
            
            # Add new prompt
            st.subheader("Add New Prompt")
            new_name = st.text_input("New prompt name")
            new_prompt = st.text_area("New prompt text", height=100)
            if st.button("Add Prompt") and new_name and new_prompt:
                new_id = new_name.lower().replace(" ", "_")
                updated_prompts.append({
                    "id": new_id,
                    "name": new_name,
                    "prompt": new_prompt
                })
                save_system_prompts(updated_prompts)
                st.success("Prompt added!")
                st.rerun()
            
            # Save all changes
            if st.button("Save All Changes", type="primary"):
                save_system_prompts(updated_prompts)
                st.success("All changes saved!")
                st.rerun()
            
            if st.button("Lock Settings"):
                st.session_state.authenticated_settings = False
                st.session_state.show_settings = False
                st.rerun()

# Main Chat Arena Interface
if not st.session_state.conversation_started:
    st.markdown("### Welcome to Chat Arena!")
    st.markdown("Two AI assistants will compete to provide the best responses to your questions.")
    st.markdown("Chat with both, then vote for the winner!")
    
    if st.button("Start New Conversation", type="primary"):
        # Load prompts and models
        prompts = load_system_prompts()
        
        # Randomly select configurations
        left_prompt = random.choice(prompts)
        right_prompt = random.choice(prompts)
        left_model = random.choice(MODELS)
        right_model = random.choice(MODELS)
        
        # Initialize conversation
        st.session_state.left_config = {
            "model": left_model,
            "prompt": left_prompt
        }
        st.session_state.right_config = {
            "model": right_model,
            "prompt": right_prompt
        }
        
        st.session_state.messages_left = [
            {"role": "system", "content": left_prompt["prompt"]}
        ]
        st.session_state.messages_right = [
            {"role": "system", "content": right_prompt["prompt"]}
        ]
        
        st.session_state.conversation_started = True
        st.session_state.conversation_history = []
        st.session_state.voting_phase = False
        st.rerun()

elif not st.session_state.voting_phase:
    # Chat interface
    left_col, right_col = st.columns(2)
    
    with left_col:
        st.subheader("Assistant A")
        for msg in st.session_state.conversation_history:
            with st.chat_message("user"):
                st.write(msg["user"])
            with st.chat_message("assistant"):
                st.write(msg["left"])
    
    with right_col:
        st.subheader("Assistant B")
        for msg in st.session_state.conversation_history:
            with st.chat_message("user"):
                st.write(msg["user"])
            with st.chat_message("assistant"):
                st.write(msg["right"])
    
    # Input form
    with st.form("chat_input", clear_on_submit=True):
        user_input = st.text_input("Your message:")
        uploaded_files = st.file_uploader(
            "Upload images (optional)",
            type=["png", "jpg", "jpeg"],
            accept_multiple_files=True
        )
        
        col1, col2, col3 = st.columns([1, 1, 8])
        with col1:
            submitted = st.form_submit_button("Send", type="primary")
        with col2:
            end_chat = st.form_submit_button("End & Vote")
    
    if submitted and user_input:
        # Prepare message content
        content = [{"type": "text", "text": user_input}]
        for file in uploaded_files or []:
            content.append({
                "type": "image_url",
                "image_url": {"url": file_to_data_url(file)}
            })
        
        # Add user message to both conversations
        user_msg = {"role": "user", "content": content if len(content) > 1 else user_input}
        st.session_state.messages_left.append(user_msg)
        st.session_state.messages_right.append(user_msg)
        
        # Get responses
        left_response = ""
        right_response = ""
        
        # Create columns for responses
        left_col_resp, right_col_resp = st.columns(2)
        
        # Display user messages
        with left_col_resp:
            with st.chat_message("user"):
                st.write(user_input)
            with st.chat_message("assistant"):
                left_placeholder = st.empty()
        
        with right_col_resp:
            with st.chat_message("user"):
                st.write(user_input)
            with st.chat_message("assistant"):
                right_placeholder = st.empty()
        
        # Create streaming generators
        left_stream = stream_chat_completion(
            st.session_state.left_config["model"]["id"],
            st.session_state.messages_left
        )
        right_stream = stream_chat_completion(
            st.session_state.right_config["model"]["id"],
            st.session_state.messages_right
        )
        
        # Stream both responses in an interleaved fashion
        left_done = False
        right_done = False
        
        while not (left_done and right_done):
            # Process left stream
            if not left_done:
                try:
                    chunk = next(left_stream)
                    left_response += chunk
                    left_placeholder.markdown(left_response + "▌")
                except StopIteration:
                    left_done = True
                    left_placeholder.markdown(left_response)
            
            # Process right stream
            if not right_done:
                try:
                    chunk = next(right_stream)
                    right_response += chunk
                    right_placeholder.markdown(right_response + "▌")
                except StopIteration:
                    right_done = True
                    right_placeholder.markdown(right_response)
        
        # Add assistant responses
        st.session_state.messages_left.append({"role": "assistant", "content": left_response})
        st.session_state.messages_right.append({"role": "assistant", "content": right_response})
        
        # Add to conversation history
        st.session_state.conversation_history.append({
            "user": user_input,
            "left": left_response,
            "right": right_response
        })
        
        st.rerun()
    
    if end_chat:
        st.session_state.voting_phase = True
        st.rerun()

else:
    # Voting phase
    st.markdown("## Time to vote!")
    st.markdown("Which assistant provided better responses overall?")
    
    # Show the conversation
    left_col, right_col = st.columns(2)
    
    with left_col:
        st.subheader("Assistant A")
        for msg in st.session_state.conversation_history:
            with st.chat_message("user"):
                st.write(msg["user"])
            with st.chat_message("assistant"):
                st.write(msg["left"])
    
    with right_col:
        st.subheader("Assistant B")
        for msg in st.session_state.conversation_history:
            with st.chat_message("user"):
                st.write(msg["user"])
            with st.chat_message("assistant"):
                st.write(msg["right"])
    
    # Voting buttons
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🏆 Assistant A Wins", type="primary"):
            save_vote(
                st.session_state.conversation_history,
                st.session_state.left_config,
                st.session_state.right_config,
                "left"
            )
            st.balloons()
            st.success("Vote recorded! Thank you!")
            st.info(f"Assistant A was: {st.session_state.left_config['model']['name']} with {st.session_state.left_config['prompt']['name']}")
            st.info(f"Assistant B was: {st.session_state.right_config['model']['name']} with {st.session_state.right_config['prompt']['name']}")
    
    with col2:
        if st.button("🏆 Assistant B Wins", type="primary"):
            save_vote(
                st.session_state.conversation_history,
                st.session_state.left_config,
                st.session_state.right_config,
                "right"
            )
            st.balloons()
            st.success("Vote recorded! Thank you!")
            st.info(f"Assistant A was: {st.session_state.left_config['model']['name']} with {st.session_state.left_config['prompt']['name']}")
            st.info(f"Assistant B was: {st.session_state.right_config['model']['name']} with {st.session_state.right_config['prompt']['name']}")
    
    with col3:
        if st.button("🤝 It's a Tie"):
            save_vote(
                st.session_state.conversation_history,
                st.session_state.left_config,
                st.session_state.right_config,
                "tie"
            )
            st.success("Vote recorded! Thank you!")
            st.info(f"Assistant A was: {st.session_state.left_config['model']['name']} with {st.session_state.left_config['prompt']['name']}")
            st.info(f"Assistant B was: {st.session_state.right_config['model']['name']} with {st.session_state.right_config['prompt']['name']}")
    
    if st.button("Start New Conversation"):
        st.session_state.conversation_started = False
        st.session_state.voting_phase = False
        st.rerun() 