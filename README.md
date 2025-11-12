# Docker

Qdrant:

```docker
docker run -d --name qdrant -p 6333:6333 -v "...:/qdrant/storage" qdrant/qdrant
```

# Uvicorn

```bash
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

```bash
uv run uvicorn main:app --reload
```

# REST API

![](docs/images/rest1.png)

![](docs/images/rest2.png)
