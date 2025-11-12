# se importa pydantic para crear modelos de datos con validación automática
import pydantic

# lista de fragmentos de texto (por ejemplo, trozos de un documento)
class RAGChunkAndSrc(pydantic.BaseModel):
    chunks: list[str]
    source_id: str = None

# cantidad de elementos o fragmentos que fueron procesados o insertados
class RAGUpsertResult(pydantic.BaseModel):
    ingested: int

# lista de textos o fragmentos relevantes encontrados en la búsqueda
class RAGSearchResult(pydantic.BaseModel):
    contexts: list[str]
    sources: list[str]

# la respuesta generada a partir de los contextos encontrados
# lista de fuentes que respaldan la respuesta
 # número de contextos o fragmentos usados para generar la respuesta
class RAQQueryResult(pydantic.BaseModel):
    answer: str
    sources: list[str]
    num_contexts: int