FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    PROVIDER_CONFIG_MODE=environment \
    KNOWLEDGE_REPO=chenbinggang123/Cookie-s_Knowledge_Base \
    KNOWLEDGE_REF=main \
    KNOWLEDGE_VAULT_DIR=/tmp/plain-cookie-vault

WORKDIR /workspace

COPY experiments/wiki-vs-rag/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY experiments/wiki-vs-rag/raglab /workspace/experiments/wiki-vs-rag/raglab
COPY experiments/wiki-vs-rag/bootstrap.py /workspace/experiments/wiki-vs-rag/bootstrap.py
COPY experiments/wiki-vs-rag/server.py /workspace/experiments/wiki-vs-rag/server.py
COPY experiments/wiki-vs-rag/web /workspace/experiments/wiki-vs-rag/web
COPY experiments/wiki-vs-rag/game_scope.json /workspace/experiments/wiki-vs-rag/game_scope.json

WORKDIR /workspace/experiments/wiki-vs-rag

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/health', timeout=3)"

CMD ["python", "bootstrap.py"]
