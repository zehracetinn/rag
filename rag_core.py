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
MODEL_NAME = os.getenv("OLLAMA_MODEL", "llama3-tr")

SUMMARY_KEYWORDS = [
    "ana konu",
    "özet",
    "genel",
    "tamamı",
    "ne anlatıyor",
    "konusu",
    "genel olarak",
]

MAX_CONTEXT_CHARS = 2000
MAX_SUMMARY_CONTEXT_CHARS = 3200
MAX_TOKENS_QA = 300
MAX_TOKENS_SUMMARY = 700
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
            chunks.append({"doc_id": doc_id, "chunk_id": chunk_id, "text": piece})

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
            div = (
                max([float(np.dot(doc_vecs[idx], doc_vecs[s])) for s in selected])
                if selected
                else 0.0
            )
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
    def __init__(
        self,
        embedding_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    ):
        device = (
            "mps"
            if torch.backends.mps.is_available()
            else "cuda" if torch.cuda.is_available() else "cpu"
        )

        print(f"Embedding modeli yükleniyor ({device})...")
        self.embed_model = SentenceTransformer(embedding_model, device=device)

        self.chunks = []
        self.doc_embeddings = None
        self.index = None

    def reset(self):
        self.chunks = []
        self.doc_embeddings = None
        self.index = None

    def _is_summary_question(self, question: str) -> bool:
        q = question.lower()
        return any(key in q for key in SUMMARY_KEYWORDS)

    def ask_stream(self, question: str, top_k: int = 6, doc_id: str | None = None):
        context, _sources = self._hybrid_context(question, top_k=top_k, doc_id=doc_id)
        prompt = self._build_prompt(context, question)
        is_summary = self._is_summary_question(question)

        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": True,
            "options": {
                "num_predict": MAX_TOKENS_SUMMARY if is_summary else MAX_TOKENS_QA,
                "temperature": 0.0,
                "top_p": 0.8,
                "repeat_penalty": 1.1,
            },
        }

        try:
            with requests.post(
                OLLAMA_URL,
                json=payload,
                stream=True,
                timeout=REQUEST_TIMEOUT,
            ) as r:
                r.raise_for_status()

                for line in r.iter_lines():
                    if not line:
                        continue

                    try:
                        decoded = line.decode("utf-8").strip()
                        if not decoded:
                            continue

                        data = json.loads(decoded)

                        if "response" in data:
                            yield data["response"]

                        if data.get("done", False):
                            break

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            yield f"[ERROR] {str(e)}"

    # --------------------------------------------------
    def build_from_pdf(self, pdf_path: str, doc_id: str | None = None):
        if not os.path.exists(pdf_path):
            raise RuntimeError(f"{pdf_path} bulunamadı.")

        text = read_pdf(pdf_path)
        resolved_doc_id = doc_id or os.path.basename(pdf_path)

        new_chunks = chunk_text(text, resolved_doc_id)

        if not new_chunks:
            raise RuntimeError("PDF içeriği boş.")

        texts = [c["text"] for c in new_chunks]

        emb = self.embed_model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype("float32")

        if self.index is None:
            dim = emb.shape[1]
            self.index = faiss.IndexFlatIP(dim)
            self.doc_embeddings = emb
        else:
            self.doc_embeddings = np.vstack([self.doc_embeddings, emb])

        self.index.add(emb)
        self.chunks.extend(new_chunks)

        print(f"{resolved_doc_id} yüklendi. Toplam chunk: {len(self.chunks)}")

    # --------------------------------------------------
    def _hybrid_context(self, question: str, top_k: int = 6, doc_id: str | None = None):
        if self.index is None or self.doc_embeddings is None or len(self.chunks) == 0:
            raise RuntimeError("Önce PDF yüklemelisiniz.")

        query_vec = self.embed_model.encode(
            [question],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype("float32")[0]

        summary_mode = self._is_summary_question(question)

        search_k = min(len(self.chunks), max(top_k, 24 if summary_mode else 12))
        scores, indices = self.index.search(np.array([query_vec]), k=search_k)
        candidate_pairs = [
            (int(idx), float(score))
            for idx, score in zip(indices[0], scores[0])
            if int(idx) >= 0
        ]
        candidates = [idx for idx, _ in candidate_pairs]

        if doc_id:
            filtered = [idx for idx in candidates if self.chunks[idx]["doc_id"] == doc_id]
            if filtered:
                candidates = filtered

        if not candidates:
            raise RuntimeError("Uygun bağlam bulunamadı.")

        if summary_mode:
            # Ozet sorularinda birincil dokumana odaklanarak daha tutarli baglam olustur.
            primary_doc = self.chunks[candidates[0]]["doc_id"]
            primary_doc_indices = [
                idx for idx, _ in candidate_pairs if self.chunks[idx]["doc_id"] == primary_doc
            ]

            selected_indices = primary_doc_indices[: min(8, len(primary_doc_indices))]
            if len(selected_indices) < 8:
                for idx, _ in candidate_pairs:
                    if idx not in selected_indices:
                        selected_indices.append(idx)
                    if len(selected_indices) >= 12:
                        break

            max_chars = MAX_SUMMARY_CONTEXT_CHARS
        else:
            selected_indices = mmr_select(
                query_vec,
                self.doc_embeddings,
                candidates,
                k=min(top_k, len(candidates)),
            )
            max_chars = MAX_CONTEXT_CHARS

        selected_chunks = [self.chunks[i] for i in selected_indices]
        if summary_mode:
            selected_chunks = sorted(selected_chunks, key=lambda c: (c["doc_id"], c["chunk_id"]))

        context_parts = []
        total = 0
        for c in selected_chunks:
            t = c["text"]
            if total + len(t) > max_chars:
                break
            context_parts.append(t)
            total += len(t)

        context = "\n\n".join(context_parts)
        sources = [{"dosya": c["doc_id"], "parca": c["chunk_id"]} for c in selected_chunks]

        return context, sources

    # --------------------------------------------------
    def _build_prompt(self, context: str, question: str):
        if self._is_summary_question(question):
            instruction = (
                "Bu bir ozet sorusu. Cevabi 4-5 tam cumlelik tek paragraf halinde yaz. "
                "Her cumle net, tamamlanmis ve ozne-yuklem icersin. Liste, kod, anahtar kelime yigini "
                "ve kesik ifade kullanma. Ilk cumlede ana konuyu, sonraki cumlelerde onemli noktalarin "
                "neden onemli oldugunu acikla. Metni oldugu gibi kopyalama; 8 kelimeden uzun dogrudan "
                "alinti yapma. Baglamda olmayan bilgi ekleme."
            )
        else:
            instruction = (
                "Soruya yalnızca bağlamdan cevap ver. Bağlamda yoksa sadece 'Bu bilgi dokümanda bulunamadı.' yaz."
            )

        return f"""Sen bir doküman soru-cevap asistanısın.

Kurallar:
1) Sadece BAĞLAM içindeki bilgileri kullan.
2) BAĞLAM dışında bilgi ekleme.
3) Cevabı Türkçe, kısa ve net ver.
4) {instruction}

BAĞLAM:
{context}

SORU:
{question}

CEVAP:
""".strip()

    # --------------------------------------------------
    def ask(self, question: str, top_k: int = 6, doc_id: str | None = None):
        context, sources = self._hybrid_context(question, top_k=top_k, doc_id=doc_id)
        prompt = self._build_prompt(context, question)
        is_summary = self._is_summary_question(question)

        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": MAX_TOKENS_SUMMARY if is_summary else MAX_TOKENS_QA,
                "temperature": 0.0,
                "top_p": 0.8,
                "repeat_penalty": 1.1,
            },
        }

        try:
            r = requests.post(
                OLLAMA_URL,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()

            answer = r.json().get("response", "").strip()

            return {"cevap": answer, "kaynaklar": sources}

        except Exception as e:
            return {"hata": str(e)}


# --------------------------------------------------
# TEST
# --------------------------------------------------
if __name__ == "__main__":
    rag = RAGEngine()
    rag.build_from_pdf("ornek.pdf")
    result = rag.ask("Bu dokümanın ana konusu nedir?")

    print("\nCEVAP:\n", result["cevap"])
    print("\nKAYNAKLAR:\n", result["kaynaklar"])
