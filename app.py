import streamlit as st
import requests

# --- YAPILANDIRMA ---
st.set_page_config(
    page_title="Local AI Pro",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CSS ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    html, body, [class*="st-"] { font-family: 'Inter', sans-serif; font-size: 22px !important; color: #ffffff !important; }
    .stApp { background-color: #000000 !important; }
    [data-testid="stSidebar"] { background-color: #0a0a0a !important; border-right: 2px solid #FFD700; width: 450px !important; }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #FFD700 !important; font-weight: 800; font-size: 36px !important; }
    .stChatMessage { font-size: 24px !important; padding: 40px !important; background-color: #000000 !important; border-bottom: 1px solid #333333 !important; }
    [data-testid="stChatMessage"]:nth-child(even) { background-color: #111111 !important; }
    .hero-title { font-size: 72px !important; font-weight: 800; color: #FFD700; text-align: center; margin-top: 50px; }
    .hero-subtitle { font-size: 28px !important; color: #ffffff; text-align: center; margin-bottom: 50px; }
    .stChatInputContainer { padding: 2rem 10% !important; background-color: #000000 !important; }
    .stChatInputContainer textarea { background-color: #1a1a1a !important; border: 2px solid #FFD700 !important; color: #ffffff !important; border-radius: 12px !important; font-size: 24px !important; }
    button[kind="primary"] { background-color: #FFD700 !important; color: #000000 !important; font-weight: 800 !important; font-size: 22px !important; border: none !important; }
    .stExpander { background-color: #1a1a1a !important; border: 1px solid #FFD700 !important; }
    </style>
""",
    unsafe_allow_html=True,
)

# --- BACKEND ---
API_BASE = "http://127.0.0.1:8000"

if "messages" not in st.session_state:
    st.session_state.messages = []
if "indexed_files" not in st.session_state:
    st.session_state.indexed_files = []
if "active_doc_id" not in st.session_state:
    st.session_state.active_doc_id = None

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h2>⚙️ Kontrol Paneli</h2>", unsafe_allow_html=True)
    st.markdown("### 📄 Doküman Yönetimi")
    if st.button("🧹 Hafızayı Temizle", use_container_width=True):
        try:
            rr = requests.post(f"{API_BASE}/reset", timeout=60)
            if rr.status_code == 200:
                st.session_state.indexed_files = []
                st.session_state.active_doc_id = None
                st.session_state.messages = []
                st.success("Sistem hafızası temizlendi.")
                st.rerun()
            else:
                st.error(f"Temizleme hatası: {rr.text}")
        except Exception as e:
            st.error(f"Temizleme hatası: {e}")

    uploaded_files = st.file_uploader(
        "Dosya Yükle",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded_files:
        if st.button("🚀 VERİLERİ SİSTEME YÜKLE", use_container_width=True, type="primary"):
            with st.status("Yapay zeka belgeleri okuyor...", expanded=False) as status:
                try:
                    for file in uploaded_files:
                        files = {"file": (file.name, file.getvalue(), "application/pdf")}
                        response = requests.post(f"{API_BASE}/upload", files=files, timeout=300)
                        if response.status_code == 200 and file.name not in st.session_state.indexed_files:
                            st.session_state.indexed_files.append(file.name)
                    status.update(label="Yükleme Başarılı!", state="complete")
                    st.rerun()
                except Exception as e:
                    st.error(f"Hata: {e}")

    for file_name in st.session_state.indexed_files:
        st.markdown(
            f"<div style='color:#FFD700; border:1px solid #FFD700; padding:10px; border-radius:10px; margin-bottom:5px;'>📁 {file_name} aktif</div>",
            unsafe_allow_html=True,
        )

    if st.session_state.indexed_files:
        st.session_state.active_doc_id = st.selectbox(
            "Soru sorulacak aktif doküman",
            options=st.session_state.indexed_files,
            index=max(0, len(st.session_state.indexed_files) - 1),
        )

    st.divider()
    st.markdown("### 🧠 Sistem Ayarları")
    top_k = st.slider("Hafıza Derinliği", 1, 15, 6)
    is_streaming = st.toggle("Canlı Yazım Modu", value=True)

# --- ANA EKRAN ---
if not st.session_state.messages:
    st.markdown('<h1 class="hero-title">Size nasıl yardımcı olabilirim?</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hero-subtitle">Belgelerini yükle ve yüksek performanslı AI ile sohbete başla.</p>',
        unsafe_allow_html=True,
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- CHAT ---
if prompt := st.chat_input("Buraya bir soru yazın..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        sources = []

        try:
            if is_streaming:
                with requests.post(
                    f"{API_BASE}/ask-stream",
                    data={
                        "question": prompt,
                        "top_k": top_k,
                        "doc_id": st.session_state.active_doc_id,
                    },
                    stream=True,
                    timeout=300,
                ) as r:
                    if r.status_code != 200:
                        st.error(f"Sunucu Hatası: {r.text}")
                    else:
                        for line in r.iter_lines(decode_unicode=True):
                            if not line or not line.startswith("data: "):
                                continue

                            chunk = line.replace("data: ", "", 1)

                            if chunk == "[DONE]":
                                break

                            if chunk.startswith("[ERROR]"):
                                st.error(chunk)
                                full_response = ""
                                break

                            full_response += chunk
                            message_placeholder.markdown(full_response + " ▌")

                        if full_response:
                            message_placeholder.markdown(full_response)
            else:
                r = requests.post(
                    f"{API_BASE}/ask",
                    data={
                        "question": prompt,
                        "top_k": top_k,
                        "doc_id": st.session_state.active_doc_id,
                    },
                    timeout=300,
                )
                if r.status_code == 200:
                    data = r.json()
                    full_response = data.get("answer", "")
                    sources = data.get("sources", [])
                    message_placeholder.markdown(full_response)
                else:
                    st.error(f"Sunucu Hatası: {r.status_code} - {r.text}")

            if sources:
                with st.expander("📚 Kaynaklar"):
                    for s in sources:
                        st.write(f"• {s['dosya']} → Parça {s['parca']}")

            if full_response:
                st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            st.error(f"Bağlantı Hatası: {e}")
