# 1. Bajar un sistema Linux limpio con Python
FROM python:3.11-slim

# 2. INSTALAR FFMPEG A LA FUERZA SIN EXCUSAS
RUN apt-get update && apt-get install -y ffmpeg

# 3. Crear la carpeta de trabajo
WORKDIR /app

# 4. Copiar e instalar las librerías
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar tu código
COPY . .

# 6. Arrancar la aplicación en el puerto correcto
EXPOSE 8080
CMD ["streamlit", "run", "tyvidoo.py", "--server.port=8080", "--server.address=0.0.0.0"]
