import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# Model yükle
model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

documents = [
    "Makine öğrenmesi yapay zekanın bir alt dalıdır.",
    "Gradient descent optimizasyon algoritmasıdır.",
    "Galatasaray Türkiye'nin bir futbol kulübüdür."
]

# Embedding üret
doc_embeddings = model.encode(documents)

# FAISS index oluştur
dimension = doc_embeddings.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(np.array(doc_embeddings))

# Soru
query = "ML nedir?"
query_embedding = model.encode([query])

# En yakın 1 sonucu getir
distances, indices = index.search(np.array(query_embedding), k=1)

print("Soru:", query)
print("En yakın sonuç:", documents[indices[0][0]])
