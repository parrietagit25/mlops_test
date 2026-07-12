FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# bash: requerido por scripts/run_*.sh invocados desde el eval runner (UI-0B).
# curl: utilidad de diagnóstico ligera. Node no se instala aquí: suites
# promptfoo/security que dependen de npx fallarán con mensaje claro si
# Node no está en el contenedor (aceptable en Fase 1 Local).
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]
