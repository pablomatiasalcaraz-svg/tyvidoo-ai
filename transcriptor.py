import os
import time
from openai import OpenAI

# Conectamos con OpenAI automáticamente usando la variable de entorno de Railway
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def transcribir_audio(ruta_audio):
    print(f"🚀 Enviando audio a los superordenadores de OpenAI: {ruta_audio}...")
    inicio = time.time()
    
    with open(ruta_audio, "rb") as archivo_audio:
        # Aquí ocurre la verdadera magia rápida. 
        # Pedimos el formato 'verbose_json' para que nos devuelva los tiempos (start y end) exactos para los cortes.
        resultado = client.audio.transcriptions.create(
            model="whisper-1",
            file=archivo_audio,
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )
    
    fin = time.time()
    tiempo_tardado = round(fin - inicio, 2)
    
    # Convertimos la respuesta de OpenAI al mismo formato de diccionario que usabas antes
    # Esto es VITAL para no romper tu archivo 'cortador.py'
    resultado_dict = resultado.model_dump() if hasattr(resultado, 'model_dump') else resultado
    
    print(f"\n✅ ¡Transcripción completada a la velocidad de la luz en {tiempo_tardado} segundos!")
    print("\n--- PREVISIÓN DEL TEXTO (Primeros 300 caracteres) ---")
    print(resultado_dict["text"][:300] + "...\n")
    
    # Mostramos los tiempos para confirmar que la estructura es la correcta
    if "segments" in resultado_dict and len(resultado_dict["segments"]) > 0:
        print("--- ESTRUCTURA DE TIEMPOS (Primer fragmento) ---")
        primer_segmento = resultado_dict["segments"][0]
        print(f"[{primer_segmento['start']}s -> {primer_segmento['end']}s] {primer_segmento['text']}")
    
    return resultado_dict

# --- ZONA DE PRUEBAS ---
if __name__ == "__main__":
    print("🛠️ MÓDULO 2: TRANSCRIPTOR IA (Conectado a la API de OpenAI)")
    
    # Puedes probarlo en local descomentando la línea de abajo si tienes el MP3 en esa ruta
    ruta_del_mp3 = "archivos_brutos/El Mercado de Falsificaciones Más Grande de Asia.mp3"
    # transcribir_audio(ruta_del_mp3)