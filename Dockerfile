# Copiloto do merchandiser (MCP, Streamable HTTP) para o Fly.io. Só o pacote copiloto/ e o que ele importa
# de ingest/; a loja (web/) vai para a Vercel. Modo público: sem login e só leitura (ver copiloto/__main__.py).
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

# dependências primeiro, para o cache da camada sobreviver a mudança de código
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY ingest ./ingest
COPY copiloto ./copiloto

ENV COPILOTO_PUBLICO=1
EXPOSE 8080
CMD ["uv", "run", "--frozen", "--no-dev", "--no-sync", "python", "-m", "copiloto", "--http", "8080"]
