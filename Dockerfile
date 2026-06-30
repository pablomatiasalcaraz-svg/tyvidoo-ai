FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD streamlit run tyvidoo.py --server.port $PORT --server.address 0.0.0.0
