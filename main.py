import logging
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
import uuid
import os
import datetime 
from openai import OpenAI

# tipos personalizados
from data_loader import load_and_chunk_pdf, embed_texts
from vector_db import QdrantStorage
from custom_types import RAQQueryResult, RAGSearchResult, RAGUpsertResult, RAGChunkAndSrc

load_dotenv()

app = FastAPI()
logger = logging.getLogger("uvicorn")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.post("/ingest-pdf")
async def rag_ingest_pdf(pdf_path: str, source_id: str = None):
    """
    Endpoint para ingestar y procesar un PDF
    """
    try:
        # Cargar y chunk el PDF
        if source_id is None:
            source_id = pdf_path
            
        chunks = load_and_chunk_pdf(pdf_path)
        
        # Embed y upsert en la base vectorial
        vecs = embed_texts(chunks)
        ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}:{i}")) for i in range(len(chunks))]
        payloads = [{"source": source_id, "text": chunks[i]} for i in range(len(chunks))]
        
        QdrantStorage().upsert(ids, vecs, payloads)
        
        return {"ingested": len(chunks), "source_id": source_id}
        
    except Exception as e:
        logger.error(f"Error ingesting PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

@app.post("/query-pdf")
async def rag_query_pdf_ai(question: str, top_k: int = 5):
    """
    Endpoint para consultar los PDFs ingeridos usando RAG
    """
    try:
        # Buscar contextos relevantes
        query_vec = embed_texts([question])[0]
        store = QdrantStorage()
        found = store.search(query_vec, top_k)
        
        # Construir contexto para el LLM
        context_block = "\n\n".join(f"- {c}" for c in found["contexts"])
        user_content = (
            "Use the following context to answer the question.\n\n"
            f"Context:\n{context_block}\n\n"
            f"Question: {question}\n"
            "Answer concisely using the context above."
        )

        # Llamar a OpenAI directamente
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You answer questions using only the provided context."},
                {"role": "user", "content": user_content}
            ],
            max_tokens=1024,
            temperature=0.2
        )

        answer = response.choices[0].message.content.strip()
        
        return {
            "answer": answer, 
            "sources": found["sources"], 
            "num_contexts": len(found["contexts"])
        }
        
    except Exception as e:
        logger.error(f"Error querying PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error querying PDF: {str(e)}")