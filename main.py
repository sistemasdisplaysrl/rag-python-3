import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import uuid
import os
from datetime import datetime
from pathlib import Path
from openai import OpenAI

from data_loader import load_and_chunk_pdf, embed_texts
from vector_db import QdrantStorage

load_dotenv()

app = FastAPI()
logger = logging.getLogger("uvicorn")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# Modelos de request
class IngestRequest(BaseModel):
    pdf_path: str
    doc_id: str  # ID único del documento (ej: "doc_rrhh_001")
    area: str  # área: rrhh, marketing, almacenes, etc.
    doc_version: str = "1.0"
    author: str = None
    category: str = None
    replace_existing: bool = True  # Si es True, archiva la versión anterior


class QueryRequest(BaseModel):
    question: str
    area: str = None  # Opcional: filtrar por área
    doc_id: str = None  # Opcional: consultar documento específico
    top_k: int = 5


@app.post("/ingest-pdf")
async def rag_ingest_pdf(request: IngestRequest):
    """
    Ingesta un PDF con gestión de versiones
    Si replace_existing=True, archiva la versión anterior del documento
    """
    try:
        store = QdrantStorage()
        
        # 1. Construir la ruta completa del PDF usando pathlib
        pdf_full_path = Path("pdfs") / request.pdf_path
        
        # Verificar si el archivo existe antes de proceder
        if not pdf_full_path.exists():
            raise HTTPException(
                status_code=404, 
                detail=f"Archivo PDF no encontrado: {request.pdf_path} (buscado en: {pdf_full_path})"
            )
        
        if not pdf_full_path.is_file():
            raise HTTPException(
                status_code=400,
                detail=f"La ruta no es un archivo válido: {request.pdf_path}"
            )
        
        # 2. Si se debe reemplazar, eliminar versión anterior
        deleted_count = 0
        if request.replace_existing:
            deleted_count = store.delete_document(request.doc_id)
            logger.info(f"Eliminados {deleted_count} chunks del doc_id: {request.doc_id}")
        
        # 3. Cargar y chunk el PDF (convertir Path a string para compatibilidad)
        chunks = load_and_chunk_pdf(str(pdf_full_path))
        
        if not chunks:
            raise HTTPException(status_code=400, detail="No se pudieron extraer chunks del PDF")
        
        # 4. Generar embeddings
        vecs = embed_texts(chunks)
        
        # 5. Crear IDs únicos para cada chunk
        ids = [
            str(uuid.uuid5(uuid.NAMESPACE_URL, f"{request.doc_id}:v{request.doc_version}:{i}"))
            for i in range(len(chunks))
        ]
        
        # 6. Crear payloads enriquecidos con metadata
        upload_timestamp = datetime.now().isoformat()
        payloads = [
            {
                "text": chunks[i],
                "source": request.pdf_path,  # Guardamos solo el nombre del archivo
                "doc_id": request.doc_id,
                "area": request.area,
                "doc_version": request.doc_version,
                "upload_date": upload_timestamp,
                "status": "active",
                "chunk_index": i,
                "metadata": {
                    "author": request.author,
                    "category": request.category
                }
            }
            for i in range(len(chunks))
        ]
        
        # 7. Upsert en Qdrant
        store.upsert(ids, vecs, payloads)
        
        return {
            "success": True,
            "ingested": len(chunks),
            "doc_id": request.doc_id,
            "area": request.area,
            "doc_version": request.doc_version,
            "deleted_previous": deleted_count if request.replace_existing else 0,
            "upload_date": upload_timestamp
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ingesting PDF: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


@app.post("/query")
async def rag_query(request: QueryRequest):
    """
    Consulta documentos usando RAG con filtros opcionales
    """
    try:
        # 1. Generar embedding de la pregunta
        query_vec = embed_texts([request.question])[0]
        
        # 2. Buscar en Qdrant con filtros
        store = QdrantStorage()
        found = store.search(
            query_vector=query_vec,
            top_k=request.top_k,
            area=request.area,
            doc_id=request.doc_id
        )
        
        if not found["contexts"]:
            return {
                "answer": "No se encontró información relevante en los documentos disponibles.",
                "sources": [],
                "doc_ids": [],
                "num_contexts": 0
            }
        
        # 3. Construir contexto para el LLM
        context_block = "\n\n".join(f"- {c}" for c in found["contexts"])
        
        # Agregar información de filtros aplicados al prompt
        filter_info = []
        if request.area:
            filter_info.append(f"Área: {request.area}")
        if request.doc_id:
            filter_info.append(f"Documento: {request.doc_id}")
        
        filter_text = f" ({', '.join(filter_info)})" if filter_info else ""
        
        user_content = (
            f"Usa el siguiente contexto{filter_text} para responder la pregunta.\n\n"
            f"Contexto:\n{context_block}\n\n"
            f"Pregunta: {request.question}\n\n"
            "Responde de manera concisa usando únicamente el contexto proporcionado."
        )

        # 4. Llamar a OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": "Eres un asistente que responde preguntas basándose únicamente en el contexto proporcionado. Si la información no está en el contexto, indícalo claramente."
                },
                {"role": "user", "content": user_content}
            ],
            max_tokens=1024,
            temperature=0.2
        )

        answer = response.choices[0].message.content.strip()
        
        return {
            "answer": answer,
            "sources": found["sources"],
            "doc_ids": found.get("doc_ids", []),
            "num_contexts": len(found["contexts"]),
            "filters_applied": {
                "area": request.area,
                "doc_id": request.doc_id
            }
        }
        
    except Exception as e:
        logger.error(f"Error querying: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error querying: {str(e)}")


@app.delete("/document/{doc_id}")
async def delete_document(doc_id: str):
    """
    Elimina físicamente un documento y todos sus chunks
    """
    try:
        store = QdrantStorage()
        count = store.delete_document(doc_id)
        
        if count == 0:
            raise HTTPException(status_code=404, detail=f"Documento {doc_id} no encontrado")
        
        return {
            "success": True,
            "doc_id": doc_id,
            "chunks_affected": count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")


@app.get("/document/{doc_id}/info")
async def get_document_info(doc_id: str):
    """
    Obtiene información de un documento
    """
    try:
        store = QdrantStorage()
        info = store.get_document_info(doc_id)
        
        if not info:
            raise HTTPException(status_code=404, detail=f"Documento {doc_id} no encontrado")
        
        return info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/documents")
async def list_documents(area: str = None):
    """
    Lista todos los documentos en la base de datos
    Opcionalmente filtrados por área
    """
    try:
        store = QdrantStorage()
        documents = store.list_documents(area=area)
        
        return {
            "total": len(documents),
            "documents": documents,
            "filtered_by_area": area
        }
        
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")