import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
from rag_core import RAGEngine

app = FastAPI(title="Local RAG (Ollama + FAISS + MPS)")

engine = RAGEngine()
DEFAULT_PDF = os.getenv("RAG_PDF", "ornek.pdf")

# --------------------------------------------------
# 🚀 Sunucu Başlarken Default PDF Yükle
# --------------------------------------------------
if os.path.exists(DEFAULT_PDF):
    print("Default PDF yükleniyor...")
    engine.build_from_pdf(DEFAULT_PDF)
    print("Yüklendi. Chunk:", len(engine.chunks))


# --------------------------------------------------
# 📄 PDF Upload
# --------------------------------------------------
@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):

    try:
        name = f"uploaded_{uuid.uuid4().hex}.pdf"
        path = os.path.join(os.getcwd(), name)

        content = await file.read()
        with open(path, "wb") as f:
            f.write(content)

        engine.build_from_pdf(path)

        return {
            "ok": True,
            "pdf_path": path,
            "chunks": len(engine.chunks)
        }

    except Exception as e:
        return JSONResponse(
            {"error": f"Upload hatası: {str(e)}"},
            status_code=500
        )


# --------------------------------------------------
# ❓ Normal Ask
# --------------------------------------------------

@app.post("/ask")
async def ask(
    question: str = Form(...),top_k: int = Form(6)):


    if engine.index is None:

        return JSONResponse(
            {"error": "Henüz PDF yüklenmedi."},
            status_code=400
        )

    try:
        out = engine.ask(question,top_k=top_k)

        return {
        "answer": out["cevap"],
        "sources": out.get("kaynaklar", [])
        }


    except Exception as e:
        return JSONResponse(
            {"error": f"Ollama hatası: {str(e)}"},
            status_code=500
        )


# --------------------------------------------------
# ⚡ Streaming Ask
# --------------------------------------------------
@app.post("/ask-stream")
async def ask_stream(question: str = Form(...),top_k: int = Form(6)):

    if not engine.index:
        return JSONResponse(
            {"error": "Henüz PDF yüklenmedi."},
            status_code=400
        )

    def event_gen():
        try:
            for token in engine.ask_stream(question,top_k=top_k):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream"
    )
