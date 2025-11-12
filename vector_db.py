from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct  


class QdrantStorage:
    # inicializa la conexión con el servidor de qdrant y crea una colección si no existe
    def __init__(self, url="http://127.0.0.1:6333", collection="docs", dim=3072):
        self.client = QdrantClient(url=url, timeout=30)  # cliente de conexión a qdrant
        self.collection = collection  # nombre de la colección donde se almacenarán los vectores
        # verifica si la colección existe, y si no, la crea con el tamaño y tipo de distancia especificados
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

    # inserta o actualiza puntos en la colección de qdrant
    def upsert(self, ids, vectors, payloads):
        # combina los ids, vectores y datos adicionales en una lista de estructuras PointStruct
        points = [PointStruct(id=ids[i], vector=vectors[i], payload=payloads[i]) for i in range(len(ids))]
        self.client.upsert(self.collection, points=points)  # realiza la operación de inserción o actualización

    # realiza una búsqueda en la colección utilizando un vector de consulta
    def search(self, query_vector, top_k: int = 5):
        results = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            with_payload=True,
            limit=top_k
        )
        contexts = []  # lista para guardar los fragmentos de texto encontrados
        sources = set()  # conjunto para almacenar las fuentes únicas

        # recorre los resultados y extrae los textos y sus fuentes
        for r in results:
            payload = getattr(r, "payload", None) or {}
            text = payload.get("text", "")
            source = payload.get("source", "")
            if text:
                contexts.append(text)
                sources.add(source)

        # devuelve los fragmentos de texto relevantes y las fuentes asociadas
        return {"contexts": contexts, "sources": list(sources)}
