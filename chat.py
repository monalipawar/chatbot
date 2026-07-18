"""
OrbitChat — Cosmic-themed AI Chatbot powered by Google Gemini (free tier)
Standalone Streamlit app. Part of the App Universe.

Setup:
1. Get a free Gemini API key: https://aistudio.google.com/apikey
2. pip install google-genai streamlit
3. Paste your key in the sidebar (stored only in session, never saved to disk)
   — or set it as an environment variable GEMINI_API_KEY to skip the prompt.

Chat history persists locally to JSON so conversations survive a page refresh.
"""

import streamlit as st
import json
import os
from datetime import datetime

# ----------------------------- CONFIG ---------------------------------

st.set_page_config(
    page_title="OrbitChat",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

HISTORY_FILE = "orbit_chat_history.json"

THEMES = {
    "Nebula Purple": {"primary": "#a78bfa", "secondary": "#f472b6", "accent": "#818cf8"},
    "Aurora Green":  {"primary": "#34d399", "secondary": "#a3e635", "accent": "#22d3ee"},
    "Solar Flare":   {"primary": "#fb923c", "secondary": "#f87171", "accent": "#fbbf24"},
    "Deep Space":    {"primary": "#60a5fa", "secondary": "#818cf8", "accent": "#38bdf8"},
    "Rose Comet":    {"primary": "#fb7185", "secondary": "#f472b6", "accent": "#e879f9"},
}

GEMINI_MODELS = {
    "Gemini 3.1 Flash-Lite (free, lightest)": "gemini-3.1-flash-lite",
    "Gemini 3.5 Flash (free, most capable)": "gemini-3.5-flash",
}

PERSONALITIES = {
    "Helpful Assistant": {"icon": "🤖", "prompt": "You are a helpful, friendly, and concise assistant."},
    "Creative Writer":   {"icon": "🖋️", "prompt": "You are an imaginative creative writing assistant. Favor vivid, original language."},
    "Code Helper":       {"icon": "👩‍💻", "prompt": "You are a precise coding assistant. Give clear, correct code with brief explanations."},
    "Study Buddy":       {"icon": "📖", "prompt": "You are a patient tutor. Explain concepts step by step with simple examples."},
}

SUGGESTED_PROMPTS = [
    "Explain black holes like I'm 10",
    "Give me 3 dinner ideas using chicken",
    "Help me write a polite follow-up email",
    "What's a fun fact about space?",
]

# ----------------------------- STATE -------------------------------------

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

if "messages" not in st.session_state:
    st.session_state.messages = load_history()
if "theme" not in st.session_state or st.session_state.theme not in THEMES:
    st.session_state.theme = "Nebula Purple"
if "system_prompt_choice" not in st.session_state or st.session_state.system_prompt_choice not in PERSONALITIES:
    st.session_state.system_prompt_choice = "Helpful Assistant"
if "model_choice" not in st.session_state or st.session_state.model_choice not in GEMINI_MODELS:
    st.session_state.model_choice = "Gemini 3.1 Flash-Lite (free, lightest)"
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

# ----------------------------- STYLES -------------------------------------

t = THEMES[st.session_state.theme]

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {{
    font-family: 'Outfit', sans-serif;
}}

.stApp {{
    background: radial-gradient(ellipse at top, #1a1333 0%, #0a0715 50%, #050308 100%);
    background-attachment: fixed;
}}

.stApp::before {{
    content: "";
    position: fixed;
    top: 0; left: 0; width: 100%; height: 100%;
    background-image:
        radial-gradient(2px 2px at 20% 30%, white, transparent),
        radial-gradient(2px 2px at 60% 70%, white, transparent),
        radial-gradient(1px 1px at 80% 10%, white, transparent),
        radial-gradient(1px 1px at 40% 90%, white, transparent),
        radial-gradient(1px 1px at 90% 50%, white, transparent);
    background-size: 300px 300px;
    opacity: 0.4;
    pointer-events: none;
    z-index: 0;
}}

h1, h2, h3 {{ color: white !important; font-weight: 700 !important; }}

.main .block-container {{
    max-width: 820px;
    padding-top: 1rem;
    padding-bottom: 6rem;
}}

/* Hero */
.hero {{ text-align: center; padding: 0.8rem 0 0.4rem 0; }}
.hero h1 {{
    font-size: 2.3rem;
    background: linear-gradient(135deg, {t['primary']}, {t['secondary']});
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin-bottom: 0.2rem;
}}
.hero p {{ color: rgba(255,255,255,0.55); font-size: 0.9rem; margin: 0; }}

.status-pill {{
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 999px; padding: 3px 12px;
    font-size: 0.72rem; color: rgba(255,255,255,0.7);
    margin-top: 0.5rem;
}}
.status-dot {{
    width: 7px; height: 7px; border-radius: 50%;
    background: {t['accent']};
    box-shadow: 0 0 8px {t['accent']};
}}

/* Empty state / suggestions */
.empty-state {{
    text-align: center;
    padding: 2rem 1rem 1rem;
    color: rgba(255,255,255,0.4);
}}
.empty-state-icon {{ font-size: 2.6rem; margin-bottom: 0.4rem; }}

/* Sidebar */
section[data-testid="stSidebar"] {{
    background: rgba(10,7,21,0.92);
    backdrop-filter: blur(10px);
    border-right: 1px solid rgba(255,255,255,0.06);
}}
section[data-testid="stSidebar"] h3 {{
    font-size: 0.85rem !important;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: rgba(255,255,255,0.5) !important;
    font-weight: 600 !important;
    margin-bottom: 0.4rem !important;
}}

div[data-testid="stMetricValue"] {{ color: {t['primary']} !important; }}
div[data-testid="stMetric"] {{
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 0.5rem 0.7rem;
}}
div[data-testid="stMetricLabel"] {{ color: rgba(255,255,255,0.45) !important; }}

.stTextInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea,
input[type="text"], input[type="password"], textarea {{
    background: rgba(255,255,255,0.08) !important;
    color: #ffffff !important;
    caret-color: #ffffff !important;
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    -webkit-text-fill-color: #ffffff !important;
}}
.stTextInput input::placeholder, textarea::placeholder {{
    color: rgba(255,255,255,0.4) !important;
    -webkit-text-fill-color: rgba(255,255,255,0.4) !important;
}}
.stTextInput input:focus {{
    border-color: {t['primary']} !important;
    box-shadow: 0 0 0 1px {t['primary']}55 !important;
}}

/* Buttons */
.stButton button {{
    background: linear-gradient(135deg, {t['primary']}22, {t['secondary']}22) !important;
    border: 1px solid {t['primary']}55 !important;
    color: white !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}}
.stButton button:hover {{
    border-color: {t['primary']} !important;
    background: linear-gradient(135deg, {t['primary']}44, {t['secondary']}44) !important;
    transform: translateY(-1px);
}}

/* Chat bubbles */
[data-testid="stChatMessage"] {{
    background: rgba(255,255,255,0.045);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    margin-bottom: 0.7rem;
    padding: 0.2rem 0.3rem;
}}

.stChatInput textarea {{
    background: rgba(255,255,255,0.07) !important;
    color: white !important;
    border-radius: 14px !important;
}}
[data-testid="stChatInput"] {{
    border-color: {t['primary']}44 !important;
}}

.timestamp {{
    font-size: 0.68rem;
    color: rgba(255,255,255,0.3);
    margin-top: 0.15rem;
}}

/* Suggestion chips rendered as buttons */
div[data-testid="column"] .stButton button {{
    font-size: 0.8rem !important;
    padding: 0.5rem 0.7rem !important;
    white-space: normal !important;
    height: auto !important;
}}

hr {{ border-color: rgba(255,255,255,0.08) !important; }}
</style>
""", unsafe_allow_html=True)

# ----------------------------- SIDEBAR -------------------------------------

with st.sidebar:
    st.markdown("### 🔑 API Key")
    env_key = os.environ.get("GEMINI_API_KEY", "")
    if not env_key:
        try:
            env_key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            env_key = ""
    api_key = st.text_input(
        "Gemini API key",
        value=env_key,
        type="default",
        label_visibility="collapsed",
        placeholder="Paste your free API key...",
        help="Get a free key at https://aistudio.google.com/apikey — kept in session only, never saved to disk.",
    )
    if not api_key:
        st.caption("👉 [Get a free Gemini API key](https://aistudio.google.com/apikey)")
    else:
        st.caption("✅ Key loaded for this session")

    st.markdown("---")
    st.markdown("### 🎨 Appearance")
    st.session_state.theme = st.selectbox("Color theme", list(THEMES.keys()),
                                           index=list(THEMES.keys()).index(st.session_state.theme),
                                           label_visibility="collapsed")

    st.markdown("---")
    st.markdown("### 🤖 Model")
    st.session_state.model_choice = st.selectbox("Gemini model", list(GEMINI_MODELS.keys()),
                                                  index=list(GEMINI_MODELS.keys()).index(st.session_state.model_choice),
                                                  label_visibility="collapsed")

    st.markdown("### 🎭 Personality")
    personality_labels = [f"{v['icon']}  {k}" for k, v in PERSONALITIES.items()]
    current_label = f"{PERSONALITIES[st.session_state.system_prompt_choice]['icon']}  {st.session_state.system_prompt_choice}"
    chosen_label = st.selectbox("Assistant style", personality_labels,
                                 index=personality_labels.index(current_label),
                                 label_visibility="collapsed")
    st.session_state.system_prompt_choice = chosen_label.split("  ", 1)[1]

    st.markdown("---")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.metric("Messages", len(st.session_state.messages))
    with col_b:
        if st.button("🗑️ Clear", use_container_width=True):
            st.session_state.messages = []
            save_history([])
            st.rerun()

    st.markdown("---")
    st.caption("Powered by Google Gemini's free API tier. Rate limits apply — see [ai.google.dev/pricing](https://ai.google.dev/gemini-api/docs/pricing).")

# ----------------------------- HERO -------------------------------------

active_personality = PERSONALITIES[st.session_state.system_prompt_choice]
active_model_label = st.session_state.model_choice.split(" (")[0]

st.markdown(f"""
<div class="hero">
<h1>💬 OrbitChat</h1>
<p>Your AI companion, powered by Gemini — free, fast, and always in orbit.</p>
<div class="status-pill"><span class="status-dot"></span>{active_personality['icon']} {st.session_state.system_prompt_choice} · {active_model_label}</div>
</div>
""", unsafe_allow_html=True)

if not api_key:
    st.info("Add your free Gemini API key in the sidebar to start chatting. It only takes a minute — [get one here](https://aistudio.google.com/apikey).")
    st.stop()

# ----------------------------- GEMINI CALL -------------------------------------

def get_gemini_response(history, system_prompt, model_name, key):
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        st.error("Missing package. Run: `pip install google-genai`")
        st.stop()

    client = genai.Client(api_key=key)

    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.8,
        ),
    )
    return response.text

def handle_send(text):
    st.session_state.messages.append({"role": "user", "content": text, "ts": datetime.now().isoformat()})
    try:
        model_name = GEMINI_MODELS[st.session_state.model_choice]
        system_prompt = PERSONALITIES[st.session_state.system_prompt_choice]["prompt"]
        reply = get_gemini_response(st.session_state.messages, system_prompt, model_name, api_key)
    except Exception as e:
        reply = f"⚠️ Error calling Gemini API: {e}\n\nCheck that your API key is valid and you haven't hit the free tier rate limit."
    st.session_state.messages.append({"role": "assistant", "content": reply, "ts": datetime.now().isoformat()})
    save_history(st.session_state.messages)

# ----------------------------- CHAT DISPLAY -------------------------------------

AVATARS = {"user": "🧑", "assistant": active_personality["icon"]}

if not st.session_state.messages:
    st.markdown(f"""
    <div class="empty-state">
        <div class="empty-state-icon">{active_personality['icon']}</div>
        <div>Say hello to start chatting as your <b style="color:white;">{st.session_state.system_prompt_choice}</b></div>
    </div>
    """, unsafe_allow_html=True)

    cols = st.columns(2)
    for i, sp in enumerate(SUGGESTED_PROMPTS):
        with cols[i % 2]:
            if st.button(sp, key=f"suggest_{i}", use_container_width=True):
                st.session_state.pending_prompt = sp
                st.rerun()
else:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar=AVATARS.get(msg["role"], "💬")):
            st.markdown(msg["content"])
            ts = msg.get("ts")
            if ts:
                try:
                    time_str = datetime.fromisoformat(ts).strftime("%-I:%M %p")
                except Exception:
                    time_str = ""
                if time_str:
                    st.markdown(f'<div class="timestamp">{time_str}</div>', unsafe_allow_html=True)

# ----------------------------- CHAT INPUT -------------------------------------

user_input = st.chat_input("Ask me anything...")

prompt_to_send = None
if st.session_state.pending_prompt:
    prompt_to_send = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
elif user_input:
    prompt_to_send = user_input

if prompt_to_send:
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt_to_send)
    with st.chat_message("assistant", avatar=active_personality["icon"]):
        with st.spinner("Thinking..."):
            handle_send(prompt_to_send)
        st.markdown(st.session_state.messages[-1]["content"])
    st.rerun()

st.caption("OrbitChat · Part of the App Universe · Your API key is never written to disk — only chat text is saved locally so history survives a refresh.")
