import os
import json
import numpy as np
import faiss
import requests
import torch
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = os.getenv("OLLAMA_MODEL", "llama3-tr")  # Türkçe için önerilir

SUMMARY_KEYWORDS = [
    "ana konu", "özet", "genel", "tamamı",
    "ne anlatıyor", "konusu", "genel olarak"
]

MAX_CONTEXT_CHARS = 2000
MAX_TOKENS = 300
REQUEST_TIMEOUT = 120


# --------------------------------------------------
# PDF OKUMA
# --------------------------------------------------

def read_pdf(path: str) -> str:
    try:
        reader = PdfReader(path)
        text = ""
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
        return text.strip()
    except Exception as e:
        raise RuntimeError(f"PDF okunurken hata oluştu: {e}")


# --------------------------------------------------
# CHUNKING
# --------------------------------------------------

def chunk_text(text: str, doc_id: str, chunk_size: int = 800, overlap: int = 150):
    chunks = []
    start = 0
    chunk_id = 0

    while start < len(text):
        end = start + chunk_size
        piece = text[start:end].strip()

        if piece:
            chunks.append({
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "text": piece
            })

        start = end - overlap
        chunk_id += 1

    return chunks


# --------------------------------------------------
# MMR (DIVERSITY SELECTION)
# --------------------------------------------------

def mmr_select(query_vec, doc_vecs, candidates, k=3, lam=0.65):
    selected = []

    while candidates and len(selected) < k:
        best = None
        best_score = -1e9

        for idx in candidates:
            rel = float(np.dot(query_vec, doc_vecs[idx]))
            div = max([float(np.dot(doc_vecs[idx], doc_vecs[s])) for s in selected]) if selected else 0.0
            score = lam * rel - (1 - lam) * div

            if score > best_score:
                best_score = score
                best = idx

        selected.append(best)
        candidates.remove(best)

    return selected


# --------------------------------------------------
# RAG ENGINE
# --------------------------------------------------

class RAGEngine:

    def __init__(self, embedding_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):

        device = (
            "mps" if torch.backends.mps.is_available()
            else "cuda" if torch.cuda.is_available()
            else "cpu"
        )

        print(f"Embedding modeli yükleniyor ({device})...")
        self.embed_model = SentenceTransformer(embedding_model, device=device)

        self.chunks = []
        self.doc_embeddings = None
        self.index = None




    def ask_stream(self, question: str, top_k: int = 6):

        context, sources = self._hybrid_context(question, top_k=top_k)
        prompt = self._build_prompt(context, question)

        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": True,
            "options": {
                "num_predict": MAX_TOKENS,
                "temperature": 0.2,
                "top_p": 0.9,
                "repeat_penalty": 1.1
            }
        }

        with requests.post(
            OLLAMA_URL,
            json=payload,
            stream=True,
            timeout=REQUEST_TIMEOUT
        ) as r:

            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]
                except:
                    continue





        


    # --------------------------------------------------

    def build_from_pdf(self, pdf_path: str):

        if not os.path.exists(pdf_path):
            raise RuntimeError(f"{pdf_path} bulunamadı.")

        text = read_pdf(pdf_path)
        doc_id = os.path.basename(pdf_path)

        new_chunks = chunk_text(text, doc_id)

        if not new_chunks:
            raise RuntimeError("PDF içeriği boş.")

        texts = [c["text"] for c in new_chunks]

        emb = self.embed_model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True
        ).astype("float32")

        if self.index is None:
            dim = emb.shape[1]
            self.index = faiss.IndexFlatIP(dim)
            self.doc_embeddings = emb
        else:
            self.doc_embeddings = np.vstack([self.doc_embeddings, emb])

        self.index.add(emb)
        self.chunks.extend(new_chunks)

        print(f"{doc_id} yüklendi. Toplam chunk: {len(self.chunks)}")


    # --------------------------------------------------

    def _hybrid_context(self, question: str, top_k: int = 6):

        if self.index is None or self.doc_embeddings is None or len(self.chunks) == 0:
            raise RuntimeError("Önce PDF yüklemelisiniz.")

        q_lower = question.lower()

        query_vec = self.embed_model.encode(
            [question],
            convert_to_numpy=True,
            normalize_embeddings=True
        ).astype("float32")[0]

        # SUMMARY MODE
        if any(key in q_lower for key in SUMMARY_KEYWORDS):
            selected_indices = list(range(0, min(len(self.chunks), 5)))
        else:
            _, indices = self.index.search(np.array([query_vec]), k=top_k)
            candidates = list(map(int, indices[0]))
            selected_indices = mmr_select(query_vec, self.doc_embeddings, candidates, k=3)

        selected_chunks = [self.chunks[i] for i in selected_indices]

        context = "\n\n".join(c["text"] for c in selected_chunks)

        # güvenli kesme (kelime sınırı)
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS].rsplit(" ", 1)[0]

        sources = [
            {"dosya": c["doc_id"], "parca": c["chunk_id"]}
            for c in selected_chunks
        ]

        return context, sources


    # --------------------------------------------------

    def _build_prompt(self, context: str, question: str):

        return f"""
Sen bir yapay zeka doküman analiz sistemisin.

KURALLAR:
- Sadece verilen bağlamı kullan.
- Bağlamda cevap yoksa: "Bu bilgi dokümanda yer almıyor." yaz.
- Tahmin yürütme.
- Cevap kısa, net ve Türkçe olsun.

BAĞLAM:
{context}

SORU:
{question}
""".strip()


    # --------------------------------------------------

    def ask(self, question: str, top_k: int = 6):

        context, sources = self._hybrid_context(question,top_k=top_k)
        prompt = self._build_prompt(context, question)

        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": MAX_TOKENS,
                "temperature": 0.2,
                "top_p": 0.9,
                "repeat_penalty": 1.1
            }
        }

        try:
            r = requests.post(
                OLLAMA_URL,
                json=payload,
                timeout=REQUEST_TIMEOUT
            )
            r.raise_for_status()

            answer = r.json().get("response", "").strip()

            return {
                "cevap": answer,
                "kaynaklar": sources
            }

        except Exception as e:
            return {"hata": str(e)}


# --------------------------------------------------
# TEST
# --------------------------------------------------

if __name__ == "__main__":

    rag = RAGEngine()

    # PDF yükle
    rag.build_from_pdf("ornek.pdf")

    # Soru sor
    result = rag.ask("Bu dokümanın ana konusu nedir?")

    print("\nCEVAP:\n", result["cevap"])
    print("\nKAYNAKLAR:\n", result["kaynaklar"])
