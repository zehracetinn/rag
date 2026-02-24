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

/* --- YAZI TİPİ --- */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="st-"] {
    font-family: 'Inter', sans-serif;
    color: #E2E8F0 !important; /* Göz yormayan, okunaklı kırık beyaz */
}

/* --- ANİMASYONLAR --- */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(15px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes gradientMove {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

/* --- ANA ARKA PLAN (NETFLIX DERİNLİĞİ) --- */
.stApp {
    background-color: #0B0E14;
    background-image: 
        radial-gradient(circle at 15% 50%, rgba(77, 168, 255, 0.04), transparent 50%),
        radial-gradient(circle at 85% 30%, rgba(200, 50, 150, 0.04), transparent 50%);
    background-attachment: fixed;
}

/* --- SIDEBAR (CAM EFEKTİ & YUMUŞAK GÖLGE) --- */
[data-testid="stSidebar"] {
    background: rgba(15, 20, 28, 0.85) !important;
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-right: 1px solid rgba(255, 255, 255, 0.05);
    box-shadow: 2px 0 15px rgba(0,0,0,0.3);
}

[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-weight: 700 !important;
    background: linear-gradient(135deg, #4DA8FF, #D946EF); /* Instagram/AI geçişi */
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.5px;
}

/* SIDEBAR BEYAZ BUTON VE UPLOADER DÜZELTMESİ */
[data-testid="stFileUploadDropzone"] {
    background-color: rgba(255, 255, 255, 0.03) !important;
    border: 1.5px dashed rgba(255, 255, 255, 0.15) !important;
    border-radius: 12px !important;
    padding: 20px !important;
    color: #A0AEC0 !important;
    transition: all 0.3s ease;
}
[data-testid="stFileUploadDropzone"]:hover {
    background-color: rgba(255, 255, 255, 0.06) !important;
    border-color: #4DA8FF !important;
}

/* --- ANA BLOK --- */
.main .block-container {
    padding-left: 5% !important;
    padding-right: 5% !important;
    padding-top: 3rem !important;
    max-width: 900px !important; /* ChatGPT gibi tam ortalanmış ve okunaklı */
}

/* --- SOHBET MESAJLARI (CHATGPT DÜZENİ) --- */
.stChatMessage {
    background: rgba(20, 25, 35, 0.6) !important;
    backdrop-filter: blur(10px);
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    padding: 1.5rem 2rem !important;
    margin-bottom: 1.5rem !important;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    animation: fadeIn 0.5s cubic-bezier(0.25, 0.8, 0.25, 1);
}

/* Kullanıcı mesajını biraz daha farklılaştır (İsteğe bağlı) */
[data-testid="chatAvatarIcon-user"] {
    background: linear-gradient(135deg, #FF6B6B, #5562EA) !important;
}
[data-testid="chatAvatarIcon-assistant"] {
    background: linear-gradient(135deg, #05D5FF, #5585FF) !important;
}

/* --- CHAT INPUT (GÖZ ALMAYAN, MODERN KUTU) --- */
.stChatInputContainer {
    padding: 1rem 5% 2rem 5% !important;
    background: transparent !important; /* Beyaz arka planı sildik */
}

.stChatInputContainer textarea {
    background: rgba(20, 25, 35, 0.8) !important;
    backdrop-filter: blur(15px);
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 24px !important;
    padding: 1.2rem 1.5rem !important;
    color: #F8FAFC !important;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.stChatInputContainer textarea:focus {
    border: 1px solid #4DA8FF !important;
    box-shadow: 0 0 20px rgba(77, 168, 255, 0.15), 0 8px 24px rgba(0, 0, 0, 0.3);
    outline: none !important;
}

/* --- PRIMARY BUTONLAR (INSTAGRAM/AI ANİMASYONLU) --- */
button[kind="primary"] {
    background: linear-gradient(-45deg, #EE7752, #E73C7E, #23A6D5, #23D5AB) !important;
    background-size: 300% 300% !important;
    animation: gradientMove 5s ease infinite !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    border-radius: 12px !important;
    border: none !important;
    padding: 0.6rem 1.5rem !important;
    box-shadow: 0 4px 15px rgba(231, 60, 126, 0.3);
    transition: transform 0.2s ease, box-shadow 0.2s ease !important;
}

button[kind="primary"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(231, 60, 126, 0.5);
}

/* SECONDARY BUTONLAR (Hafızayı Temizle vb.) */
button[kind="secondary"] {
    background: rgba(255, 255, 255, 0.05) !important;
    color: #E2E8F0 !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 12px !important;
    transition: all 0.3s ease;
}

button[kind="secondary"]:hover {
    background: rgba(255, 255, 255, 0.1) !important;
    border-color: rgba(255, 255, 255, 0.3) !important;
}

/* --- SCROLLBAR --- */
::-webkit-scrollbar {
    width: 6px;
    background: transparent;
}
::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 10px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.3);
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