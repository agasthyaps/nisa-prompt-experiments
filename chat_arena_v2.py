import os
import json
import random
import base64
import mimetypes
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import hashlib
import sqlite3

import streamlit as st
from dotenv import load_dotenv
import openai

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Constants
SETTINGS_PASSWORD = "admin123"  # Hardcoded password for settings access

# Model configurations
MODELS = [
    {"id": "gpt-4.1", "name": "GPT-4.1"},
    {"id": "gpt-4.5-preview", "name": "GPT-4.5 Preview"},
    {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini"},
]

# Default system prompts if database doesn't exist
DEFAULT_PROMPTS = [
    {
        "id": "helpful_assistant",
        "name": "!Saved Prompts Didn't Load",
        "prompt": "You are a helpful, harmless, and honest AI assistant."
    },
]

# -----------------------------------------------------------------------------
# Database Functions
# -----------------------------------------------------------------------------

def init_db():
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect('nisa_arena.db')
    c = conn.cursor()
    
    # Create prompts table if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS prompts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            prompt TEXT NOT NULL,
            active INTEGER DEFAULT 1
        )
    ''')
    
    # Add active column to existing tables if it doesn't exist
    c.execute("PRAGMA table_info(prompts)")
    columns = [column[1] for column in c.fetchall()]
    if 'active' not in columns:
        c.execute('ALTER TABLE prompts ADD COLUMN active INTEGER DEFAULT 1')
    
    # Create votes table if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            conversation TEXT NOT NULL,
            left_config TEXT NOT NULL,
            right_config TEXT NOT NULL,
            winner TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

def load_system_prompts() -> List[Dict[str, str]]:
    """Load system prompts from database, creating default if doesn't exist."""
    conn = sqlite3.connect('nisa_arena.db')
    c = conn.cursor()
    
    # Check if we have any prompts
    c.execute('SELECT COUNT(*) FROM prompts')
    count = c.fetchone()[0]
    
    if count == 0:
        # Insert default prompts
        for prompt in DEFAULT_PROMPTS:
            c.execute('INSERT INTO prompts (id, name, prompt, active) VALUES (?, ?, ?, ?)',
                     (prompt['id'], prompt['name'], prompt['prompt'], 1))
        conn.commit()
        prompts = [dict(prompt, active=True) for prompt in DEFAULT_PROMPTS]
    else:
        # Load existing prompts
        c.execute('SELECT id, name, prompt, active FROM prompts')
        prompts = [{'id': row[0], 'name': row[1], 'prompt': row[2], 'active': bool(row[3])} for row in c.fetchall()]
    
    conn.close()
    return prompts

def load_active_prompts() -> List[Dict[str, str]]:
    """Load only active system prompts from database."""
    conn = sqlite3.connect('nisa_arena.db')
    c = conn.cursor()
    
    c.execute('SELECT id, name, prompt FROM prompts WHERE active = 1')
    prompts = [{'id': row[0], 'name': row[1], 'prompt': row[2]} for row in c.fetchall()]
    
    conn.close()
    return prompts

def save_system_prompts(prompts: List[Dict[str, str]]) -> None:
    """Save system prompts to database."""
    conn = sqlite3.connect('nisa_arena.db')
    c = conn.cursor()
    
    # Clear existing prompts
    c.execute('DELETE FROM prompts')
    
    # Insert new prompts
    for prompt in prompts:
        active = prompt.get('active', True)  # Default to active if not specified
        c.execute('INSERT INTO prompts (id, name, prompt, active) VALUES (?, ?, ?, ?)',
                 (prompt['id'], prompt['name'], prompt['prompt'], int(active)))
    
    conn.commit()
    conn.close()

def save_vote(conversation: List[Dict], left_config: Dict, right_config: Dict, winner: str) -> None:
    """Save voting data to database."""
    conn = sqlite3.connect('nisa_arena.db')
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO votes (timestamp, conversation, left_config, right_config, winner)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        datetime.utcnow().isoformat(),
        json.dumps(conversation),
        json.dumps(left_config),
        json.dumps(right_config),
        winner
    ))
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# with open('data/system_prompts.json', 'r') as f:
#     existing_prompts = json.load(f)
#     save_system_prompts(existing_prompts)

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------

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


def format_response_with_tags(response: str) -> str:
    """Format response to style inner monologue and output sections."""
    import re
    
    # Replace <innermonologue> tags with styled content
    def replace_inner_monologue(match):
        content = match.group(1).strip()
        # Use markdown formatting instead of HTML
        return f'\n**Inner monologue:**\n*{content}*\n'
    
    # Replace <output> tags with styled content
    def replace_output(match):
        content = match.group(1).strip()
        # Use markdown formatting with clear separation
        return f'\n**Final response:**\n\n**{content}**\n'
    
    # Apply replacements
    formatted = response
    
    # Handle inner monologue tags (case insensitive)
    formatted = re.sub(
        r'<innermonologue>(.*?)</innermonologue>', 
        replace_inner_monologue, 
        formatted, 
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # Handle output tags (case insensitive)
    formatted = re.sub(
        r'<output>(.*?)</output>', 
        replace_output, 
        formatted, 
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # If no tags were found, return the original response
    if formatted == response:
        return response
    
    return formatted


# -----------------------------------------------------------------------------
# Streamlit App
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="nisa labs",
    page_icon="🧪",
    layout="wide"
)

# Custom CSS for 80s Apple aesthetic with modern touches
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&family=Space+Grotesk:wght@300;400;700&display=swap');
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    .stDeployButton {display:none;}
    footer {visibility: hidden;}
    
    /* Remove forced backgrounds - let Streamlit handle theme colors */
    
    /* Typography - Base styles */
    h1 {
        font-family: 'Space Grotesk', sans-serif !important;
        font-size: 72px !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        background: linear-gradient(135deg, #0066CC 0%, #FF6B6B 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-fill-color: transparent;
        margin-bottom: 2rem !important;
        text-transform: lowercase;
    }
    
    h2 {
        font-family: 'Space Grotesk', sans-serif !important;
        font-size: 48px !important;
        font-weight: 700 !important;
        margin-bottom: 1.5rem !important;
    }
    
    h3 {
        font-family: 'Space Grotesk', sans-serif !important;
        font-size: 32px !important;
        font-weight: 600 !important;
        margin-bottom: 1rem !important;
    }
    
    /* Markdown text */
    .stMarkdown {
        font-family: 'Space Grotesk', sans-serif !important;
        font-size: 18px !important;
        line-height: 1.6 !important;
    }
    
    /* Button styling - chunky 80s inspired */
    .stButton > button {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 18px !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 16px 32px !important;
        border: 4px solid currentColor !important;
        border-radius: 0 !important;
        box-shadow: 6px 6px 0px currentColor !important;
        transition: all 0.1s ease !important;
        margin: 8px 0 !important;
    }
    
    .stButton > button:hover {
        transform: translate(2px, 2px);
        box-shadow: 4px 4px 0px currentColor !important;
    }
    
    .stButton > button:active {
        transform: translate(4px, 4px);
        box-shadow: 2px 2px 0px currentColor !important;
    }
    
    /* Primary button styling */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0066CC 0%, #0052A3 100%) !important;
        color: #FFFFFF !important;
        border-color: #0066CC !important;
        box-shadow: 6px 6px 0px #0052A3 !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        box-shadow: 4px 4px 0px #0052A3 !important;
    }
    
    /* Text input styling */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 16px !important;
        border: 3px solid currentColor !important;
        border-radius: 0 !important;
        box-shadow: 4px 4px 0px currentColor !important;
        padding: 12px 16px !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #0066CC !important;
        box-shadow: 4px 4px 0px #0066CC !important;
        outline: none !important;
    }
    
    /* Select box styling */
    .stSelectbox > div > div {
        border: 3px solid currentColor !important;
        border-radius: 0 !important;
        box-shadow: 4px 4px 0px currentColor !important;
    }
    
    /* Chat message styling */
    .stChatMessage {
        border: 3px solid currentColor !important;
        border-radius: 0 !important;
        box-shadow: 4px 4px 0px currentColor !important;
        margin-bottom: 16px !important;
        padding: 20px !important;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] .stButton > button {
        border: 3px solid currentColor !important;
        box-shadow: 3px 3px 0px currentColor !important;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 16px !important;
        font-weight: 700 !important;
        border: 3px solid currentColor !important;
        border-radius: 0 !important;
        box-shadow: 3px 3px 0px currentColor !important;
    }
    
    /* Column styling for chat interface */
    [data-testid="column"] {
        padding: 20px !important;
        background-color: var(--background-color);
        border: 2px solid var(--secondary-background-color);
        margin: 10px !important;
    }
    
    /* Success/Error/Warning messages */
    .stAlert {
        border: 3px solid currentColor !important;
        border-radius: 0 !important;
        box-shadow: 4px 4px 0px currentColor !important;
        font-family: 'IBM Plex Mono', monospace !important;
    }
    
    /* File uploader */
    .stFileUploader {
        border: 3px dashed currentColor !important;
        border-radius: 0 !important;
        padding: 20px !important;
    }
    
    /* Special styling for main menu buttons */
    .main-menu-button {
        width: 100%;
        height: 200px !important;
        font-size: 28px !important;
        border: 6px solid currentColor !important;
        box-shadow: 12px 12px 0px currentColor !important;
        margin: 20px 0 !important;
        transition: all 0.2s ease !important;
    }
    
    .main-menu-button:hover {
        transform: translate(4px, 4px);
        box-shadow: 8px 8px 0px currentColor !important;
        background: linear-gradient(135deg, #0066CC 0%, #0052A3 100%) !important;
        color: #FFFFFF !important;
    }
    
    /* Voting buttons special styling */
    .vote-button {
        height: 120px !important;
        font-size: 24px !important;
        background: linear-gradient(135deg, #FFD700 0%, #FFC107 100%) !important;
        border: 4px solid currentColor !important;
        box-shadow: 8px 8px 0px currentColor !important;
    }
    
    /* Experimental gradient borders */
    @keyframes gradient-border {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    .gradient-border {
        background: linear-gradient(135deg, #0066CC, #FF6B6B, #FFD700, #0066CC);
        background-size: 400% 400%;
        animation: gradient-border 10s ease infinite;
        padding: 4px;
    }
    
    /* Code blocks */
    .stCodeBlock {
        border: 3px solid currentColor !important;
        border-radius: 0 !important;
        box-shadow: 4px 4px 0px currentColor !important;
    }
    
    /* Make certain elements more prominent */
    div[data-testid="stMetricValue"] {
        font-size: 48px !important;
        font-weight: 700 !important;
        font-family: 'IBM Plex Mono', monospace !important;
    }
    
    /* ============================================== */
    /* DARK MODE SPECIFIC ADJUSTMENTS */
    /* ============================================== */
    
    /* Dark mode gradient title - brighter for visibility */
    @media (prefers-color-scheme: dark) {
        h1 {
            background: linear-gradient(135deg, #4d94ff 0%, #ff9999 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-fill-color: transparent;
        }
    }
    
    [data-theme="dark"] h1 {
        background: linear-gradient(135deg, #4d94ff 0%, #ff9999 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        text-fill-color: transparent !important;
    }
    
    /* Dark mode primary buttons remain colorful */
    [data-theme="dark"] .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0066CC 0%, #0052A3 100%) !important;
        color: #FFFFFF !important;
        border-color: #0066CC !important;
        box-shadow: 6px 6px 0px #003d7a !important;
    }
    
    /* Dark mode voting buttons */
    [data-theme="dark"] .vote-button {
        background: linear-gradient(135deg, #cc9900 0%, #b38600 100%) !important;
        color: #FFFFFF !important;
    }
    
    /* Dark mode gradient borders - brighter */
    [data-theme="dark"] .gradient-border {
        background: linear-gradient(135deg, #4d94ff, #ff9999, #cc9900, #4d94ff) !important;
    }
    
    /* Paper texture overlay - subtle for both themes */
    .stApp::before {
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        opacity: 0.02;
        background-image: 
            repeating-linear-gradient(
                45deg,
                transparent,
                transparent 35px,
                rgba(128, 128, 128, 0.02) 35px,
                rgba(128, 128, 128, 0.02) 70px
            );
        pointer-events: none;
        z-index: 1;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "authenticated_settings" not in st.session_state:
    st.session_state.authenticated_settings = False

if "show_settings" not in st.session_state:
    st.session_state.show_settings = False

if "conversation_started" not in st.session_state:
    st.session_state.conversation_started = False

if "messages" not in st.session_state:
    st.session_state.messages = []

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

if "chat_mode" not in st.session_state:
    st.session_state.chat_mode = None

# Header with settings button
col1, col2 = st.columns([1, 20])
with col1:
    if st.button("⚙️", help="Settings"):
        st.session_state.show_settings = not st.session_state.show_settings

with col2:
    st.title("nisa labs")

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
            st.markdown("land on a good prompt? want to test an existing one? use this [sheet](https://docs.google.com/spreadsheets/d/1UlNmas25Y0yEwp_1iVowUwH6od5zvSeZYYdzLlKjH1c/edit?gid=0#gid=0).") 
            
            # Display and edit existing prompts
            updated_prompts = []
            for i, prompt in enumerate(prompts):
                # Style based on active status
                status_emoji = "✅" if prompt.get('active', True) else "❌"
                header_text = f"{status_emoji} {prompt['name']} ({prompt['id']})"
                
                with st.expander(header_text):
                    # Active/Inactive toggle
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**Status:** {'Active' if prompt.get('active', True) else 'Inactive'}")
                    with col2:
                        if prompt.get('active', True):
                            if st.button("Deactivate", key=f"deactivate_{i}"):
                                prompt['active'] = False
                                save_system_prompts(prompts)
                                st.rerun()
                        else:
                            if st.button("Activate", key=f"activate_{i}"):
                                prompt['active'] = True
                                save_system_prompts(prompts)
                                st.rerun()
                    
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
                            "prompt": prompt_text,
                            "active": prompt.get('active', True)
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

# Main Interface
if not st.session_state.conversation_started:
    st.markdown("""
    <div style="text-align: center; margin: 60px 0;">
        <h1 style="font-size: 84px; margin-bottom: 20px;">prompt playground</h1>
        <p style="font-size: 24px; color: #666; margin-bottom: 60px;">choose your chat mode. admins can add or edit prompts (⚙️). these nisas don't have access to tools.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="gradient-border" style="height: 250px; display: flex; align-items: center; justify-content: center;">
            <div style="width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center;">
                <h2 style="font-size: 42px; margin: 0;">single chat</h2>
                <p style="font-size: 18px; color: #666; margin-top: 10px;">Chat with a single version of nisa</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("ENTER SINGLE CHAT", type="primary", use_container_width=True):
            st.session_state.chat_mode = "single"
            st.session_state.conversation_started = True
            st.rerun()
    
    with col2:
        st.markdown("""
        <div class="gradient-border" style="height: 250px; display: flex; align-items: center; justify-content: center;">
            <div style="width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center;">
                <h2 style="font-size: 42px; margin: 0;">head-to-head</h2>
                <p style="font-size: 18px; color: #666; margin-top: 10px;">Compare two versions of nisa</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("ENTER HEAD-TO-HEAD", type="primary", use_container_width=True):
            st.session_state.chat_mode = "head2head"
            st.session_state.conversation_started = True
            # Initialize head-to-head configurations
            prompts = load_active_prompts()  # Use only active prompts
            
            # Randomly select models and prompts
            left_model = random.choice(MODELS)
            right_model = random.choice(MODELS)
            left_prompt = random.choice(prompts)
            right_prompt = random.choice(prompts)
            
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
            st.rerun()

elif st.session_state.chat_mode == "single":
    # Back button
    if st.button("← Back to Main Menu"):
        st.session_state.conversation_started = False
        st.session_state.chat_mode = None
        st.session_state.messages = []
        st.rerun()
    
    # Single chat interface
    if not st.session_state.messages:
        # Initial setup for single chat
        prompts = load_active_prompts()  # Use only active prompts
        
        # Model and prompt selection
        col1, col2 = st.columns(2)
        with col1:
            selected_model = st.selectbox(
                "Select Model",
                options=MODELS,
                format_func=lambda x: x["name"]
            )
        
        with col2:
            selected_prompt = st.selectbox(
                "Select System Prompt",
                options=prompts,
                format_func=lambda x: x["name"]
            )
        
        if st.button("Start Chat", type="primary"):
            st.session_state.messages = [
                {"role": "system", "content": selected_prompt["prompt"]}
            ]
            st.session_state.current_config = {
                "model": selected_model,
                "prompt": selected_prompt
            }
            st.rerun()
    
    else:
        # Display chat history
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.messages:
                if msg["role"] != "system":
                    with st.chat_message(msg["role"]):
                        if msg["role"] == "assistant":
                            # Display formatted response for assistant messages
                            st.write(format_response_with_tags(msg["content"]))
                        else:
                            st.write(msg["content"])
        
        # Input form
        with st.form("chat_input", clear_on_submit=True):
            user_input = st.text_input("Your message:")
            uploaded_files = st.file_uploader(
                "Upload images (optional)",
                type=["png", "jpg", "jpeg"],
                accept_multiple_files=True
            )
            
            col1, col2 = st.columns([1, 5])
            with col1:
                submitted = st.form_submit_button("Send", type="primary")
            with col2:
                new_chat = st.form_submit_button("New Chat")
        
        if submitted and user_input:
            # Prepare message content
            content = [{"type": "text", "text": user_input}]
            for file in uploaded_files or []:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": file_to_data_url(file)}
                })
            
            # Add user message
            user_msg = {"role": "user", "content": content if len(content) > 1 else user_input}
            st.session_state.messages.append(user_msg)
            
            # Display the new user message and assistant response in the chat container
            with chat_container:
                with st.chat_message("user"):
                    st.write(user_input)
                
                with st.chat_message("assistant"):
                    response_placeholder = st.empty()
                    response = ""
                    
                    for chunk in stream_chat_completion(
                        st.session_state.current_config["model"]["id"],
                        st.session_state.messages
                    ):
                        response += chunk
                        response_placeholder.markdown(response + "▌")
                    
                    response_placeholder.markdown(response)
                    
                    # Add assistant response to messages
                    st.session_state.messages.append({"role": "assistant", "content": response})
            
            # After streaming is complete, display the formatted version
            response_placeholder.write(format_response_with_tags(response))
            
            st.rerun()
        
        if new_chat:
            st.session_state.messages = []
            st.rerun()

elif st.session_state.chat_mode == "head2head":
    # Back button
    if st.button("← Back to Main Menu"):
        st.session_state.conversation_started = False
        st.session_state.chat_mode = None
        st.session_state.messages_left = []
        st.session_state.messages_right = []
        st.session_state.conversation_history = []
        st.session_state.voting_phase = False
        st.session_state.left_config = None
        st.session_state.right_config = None
        st.rerun()
    
    # Head-to-head interface (existing code)
    if not st.session_state.voting_phase:
        # Chat interface
        left_col, right_col = st.columns(2)
        
        # Create containers for the chat histories
        with left_col:
            st.subheader("nisa A")
            left_chat_container = st.container()
            with left_chat_container:
                for msg in st.session_state.conversation_history:
                    with st.chat_message("user"):
                        st.write(msg["user"])
                    with st.chat_message("assistant"):
                        st.write(format_response_with_tags(msg["left"]))
        
        with right_col:
            st.subheader("nisa B")
            right_chat_container = st.container()
            with right_chat_container:
                for msg in st.session_state.conversation_history:
                    with st.chat_message("user"):
                        st.write(msg["user"])
                    with st.chat_message("assistant"):
                        st.write(format_response_with_tags(msg["right"]))
        
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
            
            # Display in the existing chat containers
            with left_chat_container:
                with st.chat_message("user"):
                    st.write(user_input)
                with st.chat_message("assistant"):
                    left_placeholder = st.empty()
            
            with right_chat_container:
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
            
            # After streaming is complete, display formatted versions
            left_placeholder.write(format_response_with_tags(left_response))
            right_placeholder.write(format_response_with_tags(right_response))
            
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
        # Voting phase (existing code)
        st.markdown("""
        <div style="text-align: center; margin: 40px 0;">
            <h1 style="font-size: 64px;">time to vote!</h1>
            <p style="font-size: 24px; color: #666;">Which assistant provided better responses overall?</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Show the conversation
        left_col, right_col = st.columns(2)
        
        with left_col:
            st.markdown("""
            <div style="border: 4px solid currentColor; padding: 20px; margin-bottom: 20px;">
                <h2 style="text-align: center; margin-bottom: 20px;">nisa A</h2>
            </div>
            """, unsafe_allow_html=True)
            for msg in st.session_state.conversation_history:
                with st.chat_message("user"):
                    st.write(msg["user"])
                with st.chat_message("assistant"):
                    st.write(format_response_with_tags(msg["left"]))
        
        with right_col:
            st.markdown("""
            <div style="border: 4px solid currentColor; padding: 20px; margin-bottom: 20px;">
                <h2 style="text-align: center; margin-bottom: 20px;">nisa B</h2>
            </div>
            """, unsafe_allow_html=True)
            for msg in st.session_state.conversation_history:
                with st.chat_message("user"):
                    st.write(msg["user"])
                with st.chat_message("assistant"):
                    st.write(format_response_with_tags(msg["right"]))
        
        # Voting buttons
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; margin: 40px 0;">
            <h3 style="font-size: 36px; margin-bottom: 30px;">cast your vote</h3>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div style="text-align: center; padding: 20px;">
                <div style="font-size: 48px; margin-bottom: 10px;">🏆</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("NISA A WINS", type="primary", use_container_width=True):
                save_vote(
                    st.session_state.conversation_history,
                    st.session_state.left_config,
                    st.session_state.right_config,
                    "left"
                )
                st.balloons()
                st.success("Vote recorded! Thank you!")
                st.info(f"nisa A was: {st.session_state.left_config['model']['name']} with {st.session_state.left_config['prompt']['name']}")
                st.info(f"nisa B was: {st.session_state.right_config['model']['name']} with {st.session_state.right_config['prompt']['name']}")
        
        with col2:
            st.markdown("""
            <div style="text-align: center; padding: 20px;">
                <div style="font-size: 48px; margin-bottom: 10px;">🏆</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("NISA B WINS", type="primary", use_container_width=True):
                save_vote(
                    st.session_state.conversation_history,
                    st.session_state.left_config,
                    st.session_state.right_config,
                    "right"
                )
                st.balloons()
                st.success("Vote recorded! Thank you!")
                st.info(f"nisa A was: {st.session_state.left_config['model']['name']} with {st.session_state.left_config['prompt']['name']}")
                st.info(f"nisa B was: {st.session_state.right_config['model']['name']} with {st.session_state.right_config['prompt']['name']}")
        
        with col3:
            st.markdown("""
            <div style="text-align: center; padding: 20px;">
                <div style="font-size: 48px; margin-bottom: 10px;">🤝</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("IT'S A TIE", use_container_width=True):
                save_vote(
                    st.session_state.conversation_history,
                    st.session_state.left_config,
                    st.session_state.right_config,
                    "tie"
                )
                st.success("Vote recorded! Thank you!")
                st.info(f"nisa A was: {st.session_state.left_config['model']['name']} with {st.session_state.left_config['prompt']['name']}")
                st.info(f"nisa B was: {st.session_state.right_config['model']['name']} with {st.session_state.right_config['prompt']['name']}")
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("NEW PAIRING", use_container_width=True):
            # Reset conversation state but stay in head-to-head mode
            st.session_state.voting_phase = False
            st.session_state.messages_left = []
            st.session_state.messages_right = []
            st.session_state.conversation_history = []
            
            # Initialize new head-to-head configurations
            prompts = load_active_prompts()
            
            # Randomly select models and prompts
            left_model = random.choice(MODELS)
            right_model = random.choice(MODELS)
            left_prompt = random.choice(prompts)
            right_prompt = random.choice(prompts)
            
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
            
            st.rerun() 