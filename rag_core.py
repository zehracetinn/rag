import json
import os
import re

import faiss
import numpy as np
import requests
import torch
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
HF_URL = "https://router.huggingface.co/v1/chat/completions"
HF_TOKEN = os.getenv("HF_TOKEN")

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


def call_llm(prompt: str, max_tokens: int = 300, temperature: float = 0.2) -> str:
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN tanımlı değil. Ortam değişkeni olarak ayarlayın.")

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "mistralai/Mistral-7B-Instruct-v0.2:hf-inference",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    try:
        r = requests.post(
            HF_URL,
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"HuggingFace API isteği başarısız: {e}") from e

    try:
        data = r.json()
    except ValueError as e:
        raise RuntimeError("HuggingFace API geçersiz JSON döndürdü.") from e

    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise RuntimeError("HuggingFace API yanıt formatı beklenen yapıda değil.") from e


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

    def _normalize_ws(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def _ensure_sentence(self, text: str) -> str:
        t = self._normalize_ws(text).strip(" '\"`")
        if not t:
            return ""
        if t[-1] not in ".!?":
            t += "."
        return t

    def _extract_json_obj(self, text: str):
        raw = (text or "").strip()
        if not raw:
            return None

        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass

        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return None

        try:
            obj = json.loads(match.group(0))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    def _postprocess_summary(self, raw_answer: str) -> str:
        obj = self._extract_json_obj(raw_answer)
        if obj:
            keys = ["ana_konu", "nokta1", "nokta2", "nokta3", "sonuc"]
            sentences = [self._ensure_sentence(str(obj.get(k, ""))) for k in keys]
            sentences = [s for s in sentences if s]
            if len(sentences) >= 5:
                return " ".join(sentences[:5])

        cleaned = raw_answer or ""
        cleaned = re.sub(r"\b\d+\)\s*", " ", cleaned)
        cleaned = re.sub(r"\b\d+\.\s*", " ", cleaned)
        cleaned = self._normalize_ws(cleaned)

        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", cleaned) if p.strip()]
        banned = ("doküman soru-cevap asistanı", "kurallar", "bağlam", "soru", "json")
        parts = [p for p in parts if not any(b in p.lower() for b in banned)]
        parts = [self._ensure_sentence(p) for p in parts if self._ensure_sentence(p)]

        if len(parts) >= 5:
            return " ".join(parts[:5])
        if parts:
            return " ".join(parts)
        return "Bu bilgi dokümanda bulunamadı."

    def _build_summary_prompt(self, context: str, question: str) -> str:
        return f"""Sen yalnızca verilen bağlama göre özet çıkaran bir asistansın.

YALNIZCA GEÇERLİ JSON DÖNDÜR. JSON dışına tek karakter bile yazma.

JSON şeması:
{{
  "ana_konu": "Tek net cümle",
  "nokta1": "Birinci önemli nokta cümlesi",
  "nokta2": "İkinci önemli nokta cümlesi",
  "nokta3": "Üçüncü önemli nokta cümlesi",
  "sonuc": "Kısa genel sonuç cümlesi"
}}

Kurallar:
- Tam olarak 1+3+1 yapısı kullan (toplam 5 cümlelik içerik).
- Her alan tek, tamamlanmış ve Türkçe bir cümle olsun.
- Metni aynen kopyalama, uzun alıntı yapma.
- Bağlam dışı bilgi ekleme.

BAĞLAM:
{context}

SORU:
{question}

JSON:
""".strip()

    def ask_stream(self, question: str, top_k: int = 6, doc_id: str | None = None):
        result = self.ask(question, top_k=top_k, doc_id=doc_id)
        if "hata" in result:
            yield f"[ERROR] {result['hata']}"
            return
        yield result["cevap"]

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

        search_k = (
            min(len(self.chunks), max(16, top_k * 4))
            if summary_mode
            else min(len(self.chunks), max(12, top_k * 2))
        )
        scores, indices = self.index.search(np.array([query_vec]), k=search_k)
        candidate_pairs = [
            (int(idx), float(score))
            for idx, score in zip(indices[0], scores[0])
            if int(idx) >= 0
        ]
        candidates = [idx for idx, _ in candidate_pairs]

        if doc_id:
            candidates = [idx for idx in candidates if self.chunks[idx]["doc_id"] == doc_id]
            if not candidates:
                raise RuntimeError(f"Secili dokuman icin uygun baglam bulunamadi: {doc_id}")

        if not candidates:
            raise RuntimeError("Uygun bağlam bulunamadı.")

        if summary_mode:
            summary_k = min(len(candidates), max(1, top_k))
            selected_indices = mmr_select(
                query_vec,
                self.doc_embeddings,
                candidates.copy(),
                k=summary_k,
                lam=0.82,
            )
            max_chars = min(12000, max(MAX_SUMMARY_CONTEXT_CHARS, summary_k * 900))
        else:
            selected_indices = mmr_select(
                query_vec,
                self.doc_embeddings,
                candidates,
                k=min(top_k, len(candidates)),
            )
            max_chars = MAX_CONTEXT_CHARS

        selected_chunks = [self.chunks[i] for i in selected_indices]

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
            return self._build_summary_prompt(context, question)

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
        try:
            context, sources = self._hybrid_context(question, top_k=top_k, doc_id=doc_id)
            prompt = self._build_prompt(context, question)
            is_summary = self._is_summary_question(question)

            answer = call_llm(
                prompt,
                max_tokens=MAX_TOKENS_SUMMARY if is_summary else MAX_TOKENS_QA,
                temperature=0.15 if is_summary else 0.0,
            )

            if is_summary:
                answer = self._postprocess_summary(answer)

            return {"cevap": answer.strip(), "kaynaklar": sources}
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
