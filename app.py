import streamlit as st
import requests
import time

# --- YAPILANDIRMA ---
st.set_page_config(
    page_title="Local AI Pro",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SARI-SİYAH-BEYAZ YÜKSEK KONTRASTLI MODERN CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

    /* Genel Yazı Boyutları ve Okunabilirlik */
    html, body, [class*="st-"] {
        font-family: 'Inter', sans-serif;
        font-size: 22px !important;
        color: #ffffff !important; /* Tüm yazılar varsayılan beyaz */
    }

    /* Ana Arka Plan: Tam Siyah */
    .stApp {
        background-color: #000000 !important;
    }

    /* Sol Panel (Sidebar): Derin Siyah ve Sarı Detaylar */
    [data-testid="stSidebar"] {
        background-color: #0a0a0a !important;
        border-right: 2px solid #FFD700; /* Vurgu Sarısı */
        width: 450px !important;
    }
    
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { 
        font-size: 36px !important; 
        color: #FFD700 !important; /* Başlıklar Sarı */
        font-weight: 800;
    }

    /* Sidebar İçindeki Sönük Yazıları Beyaz Yap */
    [data-testid="stSidebar"] .stMarkdown p, 
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stFileUploader label {
        font-size: 22px !important;
        color: #ffffff !important;
        opacity: 1 !important;
    }

    /* Mesaj Baloncukları */
    .stChatMessage {
        font-size: 24px !important;
        padding: 40px !important;
        background-color: #000000 !important;
        border-bottom: 1px solid #333333 !important;
    }

    /* Asistan Mesajı: Hafif Koyu Gri Arka Plan (Okunurluk için) */
    [data-testid="stChatMessage"]:nth-child(even) {
        background-color: #111111 !important;
    }

    /* Ana İçerik Metinleri */
    .stMarkdown p, .stMarkdown li {
        color: #ffffff !important;
        line-height: 1.7;
    }

    /* Dev Başlıklar */
    .hero-title {
        font-size: 72px !important;
        font-weight: 800;
        color: #FFD700; /* Sarı */
        text-align: center;
        margin-top: 50px;
    }

    .hero-subtitle {
        font-size: 28px !important;
        color: #ffffff;
        text-align: center;
        margin-bottom: 50px;
    }

    /* Giriş Kutusu (Chat Input) - OKUNAKLI YAPILDI */
    .stChatInputContainer {
        padding: 2rem 10% !important;
        background-color: #000000 !important;
    }

    .stChatInputContainer textarea {
        background-color: #1a1a1a !important;
        border: 2px solid #FFD700 !important; /* Sarı Kenarlık */
        color: #ffffff !important;
        border-radius: 12px !important;
        font-size: 24px !important;
        padding: 20px !important;
    }

    /* Placeholder (Yazı yazılmadan önceki gri yazı) Rengini Beyazlat */
    .stChatInputContainer textarea::placeholder {
        color: #aaaaaa !important;
    }

    /* Slider ve Toggle */
    .stSlider label, .stToggle label {
        color: #FFD700 !important;
        font-weight: 600 !important;
    }
    
    /* Slider Çubuğu */
    .st-eb { background-color: #FFD700 !important; }

    /* Dosya Yükleme Alanı */
    .stFileUploader section {
        background-color: #1a1a1a !important;
        border: 2px dashed #FFD700 !important;
        border-radius: 15px !important;
        padding: 30px !important;
    }
    
    .stFileUploader section div div {
        color: #ffffff !important; /* "Drag and drop" yazısı */
    }

    /* Butonlar */
    button[kind="primary"] {
        background-color: #FFD700 !important; 
        color: #000000 !important;
        font-weight: 800 !important;
        border: none !important;
        font-size: 22px !important;
    }
    
    /* Kaynaklar/Expander */
    .stExpander {
        background-color: #1a1a1a !important;
        border: 1px solid #FFD700 !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- BACKEND MANTIĞI ---
API_BASE = "http://127.0.0.1:8000"

if "messages" not in st.session_state:
    st.session_state.messages = []
if "indexed_files" not in st.session_state:
    st.session_state.indexed_files = []

# --- SIDEBAR (KONTROL PANELİ) ---
with st.sidebar:
    st.markdown("<h2>⚙️ Kontrol Paneli</h2>", unsafe_allow_html=True)
    
    st.markdown("### 📄 Doküman Yönetimi")
    uploaded_files = st.file_uploader(
        "Dosya Yükle",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )

    if uploaded_files:
        if st.button("🚀 VERİLERİ SİSTEME YÜKLE", use_container_width=True, type="primary"):
            with st.status("Yapay zeka belgeleri okuyor...", expanded=False) as status:
                try:
                    for file in uploaded_files:
                        files = {"file": (file.name, file.getvalue(), "application/pdf")}
                        response = requests.post(f"{API_BASE}/upload", files=files, timeout=300)
                        if response.status_code == 200:
                            if file.name not in st.session_state.indexed_files:
                                st.session_state.indexed_files.append(file.name)
                    status.update(label="Yükleme Başarılı!", state="complete")
                    st.rerun()
                except Exception as e:
                    st.error(f"Hata: {e}")

    # Yüklenen dosyaların listesi (Bilgi kutucuklarını sarı çerçeveli yaptık)
    for file_name in st.session_state.indexed_files:
        st.markdown(f"<div style='color:#FFD700; border:1px solid #FFD700; padding:10px; border-radius:10px; margin-bottom:5px;'>📁 {file_name} aktif</div>", unsafe_allow_html=True)
    
    st.divider()
    st.markdown("### 🧠 Sistem Ayarları")
    top_k = st.slider("Hafıza Derinliği", 1, 15, 6)
    is_streaming = st.toggle("Canlı Yazım Modu (On/Off)", value=True)

# --- ANA EKRAN ---
if not st.session_state.messages:
    st.markdown('<h1 class="hero-title">Size nasıl yardımcı olabilirim?</h1>', unsafe_allow_html=True)
    st.markdown('<p class="hero-subtitle">Belgelerini yükle ve yüksek performanslı AI ile sohbete başla.</p>', unsafe_allow_html=True)
else:
    st.markdown('<div style="margin-bottom: 20px;"></div>', unsafe_allow_html=True)

# Sohbet Akışı
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- CHAT INPUT (GİRİŞ ALANI) ---
if prompt := st.chat_input("Buraya bir soru yazın..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            if is_streaming:
                with requests.post(
                f"{API_BASE}/ask-stream",
                data={"question": prompt, "top_k": top_k},
                stream=True,
                timeout=300
            ) as r:
                    for line in r.iter_lines(decode_unicode=True):
                        if line and line.startswith("data: "):
                            chunk = line.replace("data: ", "")
                            if chunk == "[DONE]": break
                            full_response += chunk
                            message_placeholder.markdown(full_response + " ▌")
                message_placeholder.markdown(full_response)
            

            else:
                r = requests.post(
                f"{API_BASE}/ask",
                data={
                    "question": prompt,
                    "top_k": top_k
                },
                timeout=300
            )
            data = r.json()
            full_response = data.get("answer", "Yanıt oluşturulamadı.")
            sources = data.get("sources", [])
            message_placeholder.markdown(full_response)

            if sources:
                with st.expander("📚 Kaynaklar"):
                    for s in sources:
                        st.write(f"• {s['dosya']} → Parça {s['parca']}")






            
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            st.error(f"Bağlantı Hatası: {e}")