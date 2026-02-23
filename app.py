import streamlit as st
import requests

# --- YAPILANDIRMA ---
st.set_page_config(
    page_title="Local AI Pro",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="auto", # Ekran boyutuna göre otomatik açılır/kapanır
)

st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ---------------- GLOBAL ---------------- */
html, body, [class*="st-"] {
    font-family: 'Inter', sans-serif;
    color: #EAF6FF !important;
}

/* BACKGROUND */
.stApp {
    background: radial-gradient(circle at 20% 20%, rgba(0,200,255,0.12), transparent 40%),
                radial-gradient(circle at 80% 40%, rgba(0,255,200,0.08), transparent 40%),
                linear-gradient(135deg, #050b14 0%, #07131f 50%, #040a12 100%);
    background-attachment: fixed;
}

/* ---------------- SIDEBAR ---------------- */
/* Genişlik kısıtlaması kaldırıldı, Streamlit'in mobil uyumluluğuna bırakıldı */
[data-testid="stSidebar"] {
    background: rgba(8,18,32,0.97) !important;
    backdrop-filter: blur(25px);
    border-right: 1px solid rgba(255,255,255,0.06);
}

[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-weight: 800 !important;
    color: #4DA8FF !important;
}

[data-testid="stSidebar"] .stSlider > div {
    padding-top: 10px;
    padding-bottom: 10px;
}

/* ---------------- ANA BLOK ---------------- */
/* Ekran küçüldüğünde paddingler daralacak şekilde % ve rem kullanıldı */
.main .block-container {
    padding-left: 5% !important;
    padding-right: 5% !important;
    padding-top: 2rem !important;
    max-width: 1200px !important;
}

/* ---------------- CHAT MESAJLARI ---------------- */
.stChatMessage {
    background: rgba(255,255,255,0.05) !important;
    backdrop-filter: blur(16px);
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.08);
    padding: 1.5rem !important;
    margin-bottom: 1.5rem !important;
}

/* ---------------- CHAT INPUT ---------------- */
/* Paddingler ve fontlar mobile uyumlu hale getirildi */
.stChatInputContainer {
    padding: 1rem 5% 2rem 5% !important;
    background: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(5,11,20,0.9) 100%);
}

.stChatInputContainer textarea {
    background: rgba(255,255,255,0.07) !important;
    border: 2px solid rgba(77,168,255,0.5) !important;
    border-radius: 20px !important;
    padding: 1rem !important;
    color: #ffffff !important;
    box-shadow: 0 0 15px rgba(77,168,255,0.2);
    transition: all 0.3s ease;
}

.stChatInputContainer textarea:focus {
    border: 2px solid #4DA8FF !important;
    box-shadow: 0 0 30px rgba(77,168,255,0.4);
}

/* SEND BUTON */
button[kind="primary"] {
    background: linear-gradient(135deg, #4DA8FF, #6FE7D2) !important;
    color: #07131f !important;
    font-weight: 700 !important;
    border-radius: 20px !important;
    border: none !important;
    transition: all 0.3s ease;
}

button[kind="primary"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(77,168,255,0.4);
}

/* ---------------- EXPANDER ---------------- */
.stExpander {
    background: rgba(255,255,255,0.04) !important;
    border-radius: 12px !important;
    padding: 10px !important;
}

/* ---------------- SCROLLBAR ---------------- */
::-webkit-scrollbar {
    width: 6px;
}

::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.2);
    border-radius: 10px;
}

::-webkit-scrollbar-thumb:hover {
    background: rgba(255,255,255,0.35);
}

</style>
""", unsafe_allow_html=True)

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
        if st.button("🚀 VERİLERİ YÜKLE", use_container_width=True, type="primary"):
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
            f"<div style='color:#FFD700; border:1px solid rgba(255,215,0,0.5); padding:8px; border-radius:8px; margin-bottom:5px; font-size:0.9rem;'>📁 {file_name} aktif</div>",
            unsafe_allow_html=True,
        )

    if st.session_state.indexed_files:
        st.session_state.active_doc_id = st.selectbox(
            "Aktif dokümanı seçin:",
            options=st.session_state.indexed_files,
            index=max(0, len(st.session_state.indexed_files) - 1),
        )

    st.divider()
    st.markdown("### 🧠 Sistem Ayarları")
    top_k = st.slider("Hafıza Derinliği", 1, 15, 6)
    is_streaming = st.toggle("Canlı Yazım Modu", value=True)

# --- ANA EKRAN ---
if not st.session_state.messages:
    st.markdown('<h2 style="text-align: center; color: #4DA8FF; margin-top: 2rem;">Size nasıl yardımcı olabilirim?</h2>', unsafe_allow_html=True)
    st.markdown(
        '<p style="text-align: center; color: #EAF6FF; opacity: 0.8;">Belgelerini yükle ve yüksek performanslı AI ile sohbete başla.</p>',
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