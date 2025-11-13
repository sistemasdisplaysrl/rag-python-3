from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class QdrantStorage:
    def __init__(self, url="http://127.0.0.1:6333", collection="docs", dim=3072):
        self.client = QdrantClient(url=url, timeout=30)
        self.collection = collection
        
        # Crear colección si no existe
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
            logger.info(f"Colección '{self.collection}' creada")

    def upsert(self, ids: List[str], vectors: List[List[float]], payloads: List[Dict]):
        """Inserta o actualiza puntos en la colección"""
        points = [
            PointStruct(id=ids[i], vector=vectors[i], payload=payloads[i]) 
            for i in range(len(ids))
        ]
        self.client.upsert(self.collection, points=points)
        logger.info(f"Upsert de {len(points)} puntos completado")

    def delete_document(self, doc_id: str) -> int:
        """
        Elimina físicamente todos los puntos de un documento
        Retorna la cantidad de puntos eliminados
        """
        # Obtener IDs de los puntos a eliminar
        scroll_result = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
            limit=10000,  # Ajustar según necesidad
            with_payload=False,
            with_vectors=False
        )
        
        points_to_delete = scroll_result[0]
        
        if not points_to_delete:
            logger.warning(f"No se encontraron puntos para doc_id: {doc_id}")
            return 0
        
        point_ids = [p.id for p in points_to_delete]
        
        # Eliminar puntos
        self.client.delete(
            collection_name=self.collection,
            points_selector=point_ids
        )
        
        count = len(point_ids)
        logger.info(f"Eliminados {count} puntos del documento {doc_id}")
        return count

    def search(
        self, 
        query_vector: List[float], 
        top_k: int = 5,
        area: Optional[str] = None,
        doc_id: Optional[str] = None
    ) -> Dict:
        """
        Búsqueda vectorial con filtros opcionales
        
        Args:
            query_vector: Vector de la consulta
            top_k: Número de resultados
            area: Filtrar por área (rrhh, marketing, etc.)
            doc_id: Filtrar por documento específico
        """
        # Construir filtros
        filter_conditions = []
        
        if area:
            filter_conditions.append(
                FieldCondition(key="area", match=MatchValue(value=area))
            )
        
        if doc_id:
            filter_conditions.append(
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id))
            )
        
        # Aplicar filtros si existen
        query_filter = Filter(must=filter_conditions) if filter_conditions else None
        
        # Realizar búsqueda
        results = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            query_filter=query_filter,
            with_payload=True,
            limit=top_k
        )
        
        contexts = []
        sources = set()
        doc_ids = set()
        
        for r in results:
            payload = getattr(r, "payload", None) or {}
            text = payload.get("text", "")
            source = payload.get("source", "")
            doc_id_val = payload.get("doc_id", "")
            
            if text:
                contexts.append(text)
                if source:
                    sources.add(source)
                if doc_id_val:
                    doc_ids.add(doc_id_val)
        
        return {
            "contexts": contexts,
            "sources": list(sources),
            "doc_ids": list(doc_ids)
        }

    def get_document_info(self, doc_id: str) -> Optional[Dict]:
        """Obtiene información de un documento"""
        scroll_result = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False
        )
        
        if scroll_result[0]:
            point = scroll_result[0][0]
            payload = getattr(point, "payload", {})
            return {
                "doc_id": payload.get("doc_id"),
                "area": payload.get("area"),
                "source": payload.get("source"),
                "doc_version": payload.get("doc_version"),
                "upload_date": payload.get("upload_date"),
                "status": payload.get("status", "active")
            }
        return None
    
    def list_documents(self, area: Optional[str] = None) -> List[Dict]:
        """
        Lista todos los documentos únicos en la colección
        Opcionalmente filtrados por área
        """
        filter_conditions = []
        if area:
            filter_conditions.append(
                FieldCondition(key="area", match=MatchValue(value=area))
            )
        
        query_filter = Filter(must=filter_conditions) if filter_conditions else None
        
        # Scroll para obtener todos los documentos
        scroll_result = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=query_filter,
            limit=10000,
            with_payload=True,
            with_vectors=False
        )
        
        # Agrupar por doc_id para obtener documentos únicos
        docs_dict = {}
        for point in scroll_result[0]:
            payload = getattr(point, "payload", {})
            doc_id = payload.get("doc_id")
            
            if doc_id and doc_id not in docs_dict:
                docs_dict[doc_id] = {
                    "doc_id": doc_id,
                    "area": payload.get("area"),
                    "source": payload.get("source"),
                    "doc_version": payload.get("doc_version"),
                    "upload_date": payload.get("upload_date")
                }
        
        return list(docs_dict.values())