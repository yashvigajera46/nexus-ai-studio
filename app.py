import base64
import io
import os
import random
import time
import urllib.parse
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

# ----------------- CREDENTIALS & CLIENT -----------------
load_dotenv()

# Prioritize Streamlit Cloud Secrets, fallback to local .env
api_key = None
if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("Missing Gemini API Key. Please add `GEMINI_API_KEY` to your Streamlit Cloud Secrets or local `.env` file.")
    st.stop()

client = genai.Client(api_key=api_key)
MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

# ----------------- ISOLATED USER SESSION STATE -----------------
# All storage exists strictly in this browser session's RAM (zero shared disk access)
if "sessions" not in st.session_state:
    st.session_state.sessions = {
        "New Conversation": [
            {"role": "assistant", "type": "text", "content": "Welcome to Nexus AI Studio. What would you like to explore or create today?"}
        ]
    }

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

# UI CSS: Keeps navigation arrow visible, eliminates branding, protects layout
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

    /* Sidebar toggle button always accessible */
    [data-testid="collapsedControl"],
    [data-testid="collapsedControl"] button,
    button[data-testid="baseButton-headerNoPadding"] {{
        display: inline-flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        z-index: 999999 !important;
    }}

    /* Hide right-hand toolbar, GitHub source button, and 3-dots menu */
    [data-testid="stToolbarActions"],
    header a[href*="github.com"],
    header .stDeployButton,
    header button[title="View source on GitHub"],
    #MainMenu,
    [data-testid="stMainMenu"] {{
        display: none !important;
        visibility: hidden !important;
    }}

    /* Hide footer and viewer counter badges */
    footer {{
        display: none !important;
        visibility: hidden !important;
    }}
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
</style>
""", unsafe_allow_html=True)

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.markdown("### ✨ **Nexus AI**")

    if st.button("✏️ New chat", use_container_width=True):
        new_id = f"Chat {len(st.session_state.sessions) + 1}"
        st.session_state.sessions[new_id] = [
            {"role": "assistant", "type": "text", "content": "How can I assist you in this new session?"}
        ]
        st.session_state.current_session = new_id
        st.session_state.doc_context = ""
        st.session_state.uploaded_file_name = None
        st.rerun()

    st.markdown("---")
    
    app_mode = st.radio(
        "Mode:",
        ["💬 Chat Assistant", "📄 Document Q&A (RAG)", "🎨 Image Generator", "🖼️ Art Gallery"],
        index=0
    )

    bot_persona = "Code Mentor"
    if app_mode == "💬 Chat Assistant":
        bot_persona = st.selectbox(
            "Persona:",
            ["Code Mentor", "Concise Pro", "Creative Explainer", "Research Analyst"],
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
        temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.05)
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

    st.markdown("---")
    cur_chat = st.session_state.sessions.get(st.session_state.current_session, [])
    export_text = "\n\n".join([f"**{m['role'].upper()}**: {m['content']}" for m in cur_chat if m.get("type") == "text"])
    st.download_button(
        label="💾 Export Chat (.md)",
        data=export_text,
        file_name=f"{st.session_state.current_session}.md",
        mime="text/markdown",
        use_container_width=True
    )

# Header
st.markdown("<div class='hero-title'>Nexus AI Studio ✨</div>", unsafe_allow_html=True)
st.markdown(
    f"<div class='hero-subtitle'>Conversation: <b>{st.session_state.current_session}</b> | Mode: <b>{app_mode}</b></div>",
    unsafe_allow_html=True
)

# ----------------- ART GALLERY VIEW -----------------
if app_mode == "🖼️ Art Gallery":
    st.markdown("### 🖼️ **Generated Visual Assets**")
    all_images = []
    for s_name, msgs in st.session_state.sessions.items():
        for m in msgs:
            if m.get("type") == "image":
                all_images.append(m)

    if not all_images:
        st.info("No generated images yet! Switch to '🎨 Image Generator' mode and create artwork.")
    else:
        cols = st.columns(3)
        for idx, img_item in enumerate(all_images):
            with cols[idx % 3]:
                st.image(img_item["content"], caption=img_item.get("caption", ""), use_container_width=True)
                if "bytes" in img_item:
                    st.download_button(
                        label="📥 Download",
                        data=img_item["bytes"],
                        file_name=f"nexus_gallery_{idx+1}.png",
                        mime="image/png",
                        key=f"gal_dl_{idx}"
                    )
    st.stop()

# ----------------- CHAT RENDERING -----------------
active_msgs = st.session_state.sessions[st.session_state.current_session]
for idx, msg in enumerate(active_msgs):
    with st.chat_message(msg["role"]):
        if msg.get("type") == "image":
            st.image(msg["content"], caption=msg.get("caption", "Generated Artwork"), use_container_width=True)
            if "bytes" in msg:
                st.download_button(
                    label="📥 Download High-Res Image",
                    data=msg["bytes"],
                    file_name="nexus_artwork.png",
                    mime="image/png",
                    key=f"dl_img_{idx}"
                )
        else:
            st.markdown(msg["content"])
            if enable_tts and msg["role"] == "assistant" and len(msg.get("content", "")) > 5:
                if st.button("🔊 Play Voice", key=f"tts_{idx}"):
                    try:
                        tts = gTTS(text=msg["content"][:400], lang="en")
                        audio_buffer = io.BytesIO()
                        tts.write_to_fp(audio_buffer)
                        st.audio(audio_buffer.getvalue(), format="audio/mp3", autoplay=True)
                    except Exception:
                        st.warning("TTS audio generation requires an active network.")

if app_mode == "💬 Chat Assistant":
    placeholder = "Ask any technical question or discuss ideas..."
elif app_mode == "📄 Document Q&A (RAG)":
    placeholder = f"Ask questions about '{st.session_state.uploaded_file_name}'..." if st.session_state.uploaded_file_name else "Please upload a document in the sidebar first..."
else:
    placeholder = "Describe the image you want to create..."

# ----------------- INPUT HANDLING -----------------
if prompt := st.chat_input(placeholder):
    current_key = st.session_state.current_session
    if current_key.startswith("Chat ") or current_key == "New Conversation":
        new_title = prompt[:24] + ("..." if len(prompt) > 24 else "")
        st.session_state.sessions[new_title] = st.session_state.sessions.pop(current_key)
        if current_key in st.session_state.pinned_chats:
            st.session_state.pinned_chats.remove(current_key)
            st.session_state.pinned_chats.add(new_title)
        st.session_state.current_session = new_title
        active_msgs = st.session_state.sessions[new_title]

    active_msgs.append({"role": "user", "type": "text", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 1. Image Mode (No Watermark + Adaptive Stylization)
    if app_mode == "🎨 Image Generator":
        with st.chat_message("assistant"):
            with st.spinner("Generating artwork..."):
                try:
                    base_prompt = prompt.strip()
                    stylized = ["chibi", "tinytan", "figurine", "3d", "anime", "cartoon", "render"]
                    
                    if any(k in base_prompt.lower() for k in stylized):
                        enhanced_prompt = f"{base_prompt}, collectible 3D figurine, smooth clay material, studio lighting, centered composition"
                    else:
                        enhanced_prompt = f"{base_prompt}, 4k resolution, clean lighting, sharp focus"

                    encoded_prompt = urllib.parse.quote(enhanced_prompt)
                    random_seed = random.randint(1000, 999999)

                    # Fetch at 1024x1150 so we can cut the 126px bottom banner off completely
                    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1150&model=flux&seed={random_seed}&nologo=true"

                    response = requests.get(image_url, timeout=45)
                    if response.status_code == 200:
                        raw_img = Image.open(io.BytesIO(response.content))
                        w, h = raw_img.size

                        # Crop out the entire bottom watermark
                        clean_img = raw_img.crop((0, 0, w, h - 126))

                        buf = io.BytesIO()
                        clean_img.save(buf, format="PNG")
                        clean_bytes = buf.getvalue()

                        st.image(clean_img, caption=prompt, use_container_width=True)
                        active_msgs.append({
                            "role": "assistant",
                            "type": "image",
                            "content": clean_img,
                            "bytes": clean_bytes,
                            "caption": prompt
                        })
                        st.rerun()
                    else:
                        st.error("Image generation server busy. Please submit your prompt again.")
                except Exception as e:
                    st.error(f"Image error: {str(e)}")

    # 2. Document Q&A (RAG)
    elif app_mode == "📄 Document Q&A (RAG)":
        if not st.session_state.doc_context:
            with st.chat_message("assistant"):
                warning_text = "Please upload a PDF or TXT file using the sidebar first so I have data to reference!"
                st.warning(warning_text)
                active_msgs.append({"role": "assistant", "type": "text", "content": warning_text})
        else:
            rag_prompt = (
                f"You are an expert document analysis assistant. Answer the user's question accurately and strictly based on the following document content.\n\n"
                f"--- DOCUMENT CONTENT ---\n{st.session_state.doc_context}\n--- END DOCUMENT ---\n\n"
                f"User Question: {prompt}"
            )
            response_text = ""
            with st.chat_message("assistant"):
                with st.spinner("Analyzing document context..."):
                    for m in MODELS:
                        try:
                            res = client.models.generate_content(
                                model=m,
                                contents=rag_prompt,
                            )
                            response_text = res.text
                            break
                        except APIError:
                            continue

                if response_text:
                    st.markdown(response_text)
                    active_msgs.append({"role": "assistant", "type": "text", "content": response_text})
                else:
                    st.error("Server is busy. Please resend your message.")

    # 3. Chat Assistant
    else:
        persona_prompts = {
            "Code Mentor": "You are an elite software architect. Provide clean, production-grade code, clear explanations, and modern best practices.",
            "Concise Pro": "Deliver high-impact, direct bullet points with zero conversational fluff.",
            "Creative Explainer": "Break down complex topics into vivid real-world analogies and engaging storytelling.",
            "Research Analyst": "Provide structured, rigorous, and deeply technical evaluations with key trade-offs."
        }
        system_instruction = persona_prompts[bot_persona]
        full_prompt = f"System Instruction: {system_instruction}\n\nUser Question: {prompt}"

        response_text = ""
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                for m in MODELS:
                    try:
                        res = client.models.generate_content(
                            model=m,
                            contents=full_prompt,
                        )
                        response_text = res.text
                        break
                    except APIError:
                        continue

            if response_text:
                st.markdown(response_text)
                active_msgs.append({"role": "assistant", "type": "text", "content": response_text})
            else:
                st.error("Server is busy. Please resend your message.")