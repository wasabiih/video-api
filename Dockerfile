FROM python:3.9-slim

# Instalar dependencias del sistema
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar y instalar requerimientos primero (para cache de capas)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Variables de entorno
ENV PORT=8080

# Exponer el puerto
EXPOSE 8080

# Comando para ejecutar la aplicación
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
