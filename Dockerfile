FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Instala as dependências antes de copiar o código: mudar o código não reinstala tudo.
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" > /tmp/dependencias.txt \
    && pip install -r /tmp/dependencias.txt \
    && rm /tmp/dependencias.txt

COPY app ./app

# Roda sem permissão de administrador. A pasta "dados" guarda o SQLite quando não há PostgreSQL.
RUN useradd --create-home --uid 10001 triagem \
    && mkdir /app/dados \
    && chown triagem /app/dados
USER triagem

ENV DATABASE_URL=sqlite:////app/dados/triagem.db
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/saude', timeout=3)"

# A porta vem da variável PORT quando a hospedagem define uma (Railway, Render).
# Os cabeçalhos do proxy dão o endereço real de quem acessa, usado no limite da demonstração.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
