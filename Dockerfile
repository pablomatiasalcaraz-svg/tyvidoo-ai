# 1. Usamos un sistema Linux ligero con Python puro
FROM python:3.11-slim

# 2. Instalamos el motor de vídeo (FFmpeg) a la fuerza y sin hacer preguntas
RUN apt-get update && apt-get install -y ffmpeg

# 3. Preparamos el entorno de trabajo
WORKDIR /app

# 4. Instalamos las librerías de tu requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiamos tu código fuente (tyvidoo.py, etc.)
COPY . .

# 6. Arrancamos la aplicación leyendo el puerto dinámico de Railway
CMD ["streamlit", "run", "tyvidoo.py", "--server.port=8501", "--server.address=0.0.0.0"]
