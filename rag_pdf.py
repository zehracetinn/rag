import numpy as np
import faiss
import requests
import torch
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


# --------------------------------------------------
# 1️⃣ PDF OKUMA
# --------------------------------------------------
def read_pdf(path):
    reader = PdfReader(path)
    text = ""
    for page in reader.pages:
        content = page.extract_text()
        if content:
            text += content + "\n"
    return text


# --------------------------------------------------
# 2️⃣ CHUNKING
# --------------------------------------------------
def chunk_text(text, chunk_size=800, overlap=150):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


# --------------------------------------------------
# 3️⃣ LLaMA API
# --------------------------------------------------
def call_llama(prompt):
    url = "http://localhost:11434/api/generate"

    payload = {
        "model": "llama3-tr",
        "prompt": prompt,
        "stream": False
    }

    response = requests.post(url, json=payload)
    return response.json()["response"]


# --------------------------------------------------
# 4️⃣ MAIN
# --------------------------------------------------
if __name__ == "__main__":

    pdf_path = "ornek.pdf"

    text = read_pdf(pdf_path)
    chunks = chunk_text(text)

    print("Toplam chunk:", len(chunks))

    # --------------------------------------------------
    # 🔥 EMBEDDING MODEL (MPS VARSA KULLAN)
    # --------------------------------------------------
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print("Embedding cihazı:", device)

    embed_model = SentenceTransformer(
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        device=device
    )

    doc_embeddings = embed_model.encode(chunks)

    # --------------------------------------------------
    # 🔍 FAISS INDEX
    # --------------------------------------------------
    dimension = doc_embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(doc_embeddings))

    # --------------------------------------------------
    # ❓ SORU
    # --------------------------------------------------
    question = input("\nSorunuzu yazın: ").strip()

    query_embedding = embed_model.encode([question])

    # --------------------------------------------------
    # 🔥 HYBRID RETRIEVAL LOGIC
    # --------------------------------------------------
    summary_keywords = ["ana konu", "özet", "genel", "tamamı", "ne anlatıyor"]

    if any(keyword in question.lower() for keyword in summary_keywords):
        print("\n⚡ Summary Mode: Tüm doküman bağlamı kullanılıyor.\n")
        context = "\n\n".join(chunks)
    else:
        print("\n⚡ Semantic Search Mode: FAISS kullanılıyor.\n")
        distances, indices = index.search(np.array(query_embedding), k=2)
        context = "\n\n".join([chunks[i] for i in indices[0]])

    print("\n--- SEÇİLEN BAĞLAM ---\n")
    print(context)
    print("\n----------------------\n")

    # --------------------------------------------------
    # 🧠 GÜÇLÜ RAG PROMPT
    # --------------------------------------------------
    prompt = f"""
Sen bir doküman analiz sistemisin.

Kurallar:
- SADECE aşağıdaki BAĞLAM içindeki bilgileri kullan.
- Bağlam dışında bilgi ekleme.
- Tahmin yürütme.
- Eğer cevap bağlamda yoksa:
  "Bu bilgi dokümanda bulunamadı." yaz.
- Cevabı kısa ve net ver.
- Cevabı yalnızca Türkçe ver.

BAĞLAM:
{context}

SORU:
{question}
"""

    answer = call_llama(prompt)

    print("\nCevap:\n")
    print(answer)
