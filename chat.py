"""
OrbitChat — Cosmic-themed AI Chatbot powered by Google Gemini (free tier)
Standalone Streamlit app. Part of the App Universe.

Setup:
1. Get a free Gemini API key: https://aistudio.google.com/apikey
2. pip install google-genai streamlit pillow
3. Set it as an environment variable GEMINI_API_KEY (or add it to
   .streamlit/secrets.toml as GEMINI_API_KEY) before launching the app.

Multiple chat sessions persist locally to JSON, so you can start new chats
and revisit previous ones from the sidebar.

NEW: Web Search mode uses Gemini's built-in Google Search grounding tool —
when on, Gemini reads multiple live web sources and writes an AI-synthesized
summary citing them (shown as source links + badge under the reply).
NEW: Image generation — toggle "Generate Image" to have Gemini create an
image from your prompt, shown inline in the chat.
"""

import streamlit as st
import json
import os
import base64
from datetime import datetime

# ----------------------------- CONFIG ---------------------------------

st.set_page_config(
    page_title="OrbitChat",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

SESSIONS_FILE = "orbit_chat_sessions.json"
IMAGES_DIR = "orbit_chat_images"
os.makedirs(IMAGES_DIR, exist_ok=True)

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

IMAGE_MODEL = "gemini-2.5-flash-image"

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

import uuid

def load_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, dict) and "sessions" in data:
                return data
        except Exception:
            pass
    return {"sessions": {}, "active": None}

def save_sessions(data):
    with open(SESSIONS_FILE, "w") as f:
        json.dump(data, f)

def make_session_title(messages):
    for m in messages:
        if m["role"] == "user" and m["content"].strip():
            text = m["content"].strip().replace("\n", " ")
            return text[:40] + ("…" if len(text) > 40 else "")
    return "New chat"

def new_session():
    sid = str(uuid.uuid4())
    st.session_state.sessions_data["sessions"][sid] = {
        "title": "New chat",
        "created": datetime.now().isoformat(),
        "messages": [],
    }
    st.session_state.sessions_data["active"] = sid
    save_sessions(st.session_state.sessions_data)
    st.session_state.messages = []
    st.session_state.active_session_id = sid

def switch_session(sid):
    st.session_state.active_session_id = sid
    st.session_state.sessions_data["active"] = sid
    st.session_state.messages = st.session_state.sessions_data["sessions"][sid]["messages"]
    save_sessions(st.session_state.sessions_data)

def persist_active_session():
    sd = st.session_state.sessions_data
    sid = st.session_state.active_session_id
    sd["sessions"][sid]["messages"] = st.session_state.messages
    sd["sessions"][sid]["title"] = make_session_title(st.session_state.messages)
    save_sessions(sd)

if "sessions_data" not in st.session_state:
    st.session_state.sessions_data = load_sessions()

if "active_session_id" not in st.session_state:
    sd = st.session_state.sessions_data
    active = sd.get("active")
    if active and active in sd["sessions"]:
        st.session_state.active_session_id = active
        st.session_state.messages = sd["sessions"][active]["messages"]
    elif sd["sessions"]:
        latest_id = max(sd["sessions"], key=lambda k: sd["sessions"][k].get("created", ""))
        st.session_state.active_session_id = latest_id
        st.session_state.messages = sd["sessions"][latest_id]["messages"]
    else:
        new_session()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "theme" not in st.session_state or st.session_state.theme not in THEMES:
    st.session_state.theme = "Nebula Purple"
if "system_prompt_choice" not in st.session_state or st.session_state.system_prompt_choice not in PERSONALITIES:
    st.session_state.system_prompt_choice = "Helpful Assistant"
if "model_choice" not in st.session_state or st.session_state.model_choice not in GEMINI_MODELS:
    st.session_state.model_choice = "Gemini 3.1 Flash-Lite (free, lightest)"
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "web_search_on" not in st.session_state:
    st.session_state.web_search_on = False
if "image_gen_on" not in st.session_state:
    st.session_state.image_gen_on = False


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

.empty-state {{
    text-align: center;
    padding: 2rem 1rem 1rem;
    color: rgba(255,255,255,0.4);
}}
.empty-state-icon {{ font-size: 2.6rem; margin-bottom: 0.4rem; }}

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
[data-testid="stChatInput"] textarea,
[data-testid="stChatInputTextArea"],
[data-testid="stBottomBlockContainer"] textarea {{
    background-color: #14101f !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    caret-color: #ffffff !important;
}}
[data-testid="stChatInput"] textarea::placeholder {{
    color: rgba(255,255,255,0.4) !important;
    -webkit-text-fill-color: rgba(255,255,255,0.4) !important;
}}

.timestamp {{
    font-size: 0.68rem;
    color: rgba(255,255,255,0.3);
    margin-top: 0.15rem;
}}

.search-badge {{
    display: inline-flex; align-items: center; gap: 4px;
    background: {t['accent']}22;
    border: 1px solid {t['accent']}55;
    color: {t['accent']};
    border-radius: 999px;
    padding: 2px 9px;
    font-size: 0.68rem;
    font-weight: 500;
    margin-top: 0.35rem;
}}
.image-badge {{
    display: inline-flex; align-items: center; gap: 4px;
    background: {t['secondary']}22;
    border: 1px solid {t['secondary']}55;
    color: {t['secondary']};
    border-radius: 999px;
    padding: 2px 9px;
    font-size: 0.68rem;
    font-weight: 500;
    margin-top: 0.35rem;
}}
.sources-box {{
    margin-top: 0.4rem;
    padding-top: 0.4rem;
    border-top: 1px solid rgba(255,255,255,0.08);
}}
.sources-box a {{
    color: rgba(255,255,255,0.55);
    font-size: 0.72rem;
    text-decoration: none;
    display: block;
    margin-top: 0.2rem;
}}
.sources-box a:hover {{ color: {t['primary']}; text-decoration: underline; }}

div[data-testid="column"] .stButton button {{
    font-size: 0.8rem !important;
    padding: 0.5rem 0.7rem !important;
    white-space: normal !important;
    height: auto !important;
}}

/* Toggle pills row */
.toggle-row {{ display: flex; gap: 0.5rem; margin-bottom: 0.4rem; }}

hr {{ border-color: rgba(255,255,255,0.08) !important; }}
</style>
""", unsafe_allow_html=True)

# ----------------------------- SIDEBAR -------------------------------------

with st.sidebar:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        try:
            api_key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            api_key = ""

    st.markdown("### 🎨 Appearance")
    st.session_state.theme = st.selectbox("Color theme", list(THEMES.keys()),
                                           index=list(THEMES.keys()).index(st.session_state.theme),
                                           label_visibility="collapsed")

    st.markdown("---")
    st.markdown("### 🤖 Model")
    st.session_state.model_choice = st.selectbox("Gemini model", list(GEMINI_MODELS.keys()),
                                                  index=list(GEMINI_MODELS.keys()).index(st.session_state.model_choice),
                                                  label_visibility="collapsed")

    st.markdown("---")
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
            persist_active_session()
            st.rerun()

    st.markdown("---")
    st.markdown("### 💬 Chats")
    if st.button("➕ New chat", use_container_width=True):
        new_session()
        st.rerun()

    sd = st.session_state.sessions_data
    ordered_ids = sorted(
        sd["sessions"].keys(),
        key=lambda k: sd["sessions"][k].get("created", ""),
        reverse=True,
    )
    for sid in ordered_ids:
        sess = sd["sessions"][sid]
        title = sess.get("title") or "New chat"
        is_active = sid == st.session_state.active_session_id
        label = f"{'💠 ' if is_active else ''}{title}"
        if st.button(label, key=f"chat_{sid}", use_container_width=True, disabled=is_active):
            switch_session(sid)
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
    st.info("No Gemini API key found. Set the GEMINI_API_KEY environment variable (or add it to Streamlit secrets) to start chatting — [get a free key here](https://aistudio.google.com/apikey).")
    st.stop()

# ----------------------------- MODE TOGGLES -------------------------------------

tog1, tog2, tog3 = st.columns([1, 1, 2])
with tog1:
    st.session_state.web_search_on = st.toggle("🌐 Web Search", value=st.session_state.web_search_on,
                                                 help="Gemini searches the live web across multiple sources and writes an AI summary with citations.")
with tog2:
    st.session_state.image_gen_on = st.toggle("🎨 Generate Image", value=st.session_state.image_gen_on,
                                                help="Your next message becomes an image generation prompt.")

# ----------------------------- GEMINI CALL -------------------------------------

NO_CURRENT_EVENTS_NOTE = (
    " You do not have access to live web search or real-time data. "
    "If asked about current events, today's news, live prices, sports scores, "
    "or anything requiring up-to-date information beyond your training, "
    "politely explain that you can't look up current information and offer "
    "to help in another way instead of guessing."
)

WEB_SEARCH_NOTE = (
    " You have live Google Search access. When you use it, synthesize a clear, "
    "well-organized answer in your own words that draws on multiple sources — "
    "don't just quote one source. Mention where claims are coming from when relevant."
)

def get_gemini_client(key):
    from google import genai
    return genai.Client(api_key=key)

def get_gemini_response(history, system_prompt, model_name, key, use_search):
    try:
        from google.genai import types
    except ImportError:
        st.error("Missing package. Run: `pip install google-genai`")
        st.stop()

    client = get_gemini_client(key)

    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

    config_kwargs = dict(temperature=0.8)
    if use_search:
        config_kwargs["system_instruction"] = system_prompt + WEB_SEARCH_NOTE
        config_kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    else:
        config_kwargs["system_instruction"] = system_prompt + NO_CURRENT_EVENTS_NOTE

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(**config_kwargs),
    )

    text = response.text or ""
    sources = []
    try:
        candidate = response.candidates[0]
        gm = candidate.grounding_metadata
        if gm and gm.grounding_chunks:
            for chunk in gm.grounding_chunks:
                web = getattr(chunk, "web", None)
                if web and web.uri:
                    sources.append({"title": web.title or web.uri, "uri": web.uri})
    except Exception:
        pass

    return text, sources

def generate_gemini_image(prompt, key):
    """Returns (caption_text, list_of_base64_png_strings)."""
    from google.genai import types

    client = get_gemini_client(key)
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[prompt],
    )

    text_out = ""
    images_b64 = []
    for part in response.candidates[0].content.parts:
        if getattr(part, "text", None):
            text_out += part.text
        if getattr(part, "inline_data", None) and part.inline_data.data:
            images_b64.append(base64.b64encode(part.inline_data.data).decode("utf-8"))
    return text_out.strip(), images_b64

def save_image_files(images_b64, sid):
    """Save base64 images to disk, return list of relative file paths."""
    paths = []
    for i, b64 in enumerate(images_b64):
        fname = f"{sid}_{uuid.uuid4().hex[:8]}.png"
        fpath = os.path.join(IMAGES_DIR, fname)
        with open(fpath, "wb") as f:
            f.write(base64.b64decode(b64))
        paths.append(fpath)
    return paths

def handle_send(text):
    st.session_state.messages.append({"role": "user", "content": text, "ts": datetime.now().isoformat()})

    if st.session_state.image_gen_on:
        try:
            caption, images_b64 = generate_gemini_image(text, api_key)
            image_paths = save_image_files(images_b64, st.session_state.active_session_id)
            reply = caption if caption else "Here's what I created:"
            msg = {
                "role": "assistant",
                "content": reply,
                "ts": datetime.now().isoformat(),
                "images": image_paths,
                "generated": True,
            }
        except Exception as e:
            msg = {"role": "assistant", "content": f"⚠️ Image generation failed: {e}", "ts": datetime.now().isoformat()}
        st.session_state.messages.append(msg)
        persist_active_session()
        return

    try:
        model_name = GEMINI_MODELS[st.session_state.model_choice]
        system_prompt = PERSONALITIES[st.session_state.system_prompt_choice]["prompt"]
        reply, sources = get_gemini_response(
            st.session_state.messages, system_prompt, model_name, api_key,
            st.session_state.web_search_on,
        )
    except Exception as e:
        reply, sources = f"⚠️ Something went wrong calling Gemini: {e}", []

    msg = {
        "role": "assistant",
        "content": reply,
        "ts": datetime.now().isoformat(),
    }
    if sources:
        msg["sources"] = sources
        msg["searched"] = True
    st.session_state.messages.append(msg)
    persist_active_session()

# ----------------------------- CHAT DISPLAY -------------------------------------

AVATARS = {"user": "🧑", "assistant": active_personality["icon"]}

def render_assistant_extras(msg):
    if msg.get("searched") and msg.get("sources"):
        st.markdown('<div class="search-badge">🌐 AI summary from multiple web sources</div>', unsafe_allow_html=True)
        links_html = "".join(
            f'<a href="{s["uri"]}" target="_blank">🔗 {s["title"]}</a>' for s in msg["sources"][:6]
        )
        st.markdown(f'<div class="sources-box">{links_html}</div>', unsafe_allow_html=True)
    if msg.get("generated"):
        st.markdown('<div class="image-badge">🎨 AI-generated image</div>', unsafe_allow_html=True)
    for img_path in msg.get("images", []):
        if os.path.exists(img_path):
            st.image(img_path, use_container_width=True)

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
            if msg["role"] == "assistant":
                render_assistant_extras(msg)
            ts = msg.get("ts")
            if ts:
                try:
                    time_str = datetime.fromisoformat(ts).strftime("%-I:%M %p")
                except Exception:
                    time_str = ""
                if time_str:
                    st.markdown(f'<div class="timestamp">{time_str}</div>', unsafe_allow_html=True)

# ----------------------------- CHAT INPUT -------------------------------------

placeholder = "Describe the image you want..." if st.session_state.image_gen_on else "Ask me anything..."
user_input = st.chat_input(placeholder)

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
        spinner_text = "Painting..." if st.session_state.image_gen_on else (
            "Searching the web..." if st.session_state.web_search_on else "Thinking..."
        )
        with st.spinner(spinner_text):
            handle_send(prompt_to_send)
        last_msg = st.session_state.messages[-1]
        st.markdown(last_msg["content"])
        render_assistant_extras(last_msg)
    st.rerun()

st.caption("OrbitChat · Part of the App Universe · Web Search uses live Google grounding · Your API key is never written to disk — chats and generated images are saved locally.")
