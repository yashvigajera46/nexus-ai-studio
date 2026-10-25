# Nexus AI Studio ✨

A multi-modal AI productivity platform built with Python and Streamlit. Nexus AI Studio integrates LLM-driven chat assistance, document analysis via Retrieval-Augmented Generation (RAG), and watermark-free high-definition generative image creation.

---

## 🚀 Key Features

* **Intelligent Conversational Agent:** Multi-persona technical assistant with customizable temperature, max tokens, and automatic server fallback logic.
* **Document Q&A (RAG Pipeline):** Ingests and parses `.pdf` and `.txt` files on the fly to deliver context-grounded summaries and document-level answers.
* **Photorealistic Image Generation:** Generates watermark-free, high-resolution visuals powered by the Flux model engine with automatic prompt optimization.
* **Visual Asset Gallery:** Aggregates and displays generated artwork in a responsive masonry grid with direct high-res downloads.
* **Local Session Persistence:** Retains multi-turn conversation threads, pinned chats, and history across network interruptions and reloads using JSON state serialization.
* **Text-to-Speech (TTS):** Integrated voice playback for AI responses.

---

## 🛠️ Tech Stack

* **Frontend & UI:** Streamlit, CSS3 Glassmorphism
* **Backend & Logic:** Python 3
* **AI & LLM Services:** Google Gemini API (`google-genai`), Flux Engine (via Pollinations)
* **Document Processing:** PyPDF
* **Media & Audio:** Pillow (PIL), gTTS

