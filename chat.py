"""
OrbitChat — Cosmic-themed AI Chatbot powered by Google Gemini (free tier)
Standalone Streamlit app. Part of the App Universe.

Setup:
1. Get a free Gemini API key: https://aistudio.google.com/apikey
2. pip install google-genai streamlit
3. Paste your key in the sidebar (stored only in session, never saved to disk)
   — or set it as an environment variable GEMINI_API_KEY to skip the prompt.

Multiple chat sessions persist locally to JSON, so you can start new chats
and revisit previous ones from the sidebar. No live web search — the bot
will say so if asked about current events instead of guessing.
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

SESSIONS_FILE = "orbit_chat_sessions.json"
QUOTA_FILE = "orbit_chat_quota.json"

def _today_pacific_str():
    # Approximate Pacific time without extra deps: UTC-8 (close enough for a daily-reset marker)
    from datetime import timedelta
    return (datetime.utcnow() - timedelta(hours=8)).strftime("%Y-%m-%d")

def load_quota_state():
    default = {"date": _today_pacific_str(), "request_count": 0, "quota_hit": False, "quota_hit_ts": None}
    if os.path.exists(QUOTA_FILE):
        try:
            with open(QUOTA_FILE, "r") as f:
                data = json.load(f)
            if data.get("date") != _today_pacific_str():
                return default
            return {**default, **data}
        except Exception:
            return default
    return default

def save_quota_state(state):
    with open(QUOTA_FILE, "w") as f:
        json.dump(state, f)

def mark_request_sent():
    q = st.session_state.quota_state
    q["request_count"] += 1
    save_quota_state(q)

def mark_quota_hit():
    q = st.session_state.quota_state
    q["quota_hit"] = True
    q["quota_hit_ts"] = datetime.utcnow().isoformat()
    save_quota_state(q)

def is_quota_error(exc) -> bool:
    msg = str(exc)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()

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
        # fall back to most recently created session
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
if "quota_state" not in st.session_state:
    st.session_state.quota_state = load_quota_state()

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
    st.markdown("---")
    st.markdown("### 📊 Quota Status")
    q = st.session_state.quota_state
    if q.get("quota_hit"):
        st.error("🚫 Daily free-tier quota reached. Resets ~midnight Pacific, or enable billing to lift the cap.")
    else:
        st.caption(f"✅ {q.get('request_count', 0)} request(s) sent today · free tier")

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
    st.info("Add your free Gemini API key in the sidebar to start chatting. It only takes a minute — [get one here](https://aistudio.google.com/apikey).")
    st.stop()

# ----------------------------- GEMINI CALL -------------------------------------

NO_CURRENT_EVENTS_NOTE = (
    " You do not have access to live web search or real-time data. "
    "If asked about current events, today's news, live prices, sports scores, "
    "or anything requiring up-to-date information beyond your training, "
    "politely explain that you can't look up current information and offer "
    "to help in another way instead of guessing."
)

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
            system_instruction=system_prompt + NO_CURRENT_EVENTS_NOTE,
            temperature=0.8,
        ),
    )

    return response.text

def handle_send(text):
    st.session_state.messages.append({"role": "user", "content": text, "ts": datetime.now().isoformat()})
    is_quota_err = False
    try:
        model_name = GEMINI_MODELS[st.session_state.model_choice]
        system_prompt = PERSONALITIES[st.session_state.system_prompt_choice]["prompt"]
        mark_request_sent()
        reply = get_gemini_response(
            st.session_state.messages, system_prompt, model_name, api_key,
        )
    except Exception as e:
        if is_quota_error(e):
            is_quota_err = True
            mark_quota_hit()
            reply = (
                "🌌 **Daily quota reached.** OrbitChat's free Gemini tier resets once every 24 hours "
                "(around midnight Pacific). Your message wasn't lost — it's saved above and you can "
                "retry once the quota resets.\n\n"
                "Want it fixed for good? Enable billing on your Google AI Studio project "
                "([aistudio.google.com](https://aistudio.google.com)) to move off the free daily cap — "
                "Gemini Flash models cost a fraction of a cent per message at that point."
            )
        else:
            reply = f"⚠️ Something went wrong calling Gemini: {e}"
    st.session_state.messages.append({
        "role": "assistant",
        "content": reply,
        "ts": datetime.now().isoformat(),
        "is_quota_error": is_quota_err,
    })
    persist_active_session()

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

st.caption("OrbitChat · Part of the App Universe · Your API key is never written to disk — chats are saved locally so you can revisit past conversations anytime.")
