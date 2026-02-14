import numpy as np
from sentence_transformers import SentenceTransformer
from numpy.linalg import norm
import torch

# M4 Air için en başarılı ve hızlı çok dilli model
model_ismi = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# M4'ün gücünü kullanmak için cihazı seçiyoruz
cihaz = "mps" if torch.backends.mps.is_available() else "cpu"
print(f"Sistem şu cihazı kullanıyor: {cihaz.upper()}")

# Modeli yükle
model = SentenceTransformer(model_ismi, device=cihaz)

# Örnek cümleler (Türkçe ve İngilizceyi bile birbirine bağlar!)
sentences = [
    "Makine öğrenmesi nedir?",
    "What is machine learning?", # Anlam aynı, dil farklı
    "Galatasaray dün akşam kaç gol attı?",
]

# Embedding üret
embeddings = model.encode(sentences)

def cosine_similarity(a, b):
    return np.dot(a, b) / (norm(a) * norm(b))

# Benzerlikleri hesapla
sim_tr_en = cosine_similarity(embeddings[0], embeddings[1])
sim_tr_fb = cosine_similarity(embeddings[0], embeddings[2])

print(f"Türkçe ↔ İngilizce Benzerliği (Aynı anlam): {sim_tr_en:.4f}")
print(f"ML ↔ Futbol Benzerliği: {sim_tr_fb:.4f}")