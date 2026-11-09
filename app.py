import json
import os
import io
import time
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pypdf import PdfReader
from gtts import gTTS

# 1. Page Configuration
st.set_page_config(
    page_title="Nexus AI Studio",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Local File Storage (Persistent Chats)
HISTORY_FILE = "chat_history.json"

def load_saved_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                chats = data.get("chats", {}) if isinstance(data, dict) and "chats" in data else data
                if isinstance(chats, dict) and chats:
                    return chats
        except Exception:
            pass
    return {
        "New Conversation": [
            {"role": "assistant", "content": "Welcome to Nexus AI Studio. What would you like to explore or discuss today?"}
        ]
    }

def save_current_history():
    try:
        payload = {"chats": st.session_state.sessions}
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving history: {e}")

# 3. Credentials & Gemini API
load_dotenv()

api_key = None
if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = os.getenv("GEMINI_API_KEY")

client = None
AVAILABLE_MODELS = []

if api_key:
    try:
        clean_key = str(api_key).strip().strip("'\"")
        client = genai.Client(api_key=clean_key)
        for m in client.models.list():
            m_name = m.name.replace("models/", "")
            if "flash" in m_name or "gemini" in m_name:
                AVAILABLE_MODELS.append(m_name)
    except Exception as e:
        st.error(f"Error connecting to Gemini: {e}")

if not AVAILABLE_MODELS:
    AVAILABLE_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

# 4. Session State Setup
if "sessions" not in st.session_state:
    st.session_state.sessions = load_saved_history()
    if "New Conversation" not in st.session_state.sessions:
        st.session_state.sessions["New Conversation"] = [
            {"role": "assistant", "content": "Welcome to Nexus AI Studio. What would you like to explore or discuss today?"}
        ]
    st.session_state.current_session = "New Conversation"

if "pinned_chats" not in st.session_state:
    st.session_state.pinned_chats = set()

if "current_session" not in st.session_state or st.session_state.current_session not in st.session_state.sessions:
    st.session_state.current_session = "New Conversation"

if "doc_context" not in st.session_state:
    st.session_state.doc_context = ""
if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = None
if "rename_target" not in st.session_state:
    st.session_state.rename_target = None
if "active_theme" not in st.session_state:
    st.session_state.active_theme = "Sunset Peach"

# 5. Personas & UI Styling
PERSONAS = {
    "General Assistant": "You are Nexus, a helpful, authentic, adaptive, and highly capable AI collaborator. Answer with clarity and depth.",
    "Senior Software Engineer": "You are a Principal Software Engineer. Provide robust, clean, modular code with concise technical explanations and zero fluff.",
    "Academic Tutor": "You are an expert university professor and tutor. Explain complex concepts intuitively using step-by-step breakdowns, structured notes, and clear examples.",
    "Executive Summarizer": "You are a concise executive advisor. Provide sharp, high-impact bullet points, actionable takeaways, and direct conclusions."
}

THEMES = {
    "Sunset Peach": {
        "bg": "radial-gradient(circle at 50% 0%, #221a1f 0%, #0d0b0e 100%)",
        "accent": "linear-gradient(135deg, #ffd3b6 0%, #ffaaa5 50%, #e88d9c 100%)",
        "border": "#3d2b33",
        "input_bg": "#1e161c"
    },
    "Lavender Glow": {
        "bg": "radial-gradient(circle at 50% 0%, #1a1728 0%, #0c0a14 100%)",
        "accent": "linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%)",
        "border": "#2d2645",
        "input_bg": "#19152b"
    },
    "Obsidian Dark": {
        "bg": "radial-gradient(circle at 50% 0%, #171b26 0%, #0b0d13 100%)",
        "accent": "linear-gradient(135deg, #cbd5e1 0%, #94a3b8 100%)",
        "border": "#283042",
        "input_bg": "#151922"
    }
}
theme_conf = THEMES[st.session_state.active_theme]

st.markdown(f"""
<style>
    .stApp {{
        background: {theme_conf["bg"]};
        color: #f1f5f9;
    }}
    header[data-testid="stHeader"] {{
        background: transparent !important;
        display: block !important;
    }}
    [data-testid="collapsedControl"],
    [data-testid="collapsedControl"] button,
    button[data-testid="baseButton-headerNoPadding"] {{
        display: inline-flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        z-index: 999999 !important;
    }}
    [data-testid="stToolbarActions"],
    header a[href*="github.com"],
    header .stDeployButton,
    header button[title="View source on GitHub"],
    #MainMenu,
    [data-testid="stMainMenu"] {{
        display: none !important;
        visibility: hidden !important;
    }}
    footer,
    div[class*="viewerBadge"],
    div[data-testid="stStatusWidget"],
    .viewerBadge_container__1QSob {{
        display: none !important;
        visibility: hidden !important;
    }}
    section[data-testid="stSidebar"] {{
        background-color: #0b0c10 !important;
        border-right: 1px solid {theme_conf["border"]} !important;
    }}
    section[data-testid="stSidebar"] button {{
        color: #f8fafc !important;
        background-color: #1a1e29 !important;
        border: 1px solid {theme_conf["border"]} !important;
        padding: 4px 6px !important;
        border-radius: 8px !important;
    }}
    section[data-testid="stSidebar"] button:hover {{
        background-color: #262c3d !important;
        border-color: #6366f1 !important;
        color: #ffffff !important;
    }}
    div[data-testid="stChatInput"] {{
        max-width: 820px !important;
        margin: 0 auto !important;
        padding-bottom: 20px;
    }}
    div[data-testid="stChatInput"] > div {{
        background-color: {theme_conf["input_bg"]} !important;
        border: 1px solid {theme_conf["border"]} !important;
        border-radius: 14px !important;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.45) !important;
    }}
    div[data-testid="stChatInput"] textarea {{
        color: #f8fafc !important;
    }}
    .hero-title {{
        font-size: 2.2rem;
        font-weight: 800;
        text-align: center;
        background: {theme_conf["accent"]};
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2px;
    }}
    .hero-subtitle {{
        text-align: center;
        color: #718096;
        font-size: 0.9rem;
        margin-bottom: 20px;
    }}
</style>
""", unsafe_allow_html=True)

# 6. Sidebar (Clean Navigation & Collapsed Settings)
with st.sidebar:
    st.markdown("### ✨ **Nexus AI**")

    if st.button("✏️ New chat", use_container_width=True):
        new_id = f"Chat {len(st.session_state.sessions) + 1}"
        st.session_state.sessions[new_id] = [
            {"role": "assistant", "content": "How can I assist you in this new session?"}
        ]
        st.session_state.current_session = new_id
        st.session_state.doc_context = ""
        st.session_state.uploaded_file_name = None
        save_current_history()
        st.rerun()

    st.markdown("---")
    
    app_mode = st.radio(
        "Mode:",
        ["💬 Chat Assistant", "📄 Document Q&A (RAG)"],
        index=0
    )

    if app_mode == "📄 Document Q&A (RAG)":
        st.markdown("#### 📂 Upload Document")
        uploaded_doc = st.file_uploader("Upload a PDF or TXT", type=["pdf", "txt"])
        if uploaded_doc is not None and st.session_state.uploaded_file_name != uploaded_doc.name:
            with st.spinner("Parsing document..."):
                extracted_text = ""
                if uploaded_doc.name.endswith(".pdf"):
                    reader = PdfReader(uploaded_doc)
                    for page in reader.pages:
                        t = page.extract_text()
                        if t:
                            extracted_text += t + "\n"
                else:
                    extracted_text = uploaded_doc.read().decode("utf-8", errors="ignore")
                
                st.session_state.doc_context = extracted_text[:40000]
                st.session_state.uploaded_file_name = uploaded_doc.name
                st.success(f"Loaded: {uploaded_doc.name}")

    st.markdown("---")

    # Search & Chat Sessions List
    search_query = st.text_input("🔍 Search chats...", placeholder="Type keywords...").lower()

    def render_chat_row(s_name, is_pinned=False):
        c1, c2, c3, c4 = st.columns([0.55, 0.15, 0.15, 0.15])
        label = s_name if len(s_name) <= 15 else s_name[:12] + "..."
        if c1.button(label, key=f"btn_{s_name}", use_container_width=True, help=s_name):
            st.session_state.current_session = s_name
            st.rerun()
        
        pin_icon = "⭐" if is_pinned else "☆"
        if c2.button(pin_icon, key=f"pin_{s_name}", help="Pin / Unpin chat"):
            if is_pinned:
                st.session_state.pinned_chats.discard(s_name)
            else:
                st.session_state.pinned_chats.add(s_name)
            st.rerun()

        if c3.button("✏️", key=f"ren_{s_name}", help="Rename chat"):
            st.session_state.rename_target = s_name

        if len(st.session_state.sessions) > 1 and c4.button("🗑️", key=f"del_{s_name}", help="Delete chat"):
            st.session_state.pinned_chats.discard(s_name)
            del st.session_state.sessions[s_name]
            st.session_state.current_session = "New Conversation" if "New Conversation" in st.session_state.sessions else list(st.session_state.sessions.keys())[0]
            save_current_history()
            st.rerun()

    if st.session_state.rename_target:
        st.markdown(f"**Rename: `{st.session_state.rename_target}`**")
        new_name = st.text_input("New Title", value=st.session_state.rename_target, key="rename_input")
        col_r1, col_r2 = st.columns(2)
        if col_r1.button("Save", use_container_width=True) and new_name.strip():
            target = st.session_state.rename_target
            clean_name = new_name.strip()
            if clean_name != target:
                st.session_state.sessions[clean_name] = st.session_state.sessions.pop(target)
                if target in st.session_state.pinned_chats:
                    st.session_state.pinned_chats.remove(target)
                    st.session_state.pinned_chats.add(clean_name)
                if st.session_state.current_session == target:
                    st.session_state.current_session = clean_name
            st.session_state.rename_target = None
            save_current_history()
            st.rerun()
        if col_r2.button("Cancel", use_container_width=True):
            st.session_state.rename_target = None
            st.rerun()

    all_chat_names = [s for s in st.session_state.sessions.keys() if search_query in s.lower() and s != "New Conversation"]

    pinned_visible = [s for s in all_chat_names if s in st.session_state.pinned_chats]
    if pinned_visible:
        st.markdown("#### 📌 **Pinned**")
        for s_name in pinned_visible:
            render_chat_row(s_name, is_pinned=True)

    recents_visible = [s for s in all_chat_names if s not in st.session_state.pinned_chats]
    if recents_visible:
        st.markdown("#### 🕒 **Recents**")
        for s_name in recents_visible:
            render_chat_row(s_name, is_pinned=False)

    st.markdown("---")

    # Bottom Collapsed Settings & Export
    with st.expander("⚙️ Settings & Tools", expanded=False):
        selected_persona = st.selectbox("AI Role / Persona:", list(PERSONAS.keys()), index=0)
        enable_search = st.checkbox("🌐 Live Google Search Grounding", value=False)
        enable_tts = st.checkbox("Enable Voice Audio (TTS)", value=False)
        selected_theme = st.selectbox(
            "UI Accent Palette:",
            list(THEMES.keys()),
            index=list(THEMES.keys()).index(st.session_state.active_theme)
        )
        if selected_theme != st.session_state.active_theme:
            st.session_state.active_theme = selected_theme
            st.rerun()

    active_msgs = st.session_state.sessions.get(st.session_state.current_session, [])
    if len(active_msgs) > 1:
        md_export = f"# Nexus AI Studio - Conversation Export\n**Session:** {st.session_state.current_session}\n\n---\n"
        for m in active_msgs:
            md_export += f"### {m['role'].capitalize()}\n{m['content']}\n\n"
        st.download_button(
            label="📥 Export Chat (.md)",
            data=md_export,
            file_name=f"{st.session_state.current_session.replace(' ', '_')}.md",
            mime="text/markdown",
            use_container_width=True
        )

# Header
st.markdown("<div class='hero-title'>Nexus AI Studio ✨</div>", unsafe_allow_html=True)
st.markdown(f"<div class='hero-subtitle'>Conversation: <b>{st.session_state.current_session}</b> | Mode: <b>{app_mode}</b></div>", unsafe_allow_html=True)

# 7. Page Views
if app_mode == "📄 Document Q&A (RAG)":
    st.markdown("### 📄 **Document Intelligence (RAG)**")
    if not st.session_state.doc_context:
        st.info("Please upload a PDF or TXT file using the sidebar first.")
    else:
        st.success(f"Active Document: **{st.session_state.uploaded_file_name}**")

    if prompt := st.chat_input("Ask questions about your uploaded document..."):
        if not st.session_state.doc_context:
            st.warning("Please upload a document first!")
        elif not client:
            st.error("Gemini API key is not ready.")
        else:
            rag_prompt = (
                f"Answer the user's question accurately using only the following document content.\n\n"
                f"--- DOCUMENT CONTENT ---\n{st.session_state.doc_context}\n--- END DOCUMENT ---\n\n"
                f"Question: {prompt}"
            )
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                placeholder_box = st.empty()
                full_res = ""
                with st.spinner("Analyzing document..."):
                    for m in AVAILABLE_MODELS:
                        try:
                            stream = client.models.generate_content_stream(model=m, contents=rag_prompt)
                            for chunk in stream:
                                if chunk.text:
                                    full_res += chunk.text
                                    placeholder_box.markdown(full_res + "▌")
                            placeholder_box.markdown(full_res)
                            break
                        except Exception:
                            continue

else:
    # Chat Assistant (Multi-Turn Context, Persona Support, & Search Grounding)
    active_msgs = st.session_state.sessions.get(st.session_state.current_session, [])
    
    for idx, msg in enumerate(active_msgs):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if enable_tts and msg["role"] == "assistant" and len(msg.get("content", "")) > 5:
                if st.button("🔊 Play Voice", key=f"tts_{idx}"):
                    try:
                        tts = gTTS(text=msg["content"][:400], lang="en")
                        audio_buffer = io.BytesIO()
                        tts.write_to_fp(audio_buffer)
                        st.audio(audio_buffer.getvalue(), format="audio/mp3", autoplay=True)
                    except Exception:
                        pass

    if prompt := st.chat_input("Ask anything..."):
        current_key = st.session_state.current_session
        if current_key.startswith("Chat ") or current_key == "New Conversation":
            new_title = prompt[:24] + ("..." if len(prompt) > 24 else "")
            st.session_state.sessions[new_title] = st.session_state.sessions.pop(current_key)
            if current_key in st.session_state.pinned_chats:
                st.session_state.pinned_chats.remove(current_key)
                st.session_state.pinned_chats.add(new_title)
            st.session_state.current_session = new_title
            active_msgs = st.session_state.sessions[new_title]
            save_current_history()

        active_msgs.append({"role": "user", "content": prompt})
        save_current_history()

        with st.chat_message("user"):
            st.markdown(prompt)

        if not client:
            st.error("Gemini API key is not ready. Please verify GEMINI_API_KEY in Secrets.")
        else:
            with st.chat_message("assistant"):
                placeholder_box = st.empty()
                full_res = ""
                success = False

                # Format conversation history for full multi-turn context
                formatted_contents = []
                for m in active_msgs:
                    role_tag = "user" if m["role"] == "user" else "model"
                    formatted_contents.append(
                        types.Content(
                            role=role_tag,
                            parts=[types.Part.from_text(text=m["content"])]
                        )
                    )

                config_params = {
                    "system_instruction": PERSONAS.get(selected_persona, PERSONAS["General Assistant"])
                }
                if enable_search:
                    config_params["tools"] = [{"google_search": {}}]

                gen_config = types.GenerateContentConfig(**config_params)

                for m in AVAILABLE_MODELS:
                    try:
                        response_stream = client.models.generate_content_stream(
                            model=m,
                            contents=formatted_contents,
                            config=gen_config
                        )
                        for chunk in response_stream:
                            if chunk.text:
                                full_res += chunk.text
                                placeholder_box.markdown(full_res + "▌")
                        placeholder_box.markdown(full_res)
                        active_msgs.append({"role": "assistant", "content": full_res})
                        save_current_history()
                        success = True
                        break
                    except Exception:
                        continue

                if not success:
                    placeholder_box.error("Google's servers are temporarily experiencing high demand. Please try again.")