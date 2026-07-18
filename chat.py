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
    "Gemini 2.5 Flash-Lite (highest free limits)": "gemini-2.5-flash-lite",
    "Gemini 2.5 Flash (balanced, free tier)": "gemini-2.5-flash",
    "Gemini 2.5 Pro (strongest, free tier)": "gemini-2.5-pro",
}

SYSTEM_PROMPTS = {
    "Helpful Assistant": "You are a helpful, friendly, and concise assistant.",
    "Creative Writer": "You are an imaginative creative writing assistant. Favor vivid, original language.",
    "Code Helper": "You are a precise coding assistant. Give clear, correct code with brief explanations.",
    "Study Buddy": "You are a patient tutor. Explain concepts step by step with simple examples.",
}

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
if "theme" not in st.session_state:
    st.session_state.theme = "Nebula Purple"
if "system_prompt_choice" not in st.session_state:
    st.session_state.system_prompt_choice = "Helpful Assistant"
if "model_choice" not in st.session_state:
    st.session_state.model_choice = "Gemini 2.5 Flash-Lite (highest free limits)"

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

.hero {{ text-align: center; padding: 1rem 0 0.5rem 0; }}
.hero h1 {{
    font-size: 2.4rem;
    background: linear-gradient(135deg, {t['primary']}, {t['secondary']});
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin-bottom: 0.2rem;
}}
.hero p {{ color: rgba(255,255,255,0.6); font-size: 0.95rem; }}

section[data-testid="stSidebar"] {{
    background: rgba(10,7,21,0.9);
    backdrop-filter: blur(10px);
}}

div[data-testid="stMetricValue"] {{ color: {t['primary']} !important; }}

.stTextInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea {{
    background: rgba(255,255,255,0.06) !important;
    color: white !important;
    border-radius: 10px !important;
}}

[data-testid="stChatMessage"] {{
    background: rgba(255,255,255,0.05);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    margin-bottom: 0.6rem;
}}

.stChatInput textarea {{
    background: rgba(255,255,255,0.06) !important;
    color: white !important;
}}
</style>
""", unsafe_allow_html=True)

# ----------------------------- SIDEBAR -------------------------------------

with st.sidebar:
    st.markdown("### 🔑 Gemini API Key")
    env_key = os.environ.get("GEMINI_API_KEY", "")
    if not env_key:
        try:
            env_key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            env_key = ""
    api_key = st.text_input(
        "Paste your free API key",
        value=env_key,
        type="default",
        help="Get a free key at https://aistudio.google.com/apikey — kept in session only, never saved to disk.",
    )
    if not api_key:
        st.caption("👉 [Get a free Gemini API key](https://aistudio.google.com/apikey)")

    st.markdown("---")
    st.markdown("### 🎨 Theme")
    st.session_state.theme = st.selectbox("Color theme", list(THEMES.keys()),
                                           index=list(THEMES.keys()).index(st.session_state.theme))

    st.markdown("---")
    st.markdown("### 🤖 Model")
    st.session_state.model_choice = st.selectbox("Gemini model", list(GEMINI_MODELS.keys()),
                                                  index=list(GEMINI_MODELS.keys()).index(st.session_state.model_choice))

    st.markdown("### 🎭 Personality")
    st.session_state.system_prompt_choice = st.selectbox("Assistant style", list(SYSTEM_PROMPTS.keys()),
                                                          index=list(SYSTEM_PROMPTS.keys()).index(st.session_state.system_prompt_choice))

    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🗑️ Clear chat", use_container_width=True):
            st.session_state.messages = []
            save_history([])
            st.rerun()
    with col_b:
        st.metric("Messages", len(st.session_state.messages))

    st.markdown("---")
    st.caption("Powered by Google Gemini's free API tier. Rate limits apply (see [ai.google.dev/pricing](https://ai.google.dev/pricing)).")

# ----------------------------- HERO -------------------------------------

st.markdown("""
<div class="hero">
<h1>💬 OrbitChat</h1>
<p>Your AI companion, powered by Gemini — free, fast, and always in orbit.</p>
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

# ----------------------------- CHAT DISPLAY -------------------------------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ----------------------------- CHAT INPUT -------------------------------------

user_input = st.chat_input("Ask me anything...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input, "ts": datetime.now().isoformat()})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                model_name = GEMINI_MODELS[st.session_state.model_choice]
                system_prompt = SYSTEM_PROMPTS[st.session_state.system_prompt_choice]
                reply = get_gemini_response(st.session_state.messages, system_prompt, model_name, api_key)
            except Exception as e:
                reply = f"⚠️ Error calling Gemini API: {e}\n\nCheck that your API key is valid and you haven't hit the free tier rate limit."
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply, "ts": datetime.now().isoformat()})
    save_history(st.session_state.messages)

st.markdown("---")
st.caption("OrbitChat · Part of the App Universe · Your API key is never written to disk — only chat text is saved locally so history survives a refresh.")
