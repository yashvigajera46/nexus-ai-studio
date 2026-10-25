import io
import os
import random
import sqlite3
import time
import urllib.parse
from datetime import datetime
from PIL import Image
import requests
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError
from pypdf import PdfReader
from gtts import gTTS

# Page Configuration
st.set_page_config(
    page_title="Nexus AI Studio",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- PERSISTENT SEARCH & QUERY DATABASE -----------------
DB_FILE = "nexus_vault.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS global_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            mode TEXT,
            query TEXT,
            response TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_event(mode, query, response):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT INTO global_history (timestamp, mode, query, response) VALUES (?, ?, ?, ?)",
            (now, mode, query, response)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Logging error: {e}")

def get_all_logs(search_filter=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if search_filter:
        c.execute(
            "SELECT timestamp, mode, query, response FROM global_history WHERE query LIKE ? OR response LIKE ? ORDER BY id DESC",
            (f"%{search_filter}%", f"%{search_filter}%")
        )
    else:
        c.execute("SELECT timestamp, mode, query, response FROM global_history ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

init_db()

# ----------------- CREDENTIALS & CLIENT -----------------
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
    AVAILABLE_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

# ----------------- SESSION STATES -----------------
if "sessions" not in st.session_state:
    st.session_state.sessions = {
        "New Conversation": [
            {"role": "assistant", "content": "Welcome to Nexus AI Studio. What would you like to explore or create today?"}
        ]
    }

if "image_history" not in st.session_state:
    st.session_state.image_history = []

if "pinned_chats" not in st.session_state:
    st.session_state.pinned_chats = set()

if "current_session" not in st.session_state or st.session_state.current_session not in st.session_state.sessions:
    st.session_state.current_session = list(st.session_state.sessions.keys())[0]

if "doc_context" not in st.session_state:
    st.session_state.doc_context = ""
if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = None
if "rename_target" not in st.session_state:
    st.session_state.rename_target = None
if "active_theme" not in st.session_state:
    st.session_state.active_theme = "Sunset Peach"

# ----------------- THEMES -----------------
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
    },
    "Neon Cyberpunk": {
        "bg": "radial-gradient(circle at 50% 0%, #101c26 0%, #050d12 100%)",
        "accent": "linear-gradient(135deg, #00f2fe 0%, #4facfe 100%)",
        "border": "#1b3c4f",
        "input_bg": "#0c1a24"
    }
}

theme_conf = THEMES[st.session_state.active_theme]

# UI Styling
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
    section[data-testid="stSidebar"] button p {{
        color: #f8fafc !important;
        font-size: 0.95rem !important;
        font-weight: 500 !important;
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
    .history-card {{
        background: #141721;
        border: 1px solid #232938;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }}
</style>
""", unsafe_allow_html=True)

# ----------------- SIDEBAR -----------------
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
        st.rerun()

    st.markdown("---")
    
    app_mode = st.radio(
        "Mode:",
        ["💬 Chat Assistant", "🎨 Image Generator", "🖼️ Art Gallery", "📄 Document Q&A (RAG)", "📜 Global History Explorer"],
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

    with st.expander("⚙️ Advanced Parameters"):
        enable_tts = st.checkbox("Enable Voice Audio (TTS)", value=False)
        selected_theme = st.selectbox(
            "UI Accent Palette:",
            list(THEMES.keys()),
            index=list(THEMES.keys()).index(st.session_state.active_theme)
        )
        if selected_theme != st.session_state.active_theme:
            st.session_state.active_theme = selected_theme
            st.rerun()

    st.markdown("---")

    # Persistent search & chat switchers in sidebar
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
            st.session_state.current_session = list(st.session_state.sessions.keys())[0]
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
            st.rerun()
        if col_r2.button("Cancel", use_container_width=True):
            st.session_state.rename_target = None
            st.rerun()

    all_chat_names = [s for s in st.session_state.sessions.keys() if search_query in s.lower()]

    pinned_visible = [s for s in all_chat_names if s in st.session_state.pinned_chats]
    if pinned_visible:
        st.markdown("#### 📌 **Pinned**")
        for s_name in pinned_visible:
            render_chat_row(s_name, is_pinned=True)

    recents_visible = [s for s in all_chat_names if s not in st.session_state.pinned_chats]
    st.markdown("#### 🕒 **Recents**")
    for s_name in recents_visible:
        render_chat_row(s_name, is_pinned=False)

# Header
st.markdown("<div class='hero-title'>Nexus AI Studio ✨</div>", unsafe_allow_html=True)
st.markdown(f"<div class='hero-subtitle'>Mode: <b>{app_mode}</b></div>", unsafe_allow_html=True)

# ==========================================
# PAGE 1: 📜 GLOBAL HISTORY EXPLORER
# ==========================================
if app_mode == "📜 Global History Explorer":
    st.markdown("### 📜 **Search & Activity Vault**")
    st.caption("Browse all historical queries, prompts, and generations submitted across all users and sessions.")

    search_term = st.text_input("🔍 Search all recorded logs:", placeholder="Filter by keywords...")
    logs = get_all_logs(search_term)

    if not logs:
        st.info("No recorded history found matching your search.")
    else:
        st.markdown(f"**Found {len(logs)} log entries:**")
        for ts, mode_name, q, r in logs:
            with st.expander(f"🕒 [{ts}] | {mode_name} ➔ {q[:60]}..."):
                st.markdown(f"**Full Query / Prompt:**")
                st.info(q)
                st.markdown(f"**Saved Answer / Action:**")
                if "Image Generated" in r:
                    st.success(r)
                else:
                    st.markdown(r)
    st.stop()

# ==========================================
# PAGE 2: 🖼️ ART GALLERY
# ==========================================
elif app_mode == "🖼️ Art Gallery":
    st.markdown("### 🖼️ **Visual Showcase**")
    if not st.session_state.image_history:
        st.info("No generated images yet! Switch to '🎨 Image Generator' to create your first artwork.")
    else:
        cols = st.columns(3)
        for idx, img_item in enumerate(reversed(st.session_state.image_history)):
            with cols[idx % 3]:
                st.image(img_item["content"], caption=img_item.get("caption", ""), use_container_width=True)
                if "bytes" in img_item:
                    st.download_button(
                        label="📥 Download",
                        data=img_item["bytes"],
                        file_name=f"nexus_artwork_{idx+1}.png",
                        mime="image/png",
                        key=f"gal_dl_{idx}"
                    )
    st.stop()

# ==========================================
# PAGE 3: 🎨 HIGH-DEFINITION IMAGE GENERATOR
# ==========================================
elif app_mode == "🎨 Image Generator":
    st.markdown("### 🎨 **AI Image Creation Studio**")
    st.caption("Generate crisp, high-definition 1024px artwork without watermarks in seconds.")

    if not st.session_state.image_history:
        st.markdown(
            """
            <div style="text-align: center; padding: 40px; color: #888; border: 1px dashed #333; border-radius: 12px; margin: 20px 0;">
                No artwork generated yet in this session. Type your visual description below!
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        for idx, img_item in enumerate(st.session_state.image_history):
            with st.chat_message("user"):
                st.markdown(f"**Prompt:** {img_item.get('caption', '')}")
            with st.chat_message("assistant"):
                st.image(img_item["content"], use_container_width=True)
                st.download_button(
                    label="📥 Download High-Res Image",
                    data=img_item["bytes"],
                    file_name="nexus_artwork.png",
                    mime="image/png",
                    key=f"img_dl_{idx}"
                )

    if prompt := st.chat_input("Describe the image you want to create..."):
        with st.chat_message("user"):
            st.markdown(f"**Prompt:** {prompt}")

        with st.chat_message("assistant"):
            with st.spinner("Rendering sharp high-definition artwork (3-5s)..."):
                try:
                    clean_p = prompt.strip()
                    enhanced = f"{clean_p}, sharp focus, highly detailed, 8k resolution, octane 3d render, professional studio lighting"
                    encoded_prompt = urllib.parse.quote(enhanced)
                    random_seed = random.randint(1000, 999999)

                    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1150&model=turbo&seed={random_seed}&nologo=true"

                    response = requests.get(image_url, timeout=30)
                    if response.status_code == 200:
                        raw_img = Image.open(io.BytesIO(response.content))
                        w, h = raw_img.size

                        clean_img = raw_img.crop((0, 0, w, h - 126))

                        buf = io.BytesIO()
                        clean_img.save(buf, format="PNG")
                        clean_bytes = buf.getvalue()

                        st.session_state.image_history.append({
                            "content": clean_img,
                            "bytes": clean_bytes,
                            "caption": prompt
                        })
                        
                        # Save image prompt to permanent database history
                        log_event("🎨 Image Generation", prompt, "Image Generated Successfully (1024x1024 Turbo)")
                        st.rerun()
                    else:
                        st.error("Image server busy. Please send your prompt again.")
                except requests.exceptions.Timeout:
                    st.error("Server took too long to respond. Please try sending again.")
                except Exception as e:
                    st.error(f"Image error: {str(e)}")

# ==========================================
# PAGE 4: 📄 DOCUMENT Q&A (RAG)
# ==========================================
elif app_mode == "📄 Document Q&A (RAG)":
    st.markdown("### 📄 **Document Intelligence (RAG)**")
    if not st.session_state.doc_context:
        st.info("Please upload a PDF or TXT file using the sidebar to begin querying your document.")
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
                with st.spinner("Reading document..."):
                    generated_text = ""
                    for m in AVAILABLE_MODELS:
                        try:
                            res = client.models.generate_content(
                                model=m,
                                contents=rag_prompt,
                            )
                            if res and res.text:
                                generated_text = res.text
                                break
                        except Exception:
                            continue

                    if generated_text:
                        placeholder_box.markdown(generated_text)
                        # Save RAG search to permanent database history
                        log_event(f"📄 Document Q&A ({st.session_state.uploaded_file_name})", prompt, generated_text)
                    else:
                        placeholder_box.error("Unable to answer from the document. Please try again.")

# ==========================================
# PAGE 5: 💬 CHAT ASSISTANT
# ==========================================
else:
    active_msgs = st.session_state.sessions[st.session_state.current_session]
    
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

        active_msgs.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        if not client:
            st.error("Gemini API key is not ready. Please verify GEMINI_API_KEY in Secrets.")
        else:
            with st.chat_message("assistant"):
                placeholder_box = st.empty()
                with st.spinner("Thinking..."):
                    generated_text = ""
                    error_logs = []

                    for m in AVAILABLE_MODELS:
                        try:
                            res = client.models.generate_content(
                                model=m,
                                contents=prompt,
                            )
                            if res and res.text:
                                generated_text = res.text
                                break
                        except Exception as err:
                            error_logs.append(f"{m}: {str(err)}")
                            continue

                    if generated_text:
                        placeholder_box.markdown(generated_text)
                        active_msgs.append({"role": "assistant", "content": generated_text})
                        # Save Chat search and response to permanent database history
                        log_event("💬 Chat Assistant", prompt, generated_text)
                    else:
                        placeholder_box.error(f"Could not reach models. Details: {' | '.join(error_logs[:2])}")