import multiprocessing
import os

# Configuración del servidor
bind = "0.0.0.0:8000"  # Escucha en todas las interfaces
backlog = 2048

# Workers
workers = int(os.getenv("WORKERS", "4"))

# Worker class para FastAPI
worker_class = "uvicorn.workers.UvicornWorker"

# Threads por worker (opcional, para I/O-bound tasks)
threads = 1

# Timeout
timeout = 120  # segundos (importante para embeddings/LLM que pueden tardar)
keepalive = 5

# Logs
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = "info"

# Process naming
proc_name = "rag-python"

# Preload app (carga la app antes de hacer fork, ahorra memoria)
preload_app = True

# Graceful timeout
graceful_timeout = 30

# Reinicio automático de workers
max_requests = 1000  # Reinicia worker después de 1000 requests
max_requests_jitter = 50  # Añade aleatoriedad para evitar reinicio simultáneo

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190