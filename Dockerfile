FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema — ffmpeg para el remux/HLS de videos subidos
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copiar y instalar requerimientos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar aplicación
COPY . .

# Crear directorios necesarios
RUN mkdir -p /app/media /app/data

EXPOSE 8001

# Comando para ejecutar
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
