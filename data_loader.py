# creación de los vectores
from openai import OpenAI
from llama_index.readers.file import PDFReader
from llama_index.core.node_parser import SentenceSplitter
from dotenv import load_dotenv

# cargar variables de entorno definidas en el archivo .env
load_dotenv()

# inicialización del cliente de OpenAI para el uso de modelos de lenguaje y embeddings
client = OpenAI()

# definición del modelo de embeddings y de la dimensión de los vectores resultantes
EMBED_MODEL = "text-embedding-3-large"
EMBED_DIM = 3072

# configuración del divisor de texto: fragmentos de hasta 1000 caracteres con una superposición de 200
splitter = SentenceSplitter(chunk_size=1000, chunk_overlap=200)


def load_and_chunk_pdf(path: str):
    # carga un archivo PDF desde la ruta indicada, extrae su contenido textual y lo divide en fragmentos adecuados para el procesamiento posterior.
    # lectura del archivo PDF y obtención del contenido textual
    docs = PDFReader().load_data(file=path)

    # extracción del texto de cada documento, si está disponible
    texts = [d.text for d in docs if getattr(d, "text", None)]

    chunks = []
    # división del texto en fragmentos utilizando el divisor configurado
    for t in texts:
        chunks.extend(splitter.split_text(t))

    # retorno de la lista de fragmentos resultantes
    return chunks


def embed_texts(texts: list[str]) -> list[list[float]]:
    # genera los embeddings correspondientes a una lista de fragmentos de texto utilizando el modelo de OpenAI especificado.
    # solicitud al modelo de OpenAI para generar embeddings del texto proporcionado
    response = client.embeddings.create(
        model=EMBED_MODEL,
        input=texts,
    )

    # extracción y retorno de los vectores de embeddings generados
    return [item.embedding for item in response.data]
