"""
OrbitChat — Cosmic-themed AI Chatbot powered by Google Gemini (free tier)
Standalone Streamlit app. Part of the App Universe.

Setup:
1. Get a free Gemini API key: https://aistudio.google.com/apikey
2. pip install google-genai streamlit
3. Set it as an environment variable GEMINI_API_KEY (or add it to
   .streamlit/secrets.toml as GEMINI_API_KEY) before launching the app.

Multiple chat sessions persist locally to JSON, so you can start new chats
and revisit previous ones from the sidebar. No live web search — the bot
will say so if asked about current events instead of guessing.

v2 additions:
- Streaming replies
- Regenerate last reply / edit last user message
- Copy button on each message
- Per-session personality + model (falls back to global default)
- Pin/star chats, sidebar chat search
- Code blocks render with syntax highlighting (native via st.markdown)
- File/image upload (Gemini reads it, no generation)
- Export chat as Markdown
- Rough token/usage counter
- Retry with backoff + automatic model fallback on rate limits
"""

import streamlit as st
import json
import os
import time
import uuid
from datetime import datetime

# ----------------------------- CONFIG ---------------------------------

st.set_page_config(
    page_title="OrbitChat",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

SESSIONS_FILE = "orbit_chat_sessions.json"
UPLOADS_DIR = "orbit_chat_uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)

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
MODEL_ORDER = list(GEMINI_MODELS.values())  # fallback order

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

NO_CURRENT_EVENTS_NOTE = (
    " You do not have access to live web search or real-time data. "
    "If asked about current events, today's news, live prices, sports scores, "
    "or anything requiring up-to-date information beyond your training, "
    "politely explain that you can't look up current information and offer "
    "to help in another way instead of guessing."
)

# ----------------------------- PERSISTENCE -------------------------------------

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
        "pinned": False,
        "personality": st.session_state.get("system_prompt_choice", "Helpful Assistant"),
        "model": st.session_state.get("model_choice", list(GEMINI_MODELS.keys())[0]),
    }
    st.session_state.sessions_data["active"] = sid
    save_sessions(st.session_state.sessions_data)
    st.session_state.messages = []
    st.session_state.active_session_id = sid

def switch_session(sid):
    st.session_state.active_session_id = sid
    st.session_state.sessions_data["active"] = sid
    sess = st.session_state.sessions_data["sessions"][sid]
    st.session_state.messages = sess["messages"]
    st.session_state.system_prompt_choice = sess.get("personality", "Helpful Assistant")
    st.session_state.model_choice = sess.get("model", list(GEMINI_MODELS.keys())[0])
    save_sessions(st.session_state.sessions_data)

def persist_active_session():
    sd = st.session_state.sessions_data
    sid = st.session_state.active_session_id
    sd["sessions"][sid]["messages"] = st.session_state.messages
    sd["sessions"][sid]["title"] = make_session_title(st.session_state.messages)
    sd["sessions"][sid]["personality"] = st.session_state.system_prompt_choice
    sd["sessions"][sid]["model"] = st.session_state.model_choice
    save_sessions(sd)

def toggle_pin(sid):
    sd = st.session_state.sessions_data
    sd["sessions"][sid]["pinned"] = not sd["sessions"][sid].get("pinned", False)
    save_sessions(sd)

# ----------------------------- STATE INIT -------------------------------------

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

_active_sess = st.session_state.sessions_data["sessions"].get(st.session_state.active_session_id, {})

if "messages" not in st.session_state:
    st.session_state.messages = []
if "theme" not in st.session_state or st.session_state.theme not in THEMES:
    st.session_state.theme = "Nebula Purple"
if "system_prompt_choice" not in st.session_state or st.session_state.system_prompt_choice not in PERSONALITIES:
    st.session_state.system_prompt_choice = _active_sess.get("personality", "Helpful Assistant")
if "model_choice" not in st.session_state or st.session_state.model_choice not in GEMINI_MODELS:
    st.session_state.model_choice = _active_sess.get("model", list(GEMINI_MODELS.keys())[0])
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "editing_last" not in st.session_state:
    st.session_state.editing_last = False
if "chat_search" not in st.session_state:
    st.session_state.chat_search = ""
if "pending_attachment" not in st.session_state:
    st.session_state.pending_attachment = None
if "last_fallback_note" not in st.session_state:
    st.session_state.last_fallback_note = None

# ----------------------------- STYLES -------------------------------------

t = THEMES[st.session_state.theme]

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {{ font-family: 'Outfit', sans-serif; }}

.stApp {{
    background: radial-gradient(ellipse at top, #1a1333 0%, #0a0715 50%, #050308 100%);
    background-attachment: fixed;
}}
.stApp::before {{
    content: "";
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
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

.main .block-container {{ max-width: 820px; padding-top: 1rem; padding-bottom: 6rem; }}

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
.status-dot {{ width: 7px; height: 7px; border-radius: 50%; background: {t['accent']}; box-shadow: 0 0 8px {t['accent']}; }}

.empty-state {{ text-align: center; padding: 2rem 1rem 1rem; color: rgba(255,255,255,0.4); }}
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
.stTextInput input:focus {{ border-color: {t['primary']} !important; box-shadow: 0 0 0 1px {t['primary']}55 !important; }}

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

.stChatInput textarea {{ background: rgba(255,255,255,0.07) !important; color: white !important; border-radius: 14px !important; }}
[data-testid="stChatInput"] {{ border-color: {t['primary']}44 !important; }}
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

.timestamp {{ font-size: 0.68rem; color: rgba(255,255,255,0.3); margin-top: 0.15rem; }}

.pin-tag {{
    display: inline-flex; align-items: center; gap: 4px;
    background: {t['accent']}22; border: 1px solid {t['accent']}55; color: {t['accent']};
    border-radius: 999px; padding: 1px 8px; font-size: 0.65rem; margin-left: 6px;
}}

.attach-tag {{
    display: inline-flex; align-items: center; gap: 4px;
    background: {t['secondary']}22; border: 1px solid {t['secondary']}55; color: {t['secondary']};
    border-radius: 999px; padding: 2px 9px; font-size: 0.68rem; margin-top: 0.35rem;
}}

div[data-testid="column"] .stButton button {{
    font-size: 0.8rem !important;
    padding: 0.5rem 0.7rem !important;
    white-space: normal !important;
    height: auto !important;
}}

.msg-toolbar button {{
    font-size: 0.68rem !important;
    padding: 0.15rem 0.5rem !important;
}}

.fallback-note {{
    font-size: 0.7rem; color: {t['secondary']};
    background: {t['secondary']}18; border: 1px solid {t['secondary']}44;
    border-radius: 8px; padding: 3px 9px; margin-bottom: 0.4rem; display: inline-block;
}}

hr {{ border-color: rgba(255,255,255,0.08) !important; }}
</style>

<script>
function copyOrbitText(id) {{
    const el = document.getElementById(id);
    if (el) {{
        navigator.clipboard.writeText(el.innerText || el.textContent);
    }}
}}
</script>
""", unsafe_allow_html=True)

# ----------------------------- TOKEN ESTIMATE -------------------------------------

def estimate_tokens(text):
    # rough heuristic: ~4 chars per token
    return max(1, len(text) // 4)

def session_token_estimate(messages):
    return sum(estimate_tokens(m.get("content", "")) for m in messages)

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
    st.markdown("### 🤖 Model (this chat)")
    st.session_state.model_choice = st.selectbox("Gemini model", list(GEMINI_MODELS.keys()),
                                                  index=list(GEMINI_MODELS.keys()).index(st.session_state.model_choice),
                                                  label_visibility="collapsed")

    st.markdown("---")
    st.markdown("### 🎭 Personality (this chat)")
    personality_labels = [f"{v['icon']}  {k}" for k, v in PERSONALITIES.items()]
    current_label = f"{PERSONALITIES[st.session_state.system_prompt_choice]['icon']}  {st.session_state.system_prompt_choice}"
    chosen_label = st.selectbox("Assistant style", personality_labels,
                                 index=personality_labels.index(current_label),
                                 label_visibility="collapsed")
    st.session_state.system_prompt_choice = chosen_label.split("  ", 1)[1]
    persist_active_session()

    st.markdown("---")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.metric("Messages", len(st.session_state.messages))
    with col_b:
        st.metric("~Tokens", session_token_estimate(st.session_state.messages))

    if st.button("🗑️ Clear this chat", use_container_width=True):
        st.session_state.messages = []
        persist_active_session()
        st.rerun()

    st.markdown("---")
    st.markdown("### 💬 Chats")
    if st.button("➕ New chat", use_container_width=True):
        new_session()
        st.rerun()

    st.session_state.chat_search = st.text_input(
        "Search chats", value=st.session_state.chat_search,
        placeholder="🔎 Search chats...", label_visibility="collapsed",
    )

    sd = st.session_state.sessions_data
    all_ids = list(sd["sessions"].keys())
    query = st.session_state.chat_search.strip().lower()
    if query:
        all_ids = [sid for sid in all_ids if query in (sd["sessions"][sid].get("title") or "").lower()]

    pinned_ids = sorted(
        [sid for sid in all_ids if sd["sessions"][sid].get("pinned")],
        key=lambda k: sd["sessions"][k].get("created", ""), reverse=True,
    )
    other_ids = sorted(
        [sid for sid in all_ids if not sd["sessions"][sid].get("pinned")],
        key=lambda k: sd["sessions"][k].get("created", ""), reverse=True,
    )

    def render_chat_row(sid):
        sess = sd["sessions"][sid]
        title = sess.get("title") or "New chat"
        is_active = sid == st.session_state.active_session_id
        is_pinned = sess.get("pinned", False)
        c1, c2 = st.columns([5, 1])
        with c1:
            label = f"{'💠 ' if is_active else ''}{title}"
            if st.button(label, key=f"chat_{sid}", use_container_width=True, disabled=is_active):
                switch_session(sid)
                st.rerun()
        with c2:
            if st.button("📌" if not is_pinned else "★", key=f"pin_{sid}", use_container_width=True):
                toggle_pin(sid)
                st.rerun()

    if pinned_ids:
        st.caption("Pinned")
        for sid in pinned_ids:
            render_chat_row(sid)
    if other_ids:
        if pinned_ids:
            st.caption("All chats")
        for sid in other_ids:
            render_chat_row(sid)
    if not pinned_ids and not other_ids:
        st.caption("No chats match your search." if query else "No chats yet.")

    st.markdown("---")
    st.markdown("### 📤 Export")
    if st.session_state.messages:
        export_lines = [f"# {sd['sessions'][st.session_state.active_session_id].get('title','Chat')}\n"]
        for m in st.session_state.messages:
            who = "You" if m["role"] == "user" else "OrbitChat"
            export_lines.append(f"**{who}:**\n\n{m['content']}\n")
        export_md = "\n---\n".join(export_lines)
        st.download_button("⬇️ Download as Markdown", data=export_md,
                            file_name="orbitchat_export.md", mime="text/markdown",
                            use_container_width=True)
    else:
        st.caption("Nothing to export yet.")

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

# ----------------------------- GEMINI CALL -------------------------------------

def build_contents(history, types, attachment=None):
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    if attachment and contents:
        # attach file bytes to the last (most recent user) content
        last = contents[-1]
        try:
            with open(attachment["path"], "rb") as f:
                data = f.read()
            last.parts.append(types.Part.from_bytes(data=data, mime_type=attachment["mime"]))
        except Exception:
            pass
    return contents

def stream_gemini_response(history, system_prompt, model_name, key, attachment=None):
    """Yields text chunks. Tries model_name first, falls back through MODEL_ORDER
    on rate-limit errors, with exponential backoff retries."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        st.error("Missing package. Run: `pip install google-genai`")
        st.stop()

    client = genai.Client(api_key=key)
    contents = build_contents(history, types, attachment)
    config = types.GenerateContentConfig(
        system_instruction=system_prompt + NO_CURRENT_EVENTS_NOTE,
        temperature=0.8,
    )

    models_to_try = [model_name] + [m for m in MODEL_ORDER if m != model_name]
    last_error = None

    for candidate_model in models_to_try:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if candidate_model != model_name:
                    st.session_state.last_fallback_note = (
                        f"'{model_name}' was rate-limited — used '{candidate_model}' instead."
                    )
                else:
                    st.session_state.last_fallback_note = None

                stream = client.models.generate_content_stream(
                    model=candidate_model, contents=contents, config=config,
                )
                for chunk in stream:
                    if getattr(chunk, "text", None):
                        yield chunk.text
                return
            except Exception as e:
                last_error = e
                err_str = str(e)
                is_rate_limit = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
                if is_rate_limit:
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    else:
                        break  # move to next model in fallback list
                else:
                    yield f"⚠️ Something went wrong calling Gemini: {e}"
                    return

    yield f"⚠️ All models are currently rate-limited. Last error: {last_error}"

def handle_send(text, attachment=None):
    st.session_state.messages.append({"role": "user", "content": text, "ts": datetime.now().isoformat()})
    model_name = GEMINI_MODELS[st.session_state.model_choice]
    system_prompt = PERSONALITIES[st.session_state.system_prompt_choice]["prompt"]

    full_reply = ""
    placeholder = st.empty()
    for chunk in stream_gemini_response(st.session_state.messages, system_prompt, model_name, api_key, attachment):
        full_reply += chunk
        placeholder.markdown(full_reply + "▌")
    placeholder.markdown(full_reply)

    st.session_state.messages.append({
        "role": "assistant",
        "content": full_reply,
        "ts": datetime.now().isoformat(),
    })
    persist_active_session()

def regenerate_last():
    if len(st.session_state.messages) >= 1 and st.session_state.messages[-1]["role"] == "assistant":
        st.session_state.messages.pop()
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        last_user_text = st.session_state.messages.pop()["content"]
        st.session_state.pending_prompt = last_user_text

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
    n_msgs = len(st.session_state.messages)
    # Index of the most recent user message (the only one eligible for editing)
    last_user_idx = None
    for j in range(n_msgs - 1, -1, -1):
        if st.session_state.messages[j]["role"] == "user":
            last_user_idx = j
            break

    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"], avatar=AVATARS.get(msg["role"], "💬")):
            dom_id = f"orbit-msg-{i}"
            if msg["role"] == "user" and i == last_user_idx and st.session_state.editing_last:
                edited = st.text_area("Edit your message", value=msg["content"], key=f"edit_{i}", label_visibility="collapsed")
                ec1, ec2 = st.columns([1, 1])
                with ec1:
                    if st.button("✅ Send edit", key=f"save_edit_{i}"):
                        # trim everything from this message onward, resend edited text
                        st.session_state.messages = st.session_state.messages[:i]
                        st.session_state.editing_last = False
                        st.session_state.pending_prompt = edited
                        st.rerun()
                with ec2:
                    if st.button("✖️ Cancel", key=f"cancel_edit_{i}"):
                        st.session_state.editing_last = False
                        st.rerun()
            else:
                st.markdown(f'<div id="{dom_id}">{msg["content"]}</div>', unsafe_allow_html=True)
                if msg.get("attachment_name"):
                    st.markdown(f'<div class="attach-tag">📎 {msg["attachment_name"]}</div>', unsafe_allow_html=True)

            ts = msg.get("ts")
            time_str = ""
            if ts:
                try:
                    time_str = datetime.fromisoformat(ts).strftime("%-I:%M %p")
                except Exception:
                    time_str = ""

            toolbar_cols = st.columns([1, 1, 1, 5])
            with toolbar_cols[0]:
                st.markdown(
                    f'<button onclick="copyOrbitText(\'{dom_id}\')" '
                    f'style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);'
                    f'color:white;border-radius:8px;padding:2px 10px;font-size:0.68rem;cursor:pointer;">📋 Copy</button>',
                    unsafe_allow_html=True,
                )
            if msg["role"] == "user" and i == last_user_idx and not st.session_state.editing_last:
                with toolbar_cols[1]:
                    if st.button("✏️ Edit", key=f"editbtn_{i}"):
                        st.session_state.editing_last = True
                        st.rerun()
            if msg["role"] == "assistant" and i == n_msgs - 1:
                with toolbar_cols[1]:
                    if st.button("🔁 Regenerate", key=f"regen_{i}"):
                        regenerate_last()
                        st.rerun()

            if time_str:
                st.markdown(f'<div class="timestamp">{time_str}</div>', unsafe_allow_html=True)

if st.session_state.last_fallback_note:
    st.markdown(f'<div class="fallback-note">⚡ {st.session_state.last_fallback_note}</div>', unsafe_allow_html=True)

# ----------------------------- ATTACHMENT + INPUT -------------------------------------

with st.expander("📎 Attach a file or image", expanded=False):
    uploaded = st.file_uploader("Attach", type=["png", "jpg", "jpeg", "webp", "pdf", "txt", "md", "csv"],
                                 label_visibility="collapsed")
    if uploaded is not None:
        save_path = os.path.join(UPLOADS_DIR, f"{uuid.uuid4().hex[:8]}_{uploaded.name}")
        with open(save_path, "wb") as f:
            f.write(uploaded.getbuffer())
        st.session_state.pending_attachment = {
            "path": save_path, "name": uploaded.name, "mime": uploaded.type or "application/octet-stream",
        }
        st.success(f"Attached: {uploaded.name} — it'll be sent with your next message.")

if st.session_state.pending_attachment:
    ac1, ac2 = st.columns([5, 1])
    with ac1:
        st.markdown(f'<div class="attach-tag">📎 Ready to send: {st.session_state.pending_attachment["name"]}</div>', unsafe_allow_html=True)
    with ac2:
        if st.button("✖️", key="clear_attach"):
            st.session_state.pending_attachment = None
            st.rerun()

user_input = st.chat_input("Ask me anything...")

prompt_to_send = None
if st.session_state.pending_prompt:
    prompt_to_send = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
elif user_input:
    prompt_to_send = user_input

if prompt_to_send:
    attachment = st.session_state.pending_attachment
    st.session_state.pending_attachment = None

    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt_to_send)
        if attachment:
            st.markdown(f'<div class="attach-tag">📎 {attachment["name"]}</div>', unsafe_allow_html=True)

    if attachment:
        # tag onto the message dict for display after rerun
        pass

    with st.chat_message("assistant", avatar=active_personality["icon"]):
        handle_send(prompt_to_send, attachment)
        if attachment:
            st.session_state.messages[-2]["attachment_name"] = attachment["name"]
            persist_active_session()

    st.rerun()

st.caption("OrbitChat · Part of the App Universe · Your API key is never written to disk — chats are saved locally so you can revisit past conversations anytime.")
