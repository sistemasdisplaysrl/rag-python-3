from pydantic import BaseModel
from typing import Optional, List, Dict


class IngestRequest(BaseModel):
    """Request para ingestar un PDF"""
    pdf_path: str
    doc_id: str  # ID único del documento
    area: str  # área: rrhh, marketing, almacenes, etc.
    doc_version: str = "1.0"
    author: Optional[str] = None
    category: Optional[str] = None
    replace_existing: bool = True  # Si True, elimina versión anterior


class QueryRequest(BaseModel):
    """Request para consultar documentos"""
    question: str
    area: Optional[str] = None  # Filtrar por área
    doc_id: Optional[str] = None  # Filtrar por documento específico
    top_k: int = 5


class IngestResponse(BaseModel):
    """Response de ingesta de documento"""
    success: bool
    ingested: int
    doc_id: str
    area: str
    doc_version: str
    deleted_previous: int  # chunks eliminados de versión anterior
    upload_date: str


class QueryResponse(BaseModel):
    """Response de consulta RAG"""
    answer: str
    sources: List[str]
    doc_ids: List[str]
    num_contexts: int
    filters_applied: Dict[str, Optional[str]]


class DeleteResponse(BaseModel):
    """Response de eliminación de documento"""
    success: bool
    doc_id: str
    chunks_affected: int


class DocumentInfo(BaseModel):
    """Información de un documento"""
    doc_id: str
    area: str
    source: str
    doc_version: str
    upload_date: str
    status: str