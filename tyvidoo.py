import streamlit as st
import os
import json
import subprocess
import yt_dlp
import re
import shutil
import zipfile
from openai import OpenAI
import time
from supabase import create_client, Client
import bcrypt
import random
import base64
import streamlit.components.v1 as components

# --- INICIALIZAR MEMORIA (Antes de cargar la interfaz) ---
if "tema" not in st.session_state: st.session_state.tema = "dark"
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "mis_clips_data" not in st.session_state: st.session_state.mis_clips_data = [] 
if "plantilla" not in st.session_state: st.session_state.plantilla = "Hormozi 💛"
if "whisper_data" not in st.session_state: st.session_state.whisper_data = None
if "video_bruto_path" not in st.session_state: st.session_state.video_bruto_path = None
if "duracion_max_video" not in st.session_state: st.session_state.duracion_max_video = 100.0
if "show_auth" not in st.session_state: st.session_state.show_auth = False
if "aviso_ia" not in st.session_state: st.session_state.aviso_ia = ""
if "show_delete_confirm" not in st.session_state: st.session_state.show_delete_confirm = False

# --- CONFIGURACIÓN DE SECRETOS ---
try:
    API_KEY = os.environ.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
    SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
    
    if not API_KEY or not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Faltan contraseñas")
except Exception as e:
    st.error("⚠️ Faltan las claves. Asegúrate de ponerlas en la pestaña 'Variables' de Railway.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- FUNCIÓN DE DESENCRIPTADO PARA GOOGLE ---
def decode_jwt(token):
    try:
        parts = token.split('.')
        if len(parts) >= 2:
            payload = parts[1]
            payload += "=" * ((4 - len(payload) % 4) % 4)
            decoded = base64.b64decode(payload).decode('utf-8')
            return json.loads(decoded)
    except:
        return None

# --- CONFIGURACIÓN DE PÁGINA Y CSS PREMIUM ---
st.set_page_config(page_title="Tyvidoo | AI Video Clipping Tool", page_icon="✂️", layout="wide")

# --- VARIABLES DE TEMA (MODO DÍA Y MODO NOCHE) ---
if st.session_state.tema == "dark":
    theme_vars = """
    :root {
        --bg-main: #050505;
        --txt-main: #ffffff;
        --txt-muted: #888888;
        --card-bg: rgba(255,255,255,0.02);
        --card-border: rgba(255,255,255,0.05);
        --card-hover: rgba(255,255,255,0.2);
        --sidebar-bg: #0A0A0A;
        --pricing-bg: #0A0A0A;
        --pricing-pro-bg: linear-gradient(180deg, #110508 0%, #0A0A0A 100%);
        --glass-card: rgba(255,255,255,0.03);
        --dash-header: linear-gradient(135deg, #111111 0%, #050505 100%);
    }
    """
else:
    theme_vars = """
    :root {
        --bg-main: #F4F6F8;
        --txt-main: #111111;
        --txt-muted: #555555;
        --card-bg: #FFFFFF;
        --card-border: rgba(0,0,0,0.1);
        --card-hover: rgba(0,0,0,0.3);
        --btn-sec-bg: rgba(0,0,0,0.05);
        --btn-sec-hover: rgba(0,0,0,0.1);
        --sidebar-bg: #FFFFFF;
        --pricing-bg: #FFFFFF;
        --pricing-pro-bg: linear-gradient(180deg, #FFF0F2 0%, #FFFFFF 100%);
        --glass-card: #FFFFFF;
        --dash-header: linear-gradient(135deg, #FFFFFF 0%, #E8EBEF 100%);
    }
    """

st.markdown(f"""
    <style>
    {theme_vars}
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    .stApp {{ background-color: var(--bg-main); color: var(--txt-main); transition: all 0.3s ease; }}
    header {{visibility: hidden;}}
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    .block-container {{ padding-top: 1rem !important; max-width: 1200px; padding-bottom: 5rem;}}
    
    /* --- REGLAS ESTRICTAS DE CONTRASTE PARA TEXTOS --- */
    h1, h2, h3, h4, h5, h6 {{ color: var(--txt-main) !important; }}
    p, span, label, small {{ color: var(--txt-main) !important; }}
    
    .hero-subtitle, .section-subtitle, .pricing-features, 
    .stSlider div[data-testid="stTickBarMin"], 
    .stSlider div[data-testid="stTickBarMax"] {{ 
        color: var(--txt-muted) !important; 
    }}
    
    /* --- ELIMINACIÓN TOTAL DEL FONDO NEGRO DE STREAMLIT --- */
    div[data-testid="stFileUploader"] > section {{
        background-color: var(--card-bg) !important;
        background: var(--card-bg) !important;
        border: 2px dashed var(--txt-muted) !important;
        border-radius: 16px !important;
        padding: 25px !important;
    }}
    div[data-testid="stFileUploader"] > section * {{
        color: var(--txt-main) !important;
    }}
    div[data-testid="stFileUploader"] > section button {{
        background-color: var(--bg-main) !important;
        color: var(--txt-main) !important;
        border: 1px solid var(--txt-muted) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }}
    
    /* --- ARREGLO DE BARRA LATERAL, RADIO BUTTONS Y SLIDER --- */
    [data-testid="stSidebar"] {{ background-color: var(--sidebar-bg) !important; border-right: 1px solid var(--card-border) !important; }}
    [data-testid="stSidebarHeader"] {{ background-color: var(--sidebar-bg) !important; }}
    
    .stRadio [role="radiogroup"] * {{ color: var(--txt-main) !important; }}
    .stSlider [role="slider"] {{ background: #E94057 !important; border: none !important; }}
    
    /* --- BOTONES PRINCIPALES Y SECUNDARIOS --- */
    [data-testid="baseButton-primary"] {{ 
        background: linear-gradient(90deg, #E94057, #F27121) !important; 
        border: none !important; 
        border-radius: 12px !important; 
        padding: 12px 30px !important; 
        box-shadow: 0 4px 15px rgba(233,64,87,0.3) !important; 
        transition: transform 0.2s !important; 
    }}
    [data-testid="baseButton-primary"] p, [data-testid="baseButton-primary"] span {{
        color: #ffffff !important; 
        font-weight: 800 !important; 
        font-size: 16px !important;
    }}
    [data-testid="baseButton-primary"]:hover {{ transform: translateY(-2px) scale(1.02); box-shadow: 0 6px 20px rgba(233,64,87,0.5) !important; }}
    
    [data-testid="baseButton-secondary"] {{ 
        background: var(--card-bg) !important; 
        border: 1px solid var(--card-border) !important; 
        border-radius: 12px !important; 
        transition: all 0.2s !important; 
    }}
    [data-testid="baseButton-secondary"] p, [data-testid="baseButton-secondary"] span {{
        color: var(--txt-main) !important; 
        font-weight: 600 !important;
    }}
    [data-testid="baseButton-secondary"]:hover {{ background: var(--card-hover) !important; transform: translateY(-2px); }}
    
    /* --- ESTÉTICA GENERAL --- */
    .top-nav {{ display: flex; justify-content: space-between; align-items: center; padding: 20px 0; border-bottom: 1px solid var(--card-border); margin-bottom: 50px; }}
    .nav-logo {{ font-size: 26px; font-weight: 900; letter-spacing: -1px; background: linear-gradient(90deg, #E94057, #F27121); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
    
    .hero-tag {{ color: #E94057; font-size: 13px; font-weight: 800; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 15px; display: inline-block; background: rgba(233, 64, 87, 0.1); padding: 5px 15px; border-radius: 20px; border: 1px solid rgba(233, 64, 87, 0.3);}}
    .hero-title {{ font-size: 4.5rem; font-weight: 900; line-height: 1.1; letter-spacing: -2.5px; margin-bottom: 25px; }}
    .hero-title-gradient {{ background: linear-gradient(90deg, #8A2387, #E94057, #F27121); -webkit-background-clip: text; -webkit-text-fill-color: transparent; display: inline-block; }}
    .hero-subtitle {{ font-size: 1.3rem; font-weight: 400; max-width: 750px; margin: 0 auto 40px auto; line-height: 1.6; text-align: center; }}
    
    .dash-header {{ background: var(--dash-header); padding: 40px; border-radius: 24px; border: 1px solid var(--card-border); margin-bottom: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
    .dash-title {{ font-size: 2.5rem; font-weight: 900; margin-bottom: 10px; }}
    
    .glass-card {{ background: var(--glass-card); border: 1px solid var(--card-border); border-radius: 20px; padding: 20px; text-align: center; transition: all 0.3s ease; }}
    .glass-card:hover {{ transform: translateY(-5px); border: 1px solid var(--card-hover); }}
    
    .stTabs [data-baseweb="tab-list"] {{ gap: 24px; justify-content: center; }}
    .stTabs [data-baseweb="tab"] {{ height: 50px; white-space: pre-wrap; background-color: transparent; border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; padding-bottom: 10px; font-weight: 600; font-size: 16px; color: var(--txt-muted);}}
    .stTabs [aria-selected="true"] {{ border-bottom: 2px solid #E94057 !important; }}
    
    .marquee-wrapper {{ overflow: hidden; white-space: nowrap; margin-top: 60px; padding: 30px 0; border-top: 1px solid var(--card-border); border-bottom: 1px solid var(--card-border); background: var(--bg-main); }}
    .marquee-content {{ display: inline-block; animation: marquee 35s linear infinite; }}
    .review-card {{ display: inline-block; background: var(--glass-card); padding: 25px 40px; border-radius: 20px; border: 1px solid var(--card-border); margin-right: 30px; font-size: 16px; color: var(--txt-main); backdrop-filter: blur(10px); box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
    .review-author {{ display: block; margin-top: 12px; font-weight: 800; font-size: 14px; color: var(--txt-main); }}
    @keyframes marquee {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-50%); }} }}

    .section-title {{ font-size: 3rem; font-weight: 900; text-align: center; margin: 100px 0 20px 0; letter-spacing: -1.5px; }}
    .section-subtitle {{ text-align: center; margin-bottom: 50px; font-size: 1.2rem; max-width: 600px; margin-left: auto; margin-right: auto;}}
    
    .pricing-card {{ background: var(--pricing-bg); border: 1px solid var(--card-border); border-radius: 24px; padding: 40px 30px; text-align: center; position: relative; height: 100%; transition: transform 0.3s; display: flex; flex-direction: column; }}
    .pricing-card:hover {{ transform: translateY(-5px); border-color: var(--card-hover); }}
    
    .pricing-card.pro {{ border: 2px solid #E94057; background: var(--pricing-pro-bg); transform: scale(1.05); z-index: 10; box-shadow: 0 10px 40px rgba(233, 64, 87, 0.2); }}
    .pricing-card.pro:hover {{ transform: scale(1.05) translateY(-5px); box-shadow: 0 15px 50px rgba(233, 64, 87, 0.3); }}
    
    .badge {{ position: absolute; top: -14px; left: 50%; transform: translateX(-50%); background: linear-gradient(90deg, #E94057, #F27121); color: #fff !important; padding: 6px 16px; border-radius: 20px; font-size: 12px; font-weight: 800; letter-spacing: 1px; box-shadow: 0 4px 10px rgba(233,64,87,0.4);}}
    
    .price {{ font-size: 3.5rem; font-weight: 900; margin: 20px 0; min-height: 120px; display: flex; flex-direction: column; justify-content: center; }}
    .price span {{ font-size: 0.9rem; color: var(--txt-muted) !important; font-weight: 500; display: block; margin-top: 8px; line-height: 1.2; }}
    
    .pricing-features {{ text-align: left; margin: 20px 0 40px 0; font-size: 15px; line-height: 2.2; flex-grow: 1; }}
    
    .google-custom-btn {{
        display: flex; align-items: center; justify-content: center; background-color: #ffffff; color: #111 !important;
        font-weight: 700; font-size: 16px; border-radius: 14px; padding: 14px 24px;
        text-decoration: none; border: 1px solid #ddd; box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        transition: all 0.2s ease; width: 100%; margin-top: 15px; cursor: pointer;
    }}
    .google-custom-btn:hover {{ background-color: #f1f1f1; transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.1); }}
    .google-custom-btn svg {{ width: 22px; height: 22px; margin-right: 12px; }}
    
    .pricing-btn-primary {{ display:block; text-align:center; width:100%; padding:16px; border-radius:12px; background: linear-gradient(90deg, #E94057, #F27121); border:none; color:white !important; font-weight:800; text-decoration:none; transition: all 0.2s; box-shadow: 0 4px 15px rgba(233,64,87,0.3); margin-top: auto; }}
    .pricing-btn-primary:hover {{ transform: scale(1.03); box-shadow: 0 6px 20px rgba(233,64,87,0.5); }}
    .pricing-btn-secondary {{ display:block; text-align:center; width:100%; padding:16px; border-radius:12px; background:transparent; border:1px solid var(--card-border); color:var(--txt-main) !important; text-decoration:none; font-weight: 600; transition: background 0.2s; margin-top: auto; }}
    .pricing-btn-secondary:hover {{ background: var(--card-bg); border-color: var(--txt-muted); }}
    
    .footer {{ margin-top: 80px; padding-top: 40px; border-top: 1px solid var(--card-border); }}
    
    .stTextInput input {{ background: var(--bg-main) !important; color: var(--txt-main) !important; border: 1px solid var(--card-border) !important; }}
    </style>
""", unsafe_allow_html=True)


# --- EL "CABALLO DE TROYA" PARA GOOGLE ---
components.html("""
    <script>
        try {
            if (window.parent.location.hash.includes("access_token=")) {
                var script = window.parent.document.createElement('script');
                script.innerHTML = "window.location.href = window.location.href.replace('#', '?');";
                window.parent.document.head.appendChild(script);
            }
        } catch (e) {
            console.log("Esperando conexión...");
        }
    </script>
""", height=0, width=0)

# --- PROCESAR ENTRADA DE GOOGLE AUTOMÁTICAMENTE ---
if "access_token" in st.query_params:
    token_google = st.query_params["access_token"]
    datos_usuario = decode_jwt(token_google)
    
    email_real = "usuario_google@tyvidoo.com"
    if datos_usuario and "email" in datos_usuario:
        email_real = datos_usuario["email"].lower().strip()
        
    st.session_state.logged_in = True
    st.session_state.user_email = email_real
    
    try:
        db_check = supabase.table("usuarios").select("email").eq("email", email_real).execute()
        if len(db_check.data) == 0:
            clave_aleatoria = str(random.random()).encode('utf-8')
            hashed = bcrypt.hashpw(clave_aleatoria, bcrypt.gensalt()).decode('utf-8')
            supabase.table("usuarios").insert({"email": email_real, "password_hash": hashed, "creditos": 20}).execute()
    except:
        pass
        
    try:
        st.query_params.clear()
    except:
        pass 
    st.rerun()

# --- FUNCIONES DE CALLBACK ---
def cambiar_plantilla(nueva):
    st.session_state.plantilla = nueva

def logout_action():
    st.session_state.logged_in = False
    st.session_state.user_email = ""
    st.session_state.show_auth = False
    st.session_state.show_delete_confirm = False
    st.session_state.mis_clips_data = []
    try: st.query_params.clear()
    except: pass

def confirm_delete_action(): st.session_state.show_delete_confirm = True
def cancel_delete_action(): st.session_state.show_delete_confirm = False

def execute_delete_action():
    try:
        supabase.table("historial_clips").delete().eq("email_usuario", st.session_state.user_email).execute()
        supabase.table("usuarios").delete().eq("email", st.session_state.user_email).execute()
    except: pass
    logout_action()

def toggle_theme():
    st.session_state.tema = "light" if st.session_state.tema == "dark" else "dark"

# --- FUNCIONES DE BASE DE DATOS ---
def registrar_usuario(email, password):
    email = email.lower().strip()
    try:
        password_bytes = password.strip()[:72].encode('utf-8')
        hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
        supabase.table("usuarios").insert({"email": email, "password_hash": hashed_password, "creditos": 20}).execute()
        return True, ""
    except Exception as e: 
        return False, str(e)

def login_usuario(email, password):
    email = email.lower().strip()
    try:
        respuesta = supabase.table("usuarios").select("*").eq("email", email).execute()
        if len(respuesta.data) > 0:
            db_hash = respuesta.data[0]["password_hash"].encode('utf-8')
            password_bytes = password.strip()[:72].encode('utf-8')
            if bcrypt.checkpw(password_bytes, db_hash): return True
        return False
    except: return False

def obtener_creditos(email):
    email = email.lower().strip()
    try:
        respuesta = supabase.table("usuarios").select("creditos").eq("email", email).execute()
        if len(respuesta.data) > 0: return respuesta.data[0]["creditos"]
        return 0
    except: return 0

def gastar_creditos(email, cantidad):
    email = email.lower().strip()
    try:
        respuesta = supabase.table("usuarios").select("creditos").eq("email", email).execute()
        if len(respuesta.data) > 0 and respuesta.data[0]["creditos"] >= cantidad:
            supabase.table("usuarios").update({"creditos": respuesta.data[0]["creditos"] - cantidad}).eq("email", email).execute()
            return True
        return False
    except: return False

# --- FUNCIONES DEL MOTOR ---
def hex_a_ass(hex_color): return f"&H00{hex_color.lstrip('#')[4:6]}{hex_color.lstrip('#')[2:4]}{hex_color.lstrip('#')[0:2]}&"
def segundos_a_srt(segundos): return f"{int(segundos//3600):02d}:{int((segundos%3600)//60):02d}:{int(segundos%60):02d},{int((segundos-int(segundos))*1000):03d}"

def generar_srt_por_palabras(res, ini, fin, srt):
    with open(srt, "w", encoding="utf-8") as f:
        c = 1
        for p in res.get("words", []):
            if p["end"] > ini and p["start"] < fin:
                start_aj = max(0.0, p["start"]-ini)
                end_aj = min(fin-ini, p["end"]-ini)
                if end_aj > start_aj:
                    caracteres_malos = " ,.?!:;()'\"[]{}"
                    palabra = p['word'].strip(caracteres_malos).upper()
                    f.write(f"{c}\n{segundos_a_srt(start_aj)} --> {segundos_a_srt(end_aj)}\n{palabra}\n\n")
                    c += 1

def procesar_video_local(archivo_path, cant, d_min, d_max, prog):
    for d in ["archivos_brutos", "clips_finales"]:
        os.makedirs(d, exist_ok=True)
        for archivo in os.listdir(d): 
            if os.path.isfile(os.path.join(d, archivo)) and archivo != "v.mp4": 
                os.remove(os.path.join(d, archivo))

    a = os.path.abspath("archivos_brutos/a.mp3")
    prog.markdown("<div class='loader-container'><div class='pulse-ring'></div><h3 style='color:var(--txt-main);'>🎵 Extrayendo audio...</h3></div>", unsafe_allow_html=True)
    
    cmd_audio = ["ffmpeg", "-y", "-i", archivo_path, "-b:a", "32k", "-map", "a", a]
    subprocess.run(cmd_audio, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    
    return procesar_ia(a, archivo_path, cant, d_min, d_max, prog)

def procesar_ia(a, v, cant, d_min, d_max, prog):
    prog.markdown("<div class='loader-container'><div class='pulse-ring'></div><h3 style='color:var(--txt-main);'>🧠 La IA está analizando tu vídeo...</h3></div>", unsafe_allow_html=True)
    
    client = OpenAI(api_key=API_KEY)
    with open(a, "rb") as audio_file:
        res_raw = client.audio.transcriptions.create(
            model="whisper-1", file=audio_file, response_format="verbose_json",
            timestamp_granularities=["word"], language="es"
        )
    
    res_w = res_raw.model_dump() if hasattr(res_raw, 'model_dump') else res_raw
    st.session_state.whisper_data = res_w
    st.session_state.video_bruto_path = v
    if res_w.get("words"): st.session_state.duracion_max_video = res_w["words"][-1]["end"]

    prog.markdown("<div class='loader-container'><div class='pulse-ring'></div><h3 style='color:var(--txt-main);'>🎯 Mapeando los cortes exactos...</h3></div>", unsafe_allow_html=True)
    
    transcript_con_tiempos = ""
    palabras = res_w.get("words", [])
    for i in range(0, len(palabras), 15):
        chunk = palabras[i:i+15]
        if chunk:
            ini = chunk[0]['start']
            fin = chunk[-1]['end']
            txt = " ".join([p['word'] for p in chunk])
            transcript_con_tiempos += f"[{ini:.1f}s - {fin:.1f}s] {txt}\n"
    
    prompt_completo = f"""Actúa como un experto editor de TikTok. Extrae {cant} clips virales.
    Te paso el texto del vídeo etiquetado con las marcas de tiempo [inicio - fin].
    REGLAS ESTRICTAS:
    1. Devuelve clips interesantes.
    2. Títulos en ESPAÑOL, MUY CORTOS (MÁXIMO 4 PALABRAS).
    Devuelve un JSON EXACTO: {{"clips": [{{"inicio": 10.5, "fin": 42.1, "titulo": "TITULO"}}]}}"""
    
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini", messages=[{"role": "system", "content": prompt_completo}, {"role": "user", "content": transcript_con_tiempos}], response_format={"type": "json_object"}
        )
        clips = json.loads(res.choices[0].message.content).get("clips", [])
    except Exception:
        clips = []
        
    clips_finales = []
    for c in clips:
        ini = float(c.get("inicio", 0))
        fin = float(c.get("fin", ini + d_min))
        tit = str(c.get("titulo", "MOMENTO VIRAL"))
        
        if (fin - ini) < d_min: fin = ini + random.uniform(d_min, d_max)
        if (fin - ini) > d_max: fin = ini + d_max
            
        if fin > st.session_state.duracion_max_video: 
            fin = st.session_state.duracion_max_video
            ini = max(0, fin - d_min)
            
        palabras_tit = tit.split()
        if len(palabras_tit) > 4: tit = " ".join(palabras_tit[:4])
            
        clips_finales.append({"inicio": round(ini, 1), "fin": round(fin, 1), "titulo": tit.upper()})

    while len(clips_finales) < cant:
        ultimo_fin = clips_finales[-1]["fin"] if clips_finales else 0
        nuevo_ini = ultimo_fin + 5 
        nuevo_fin = nuevo_ini + random.uniform(d_min, d_max)
        if nuevo_fin > st.session_state.duracion_max_video:
            nuevo_ini = max(0, st.session_state.duracion_max_video - d_min)
            nuevo_fin = st.session_state.duracion_max_video
            
        clips_finales.append({"inicio": round(nuevo_ini, 1), "fin": round(nuevo_fin, 1), "titulo": "MOMENTO DESTACADO"})

    return clips_finales[:cant]

def renderizar_un_clip(num, ini, fin, tit, res_w, vid, font, tit_fs, col_tit, col_bg, ass_fs, col_sub, out, mv, logo):
    ts = int(time.time() * 1000)
    srt = f"archivos_brutos/sub_{ts}.srt"
    out_vid = f"clips_finales/clip_{ts}.mp4"
    generar_srt_por_palabras(res_w, ini, fin, srt)
    tit_safe = re.sub(r'[^\w\s¿?¡!,\.-]', '', tit).upper().replace("'", "") 
    
    f_base = "[0:v]split=2[original][copy];[copy]scale=-1:1920,crop=1080:1920,boxblur=20:20[bg];[original]scale=1080:-1[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[m_base];"
    cmd = ["ffmpeg", "-y", "-ss", str(ini), "-to", str(fin), "-i", vid]
    
    if logo and os.path.exists(logo):
        cmd.extend(["-i", logo])
        f_base += "[1:v]format=rgba,scale=150:-1[wm];[m_base][wm]overlay=30:30[m];"
    else: 
        f_base += "[m_base]null[m];"

    estilo_srt = f"PlayResX=1080,PlayResY=1920,Encoding=UTF-8,FontSize={ass_fs},PrimaryColour={col_sub},OutlineColour=&H40000000&,BorderStyle=1,Outline={out},Alignment=2,MarginV={mv},Bold=1"
    f_txt = f"[m]drawtext=text=' {tit_safe} ':fontfile={font}:fontsize={tit_fs}:fontcolor={col_tit}:x=(w-text_w)/2:y=220:box=1:boxcolor={col_bg}@0.95:boxborderw=20:enable=between(t\\,0\\,5)[w_txt];[w_txt]subtitles=filename={srt}:force_style='{estilo_srt}'[f]"
    
    cmd.extend(["-filter_complex", f_base + f_txt, "-map", "[f]", "-map", "0:a", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-movflags", "+faststart", out_vid])
    subprocess.run(cmd, capture_output=True)
    return out_vid if os.path.exists(out_vid) else None

# ==========================================
# VISTA 1: LANDING PAGE COMPLETA + GOOGLE LOGIN
# ==========================================
if not st.session_state.logged_in:
    col_logo, col_space, col_theme, col_login = st.columns([2, 4, 1, 1])
    with col_logo: st.markdown("<div class='top-nav'><div class='nav-logo'>✂️ Tyvidoo</div></div>", unsafe_allow_html=True)
    with col_theme:
        st.write("")
        btn_tema = "🌞 Día" if st.session_state.tema == "dark" else "🌙 Noche"
        if st.button(btn_tema, use_container_width=True, on_click=toggle_theme): pass
    with col_login:
        st.write("")
        if st.button("Iniciar Sesión", use_container_width=True, type="secondary"):
            st.session_state.show_auth = True
            st.rerun()

    if not st.session_state.show_auth:
        st.markdown("""
        <div style='text-align: center; margin-top: 40px;'>
            <div class='hero-tag'>INTELIGENCIA ARTIFICIAL PARA CREADORES</div>
            <h1 class='hero-title'>Multiplica tu audiencia.<br><span class='hero-title-gradient'>Sin multiplicar tu trabajo.</span></h1>
            <p class='hero-subtitle'>Deja que nuestra IA encuentre el oro escondido en tus horas de contenido. Genera Shorts, Reels y TikToks virales listos para publicar mientras tú te tomas un café.</p>
        </div>
        """, unsafe_allow_html=True)

        col_pad1, col_center, col_pad2 = st.columns([2, 6, 2])
        with col_center:
            st.markdown("<div style='background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 24px; padding: 40px; text-align: center; margin-bottom: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05);'>", unsafe_allow_html=True)
            st.markdown("<h3 style='margin-bottom: 25px;'>Pruébalo ahora mismo 👇</h3>", unsafe_allow_html=True)
            
            st.file_uploader("Sube tu archivo de vídeo o podcast (MP4, MOV)", type=["mp4", "mov"], label_visibility="collapsed")
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            if st.button("🚀 Generar mis primeros Clips Mágicos", type="primary", use_container_width=True):
                st.session_state.show_auth = True
                st.rerun()

        m_1 = "<div class='marquee-wrapper'><div class='marquee-content'>"
        m_2 = "<div class='review-card'>⭐⭐⭐⭐⭐ \"Antes tardaba 5 horas en sacar clips de mi podcast. Ahora Tyvidoo lo hace en 10 minutos. Es una locura.\"<span class='review-author'>— Marcos L. (Host de Podcast)</span></div>"
        m_3 = "<div class='review-card'>⭐⭐⭐⭐⭐ \"Llevamos 3 cuentas de clientes y esta herramienta nos ha salvado la vida. Retorno de inversión inmediato.\"<span class='review-author'>— Elena G. (Agencia de Marketing)</span></div>"
        m_4 = "<div class='review-card'>⭐⭐⭐⭐⭐ \"Los subtítulos automáticos estilo Hormozi son clavados. Se ven súper profesionales y retienen a la gente.\"<span class='review-author'>— David R. (Creador de Contenido)</span></div>"
        m_5 = "<div class='review-card'>⭐⭐⭐⭐⭐ \"Dejé de pagar a un editor externo por clips básicos. La IA escoge los momentos perfectos para Shorts.\"<span class='review-author'>— Sofía T. (YouTuber)</span></div>"
        m_6 = m_2 + m_3 + m_4 + m_5 + "</div></div>"
        st.markdown(m_1 + m_2 + m_3 + m_4 + m_5 + m_6, unsafe_allow_html=True)

        st.markdown("<h2 class='section-title'>Calidad profesional <span style='color:#E94057;'>en segundos</span></h2>", unsafe_allow_html=True)
        st.markdown("<p class='section-subtitle'>Elige entre nuestras plantillas optimizadas para retener la atención de la audiencia en TikTok, Reels y Shorts.</p>", unsafe_allow_html=True)
        
        c_vid1, c_vid2, c_vid3 = st.columns(3)
        with c_vid1:
            st.markdown(f"""<div style='border: 2px solid var(--card-border); border-radius: 12px; padding: 6px; background: var(--card-bg); cursor:pointer;'>
                <div style='width: 100%; aspect-ratio: 9/16; background: linear-gradient(to bottom, #222, #444, #222); position: relative; border-radius: 8px; overflow: hidden;'>
                    <div style='position: absolute; top: 15%; width: 100%; text-align: center;'><span style='background: black; color: white; font-family: Impact, sans-serif; font-size: 14px; padding: 4px 8px; text-transform: uppercase;'>TÍTULO VIRAL</span></div>
                    <div style='position: absolute; top: 35%; bottom: 35%; left: 0; right: 0; background: url(https://images.unsplash.com/photo-1557804506-669a67965ba0?w=400&q=80) center/cover;'></div>
                    <div style='position: absolute; bottom: 20%; width: 100%; text-align: center; color: yellow; font-family: Impact, sans-serif; font-size: 18px; text-shadow: -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000;'>TEXTO CLAVE</div>
                </div>
            </div><h4 style='margin-top:15px; text-align:center;'>Estilo Hormozi 💛</h4>""", unsafe_allow_html=True)
            
        with c_vid2:
            st.markdown(f"""<div style='border: 2px solid var(--card-border); border-radius: 12px; padding: 6px; background: var(--card-bg);'>
                <div style='width: 100%; aspect-ratio: 9/16; background: linear-gradient(to bottom, #111, #333, #111); position: relative; border-radius: 8px; overflow: hidden;'>
                    <div style='position: absolute; top: 15%; width: 100%; text-align: center;'><span style='background: #111; color: white; font-family: Arial, sans-serif; font-size: 14px; padding: 4px 8px;'>EL TEMA</span></div>
                    <div style='position: absolute; top: 35%; bottom: 35%; left: 0; right: 0; background: url(https://images.unsplash.com/photo-1581368135153-a506cf13b1e1?w=400&q=80) center/cover;'></div>
                    <div style='position: absolute; bottom: 20%; width: 100%; text-align: center; color: white; font-family: Arial, sans-serif; font-size: 16px; font-weight: bold; text-shadow: 1px 1px 2px #000;'>Podcast</div>
                </div>
            </div><h4 style='margin-top:15px; text-align:center;'>Estilo Podcast 🎙️</h4>""", unsafe_allow_html=True)

        with c_vid3:
            st.markdown(f"""<div style='border: 2px solid var(--card-border); border-radius: 12px; padding: 6px; background: var(--card-bg);'>
                <div style='width: 100%; aspect-ratio: 9/16; background: linear-gradient(to bottom, #001, #003, #001); position: relative; border-radius: 8px; overflow: hidden;'>
                    <div style='position: absolute; top: 15%; width: 100%; text-align: center;'><span style='background: #111; color: #0ff; font-family: Impact, sans-serif; font-size: 14px; padding: 4px 8px; text-transform: uppercase;'>MOMENTO</span></div>
                    <div style='position: absolute; top: 35%; bottom: 35%; left: 0; right: 0; background: url(https://images.unsplash.com/photo-1542751371-adc38448a05e?w=400&q=80) center/cover;'></div>
                    <div style='position: absolute; bottom: 20%; width: 100%; text-align: center; color: #f0f; font-family: Impact, sans-serif; font-size: 10px; text-shadow: 0 0 5px #f0f;'>GAMING</div>
                </div>
            </div><h4 style='margin-top:15px; text-align:center;'>Estilo Neón 👾</h4>""", unsafe_allow_html=True)

        st.markdown("<h2 class='section-title'>Planes simples y <span style='color:#F27121;'>transparentes</span></h2>", unsafe_allow_html=True)
        
        col_tog1, col_tog2, col_tog3 = st.columns([3, 3, 3])
        with col_tog2:
            st.markdown("<div style='margin-bottom: 40px; text-align: center;'>", unsafe_allow_html=True)
            facturacion_anual = st.toggle("Ahorra un 50% con el Plan Anual 🎁", value=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
        precio_pro = "9" if facturacion_anual else "19"
        precio_agencia = "24" if facturacion_anual else "49"
        texto_mes = "/mes (cobrado anualmente)" if facturacion_anual else "/mes"
        
        link_pro = "https://buy.stripe.com/fZueV67w5gbqexRckx6wE04" if facturacion_anual else "https://buy.stripe.com/7sY3co2bLaR62P93O16wE02"
        link_agencia = "https://buy.stripe.com/4gM00ceYx6AQ75p2JX6wE03" if facturacion_anual else "https://buy.stripe.com/28EaEQ3fP2kAdtN5W96wE01"

        p_col1, p_col2, p_col3 = st.columns(3)
        with p_col1:
            st.markdown(f"""
            <div class='pricing-card' style='margin-bottom: 15px;'>
                <h3>Starter Gratuito</h3>
                <div class='price'>$0<span>/mes</span></div>
                <div class='pricing-features'>✔️ <b>20 créditos de regalo</b><br>✔️ Exportación a 720p<br>✔️ Modelos estándar de IA<br>❌ Límite de tamaño</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🎁 Crear cuenta gratis", use_container_width=True):
                st.session_state.show_auth = True
                st.rerun()
        
        with p_col2:
            st.markdown(f"""
            <div class='pricing-card pro'>
                <div class='badge'>MÁS POPULAR</div>
                <h3>Creator Pro</h3>
                <div class='price'>${precio_pro}<span>{texto_mes}</span></div>
                <div class='pricing-features'>✔️ <b>150 créditos al mes</b><br>✔️ <b>Sin límite de tamaño</b><br>✔️ Exportación 1080p HD<br>✔️ Sin marca de agua</div>
                <a href='{link_pro}' target='_blank' class='pricing-btn-primary'>Empezar como Pro</a>
            </div>
            """, unsafe_allow_html=True)

        with p_col3:
            st.markdown(f"""
            <div class='pricing-card'>
                <h3>Agencia</h3>
                <div class='price'>${precio_agencia}<span>{texto_mes}</span></div>
                <div class='pricing-features'>✔️ <b>1000 minutos al mes</b><br>✔️ Todos los beneficios Pro<br>✔️ Acceso a la API<br>✔️ Soporte prioritario 24/7</div>
                <a href='{link_agencia}' target='_blank' class='pricing-btn-secondary'>Obtener Plan Agencia</a>
            </div>
            """, unsafe_allow_html=True)
            
        # FOOTER / PIE DE PÁGINA
        st.markdown("<div id='legales'></div><div class='footer'></div>", unsafe_allow_html=True)
        col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
        with col_f1:
            st.markdown("<h3 style='margin-bottom:10px;'>✂️ Tyvidoo</h3><p style='color:var(--txt-muted); font-size:14px; max-width: 300px;'>La inteligencia artificial definitiva para creadores de contenido y podcasters. Multiplica tu alcance en segundos.</p>", unsafe_allow_html=True)
        with col_f2:
            st.markdown("<h4 style='font-size:16px;'>Compañía</h4><p style='color:var(--txt-muted); font-size:14px; line-height:2;'>Sobre Nosotros<br><a href='#legales' style='color:var(--txt-muted); text-decoration:none;'>Términos y Privacidad</a><br><a href='#legales' style='color:var(--txt-muted); text-decoration:none;'>Política de Cookies</a></p>", unsafe_allow_html=True)
        with col_f3:
            st.markdown("<h4 style='font-size:16px;'>Soporte</h4><p style='color:var(--txt-muted); font-size:14px; line-height:2;'><a href='mailto:tyvidooinfo@gmail.com' style='color:var(--txt-muted); text-decoration:none;'>tyvidooinfo@gmail.com</a><br>Preguntas Frecuentes<br>Guía de uso rápida</p>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("⚖️ Leer Avisos Legales (Términos, Privacidad y Cookies)"):
            st.markdown("""
            **Términos y Condiciones de Uso**
            Al utilizar Tyvidoo AI, aceptas nuestros términos de servicio. Nuestra plataforma proporciona herramientas de inteligencia artificial para la edición de vídeo. El usuario es el único responsable del contenido subido y procesado, garantizando que posee los derechos de autor necesarios.
            
            **Política de Privacidad (RGPD)**
            Tu privacidad es nuestra prioridad. Los vídeos subidos son procesados de forma temporal y se eliminan de nuestros servidores de renderizado automáticamente. Los clips finales guardados en tu "Biblioteca" se mantienen en servidores seguros y privados asociados a tu cuenta. No compartimos ni vendemos tus datos a terceros.
            
            **Política de Cookies**
            Tyvidoo utiliza cookies strictly necesarias para mantener tu sesión activa y ofrecerte el servicio de la plataforma. También utilizamos cookies analíticas anónimas para mejorar el rendimiento de la web. Puedes configurar tu navegador para rechazar todas las cookies, aunque algunas partes del sitio no funcionarán correctamente.
            
            *Para cualquier consulta legal o relacionada con tus datos, contáctanos en: tyvidooinfo@gmail.com*
            """)
            
        st.markdown("<p style='text-align:center; color:var(--txt-muted); font-size:12px; margin-top:40px;'>© 2026 Tyvidoo AI. Todos los derechos reservados.</p>", unsafe_allow_html=True)

    else:
        st.markdown("<div style='text-align: center; margin-bottom: 30px;'><h2 style='font-weight: 900; font-size: 2.5rem;'>Crea tu cuenta gratis</h2><p style='color: var(--txt-muted);'>Accede a tu espacio de trabajo y recibe tus 20 créditos de bienvenida.</p></div>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            url_oauth_google = f"{SUPABASE_URL}/auth/v1/authorize?provider=google&redirect_to=https://aware-mercy-production-e677.up.railway.app"
            st.markdown(f"""
                <a href="{url_oauth_google}" target="_self" class="google-custom-btn">
                    <svg viewBox="0 0 24 24" width="20" height="20" xmlns="http://www.w3.org/2000/svg">
                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/>
                    </svg>
                    Continuar con Google
                </a>
            """, unsafe_allow_html=True)
            
            st.markdown("<p style='text-align:center; margin:25px 0; color:var(--txt-muted); font-size: 14px;'>— O USA TU CORREO —</p>", unsafe_allow_html=True)
            
            tab1, tab2 = st.tabs(["📝 Registrarse", "🔐 Iniciar Sesión"])
            with tab1:
                with st.form("reg_form"):
                    e_reg = st.text_input("Correo")
                    p_reg = st.text_input("Contraseña", type="password")
                    if st.form_submit_button("Crear mi cuenta", type="primary", use_container_width=True):
                        exito, msj = registrar_usuario(e_reg, p_reg)
                        if exito: st.success("✅ Cuenta creada. Inicia sesión para empezar.")
                        else: st.error(f"⚠️ Error: {msj}")
            with tab2:
                with st.form("log_form"):
                    e_log = st.text_input("Correo")
                    p_log = st.text_input("Contraseña", type="password")
                    if st.form_submit_button("Entrar a mi panel", type="primary", use_container_width=True):
                        if login_usuario(e_log, p_log):
                            st.session_state.logged_in = True
                            st.session_state.user_email = e_log.lower().strip()
                            st.session_state.show_auth = False
                            st.rerun()
                        else: st.error("❌ Correo o contraseña incorrectos.")
            st.write("")
            if st.button("← Volver al Inicio", use_container_width=True):
                st.session_state.show_auth = False
                st.rerun()

# ==========================================
# VISTA 2: PANEL CON NAVEGACIÓN Y BIBLIOTECA
# ==========================================
else:
    creditos = obtener_creditos(st.session_state.user_email)
    
    with st.sidebar:
        st.markdown("<h2 style='font-weight:900;'>✂️ Tyvidoo</h2>", unsafe_allow_html=True)
        st.caption(st.session_state.user_email)
        st.markdown(f"<div style='background: var(--card-bg); border-radius: 12px; padding: 20px; text-align: center; margin: 20px 0; border: 1px solid var(--card-border); box-shadow: 0 4px 10px rgba(0,0,0,0.05);'><h2 style='margin:0; font-weight: 900; color: var(--txt-main);'>{creditos}</h2><span style='font-size: 13px; color: var(--txt-muted); text-transform: uppercase; letter-spacing: 1px;'>créditos restantes</span></div>", unsafe_allow_html=True)
        
        link_recarga = f"https://buy.stripe.com/7sY3co2bLaR62P93O16wE02?client_reference_id={st.session_state.user_email}"
        st.markdown(f"<a href='{link_recarga}' target='_blank' style='display:block; text-align:center; width:100%; padding:12px; border-radius:10px; background: linear-gradient(90deg, #E94057, #F27121); border:none; color:white; font-weight:bold; text-decoration:none; margin-bottom: 25px; box-shadow: 0 4px 10px rgba(233,64,87,0.3);'>⚡ Recargar Créditos</a>", unsafe_allow_html=True)
        
        menu_principal = st.radio("Menú", ["✂️ Crear Clips", "📚 Mi Biblioteca"], label_visibility="collapsed")
        st.divider()
        
        if menu_principal == "✂️ Crear Clips":
            st.markdown("<b style='color: var(--txt-main);'>⚙️ Ajustes de Búsqueda</b>", unsafe_allow_html=True)
            cant_clips = st.slider("Clips a extraer", 1, 30, 10)
            dur_clips = st.slider("Duración aprox. (seg)", 15, 90, (20, 45))
            
            st.divider()
            st.markdown("<b style='color: var(--txt-main);'>🎨 Elige tu Diseño Final</b>", unsafe_allow_html=True)
            
            col_p1, col_p2, col_p3 = st.columns(3)
            b1 = "2px solid #E94057" if st.session_state.plantilla == "Hormozi 💛" else "1px solid var(--card-border)"
            b2 = "2px solid #E94057" if st.session_state.plantilla == "Podcast 🎙️" else "1px solid var(--card-border)"
            b3 = "2px solid #E94057" if st.session_state.plantilla == "Neón 👾" else "1px solid var(--card-border)"
            
            with col_p1:
                st.markdown(f"""<div style='border: {b1}; border-radius: 8px; padding: 4px; background: var(--card-bg);'>
                    <div style='width: 100%; aspect-ratio: 9/16; background: linear-gradient(to bottom, #222, #444, #222); position: relative; border-radius: 6px; overflow: hidden;'>
                        <div style='position: absolute; top: 15%; width: 100%; text-align: center;'><span style='background: black; color: white; font-family: Impact, sans-serif; font-size: 7px; padding: 2px 4px; text-transform: uppercase;'>TÍTULO VIRAL</span></div>
                        <div style='position: absolute; top: 35%; bottom: 35%; left: 0; right: 0; background: url(https://images.unsplash.com/photo-1557804506-669a67965ba0?w=100&q=80) center/cover;'></div>
                        <div style='position: absolute; bottom: 20%; width: 100%; text-align: center; color: yellow; font-family: Impact, sans-serif; font-size: 10px; text-shadow: -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000;'>TEXTO CLAVE</div>
                    </div>
                </div>""", unsafe_allow_html=True)
                st.button("💛 Horm", use_container_width=True, on_click=cambiar_plantilla, args=("Hormozi 💛",))

            with col_p2:
                st.markdown(f"""<div style='border: {b2}; border-radius: 8px; padding: 4px; background: var(--card-bg);'>
                    <div style='width: 100%; aspect-ratio: 9/16; background: linear-gradient(to bottom, #111, #333, #111); position: relative; border-radius: 6px; overflow: hidden;'>
                        <div style='position: absolute; top: 15%; width: 100%; text-align: center;'><span style='background: #333; color: white; font-family: Arial, sans-serif; font-size: 7px; padding: 2px 4px;'>EL TEMA</span></div>
                        <div style='position: absolute; top: 35%; bottom: 35%; left: 0; right: 0; background: url(https://images.unsplash.com/photo-1581368135153-a506cf13b1e1?w=100&q=80) center/cover;'></div>
                        <div style='position: absolute; bottom: 20%; width: 100%; text-align: center; color: white; font-family: Arial, sans-serif; font-size: 9px; font-weight: bold; text-shadow: 1px 1px 2px #000;'>Podcast</div>
                    </div>
                </div>""", unsafe_allow_html=True)
                st.button("🎙️ Pod", use_container_width=True, on_click=cambiar_plantilla, args=("Podcast 🎙️",))

            with col_p3:
                st.markdown(f"""<div style='border: {b3}; border-radius: 8px; padding: 4px; background: var(--card-bg);'>
                    <div style='width: 100%; aspect-ratio: 9/16; background: linear-gradient(to bottom, #001, #003, #001); position: relative; border-radius: 6px; overflow: hidden;'>
                        <div style='position: absolute; top: 15%; width: 100%; text-align: center;'><span style='background: #111; color: #0ff; font-family: Impact, sans-serif; font-size: 7px; padding: 2px 4px; text-transform: uppercase;'>MOMENTO</span></div>
                        <div style='position: absolute; top: 35%; bottom: 35%; left: 0; right: 0; background: url(https://images.unsplash.com/photo-1542751371-adc38448a05e?w=100&q=80) center/cover;'></div>
                        <div style='position: absolute; bottom: 20%; width: 100%; text-align: center; color: #f0f; font-family: Impact, sans-serif; font-size: 10px; text-shadow: 0 0 5px #f0f;'>GAMING</div>
                    </div>
                </div>""", unsafe_allow_html=True)
                st.button("👾 Neón", use_container_width=True, on_click=cambiar_plantilla, args=("Neón 👾",))
                
            plantilla = st.session_state.plantilla
            if plantilla == "Hormozi 💛": f_def, c_t, c_b, c_s, afs, aout, amv, tfs = "Impact", "#FFFFFF", "#000000", "#FFFF00", 110, 4, 450, 60
            elif plantilla == "Podcast 🎙️": f_def, c_t, c_b, c_s, afs, aout, amv, tfs = "Arial", "#FFFFFF", "#333333", "#FFFFFF", 80, 3, 350, 50
            else: f_def, c_t, c_b, c_s, afs, aout, amv, tfs = "Impact", "#00FFFF", "#111111", "#FF00FF", 100, 4, 400, 60
            col_s_ass = hex_a_ass(c_s)
            
            st.divider()
            archivo_logo = st.file_uploader("Marca de Agua (PNG)", type=["png"])
            
        st.divider()
        if not st.session_state.get("show_delete_confirm", False):
            st.button("🗑️ Eliminar mi cuenta", use_container_width=True, on_click=confirm_delete_action)
        else:
            st.warning("⚠️ Perderás tus créditos. ¿Seguro?")
            col_yes, col_no = st.columns(2)
            with col_yes:
                st.button("Sí, borrar", type="primary", use_container_width=True, on_click=execute_delete_action)
            with col_no:
                st.button("Cancelar", use_container_width=True, on_click=cancel_delete_action)
        
        btn_sidebar_tema = "🌞 Modo Día" if st.session_state.tema == "dark" else "🌙 Modo Noche"
        st.button(btn_sidebar_tema, use_container_width=True, on_click=toggle_theme)
        st.button("🚪 Cerrar Sesión", use_container_width=True, on_click=logout_action)

    # --- PANTALLA PRINCIPAL ---
    st.markdown("<div class='dash-header'><div class='dash-title'>✂️ Espacio de Trabajo</div></div>", unsafe_allow_html=True)
    
    if menu_principal == "✂️ Crear Clips":
        if st.session_state.aviso_ia:
            st.warning(st.session_state.aviso_ia)

        espacio_animacion = st.empty()

        if not st.session_state.mis_clips_data:
            
            archivo_subido = st.file_uploader("📂 Sube tu archivo de vídeo o podcast (MP4, MOV)", type=["mp4", "mov"])
            st.write("")
            btn_crear = st.button("🚀 Procesar Archivo y Crear Clips Mágicos", type="primary")

            if btn_crear:
                if not archivo_subido: 
                    st.warning("⚠️ Por favor, sube un archivo primero.")
                elif creditos < cant_clips: 
                    st.error("❌ No tienes suficientes créditos para esta petición.")
                else:
                    st.session_state.mis_clips_data = []
                    st.session_state.aviso_ia = ""
                    logo_path = "logo_tmp.png" if archivo_logo else None
                    if logo_path:
                        with open(logo_path, "wb") as f: f.write(archivo_logo.getbuffer())
                    
                    try:
                        os.makedirs("archivos_brutos", exist_ok=True)
                        video_guardado_path = os.path.abspath("archivos_brutos/v.mp4")
                        espacio_animacion.markdown("<div class='loader-container'><h3 style='color:var(--txt-main);'>📥 Subiendo tu vídeo...</h3></div>", unsafe_allow_html=True)
                        with open(video_guardado_path, "wb") as f: f.write(archivo_subido.getbuffer())
                        
                        clips_a_renderizar = procesar_video_local(video_guardado_path, cant_clips, dur_clips[0], dur_clips[1], espacio_animacion)
                        
                        if len(clips_a_renderizar) > creditos:
                            st.warning(f"⚠️ Has pedido más clips de los créditos que tienes. Solo se generarán los primeros {creditos}.")
                            clips_a_renderizar = clips_a_renderizar[:creditos]

                        if len(clips_a_renderizar) > 0:
                            for i, cl in enumerate(clips_a_renderizar):
                                espacio_animacion.markdown(f"<div class='loader-container'><h3 style='color:var(--txt-main);'>✂️ Renderizando clip {i+1}/{len(clips_a_renderizar)}...</h3></div>", unsafe_allow_html=True)
                                r = renderizar_un_clip(i+1, cl["inicio"], cl["fin"], cl["titulo"], st.session_state.whisper_data, st.session_state.video_bruto_path, f"/System/Library/Fonts/Supplemental/{f_def}.ttf", tfs, c_t, c_b, afs, col_s_ass, aout, amv, logo_path)
                                if r: 
                                    st.session_state.mis_clips_data.append({"id": i+1, "inicio": cl["inicio"], "fin": cl["fin"], "titulo": cl["titulo"], "ruta": r})
                                    
                                    try:
                                        nombre_nube = f"clip_{int(time.time())}_{i}.mp4"
                                        with open(r, "rb") as f:
                                            supabase.storage.from_("clips").upload(nombre_nube, f.read(), {"content-type": "video/mp4"})
                                        url_nube = supabase.storage.from_("clips").get_public_url(nombre_nube)
                                        supabase.table("historial_clips").insert({
                                            "email_usuario": st.session_state.user_email,
                                            "titulo_clip": cl["titulo"],
                                            "ruta_archivo": url_nube
                                        }).execute()
                                    except Exception as e:
                                        pass
                            
                            espacio_animacion.empty()
                            clips_logrados = len(st.session_state.mis_clips_data)
                            if clips_logrados > 0:
                                gastar_creditos(st.session_state.user_email, clips_logrados)
                                time.sleep(0.5) 
                                st.rerun()
                        else:
                            espacio_animacion.empty()
                            st.error("⚠️ Ha ocurrido un error al buscar clips.")

                    except Exception as e:
                        espacio_animacion.empty()
                        st.error(f"Error procesando: {e}")

        elif st.session_state.mis_clips_data:
            st.success("✅ ¡Tus clips están listos! También se han guardado permanentemente en tu Biblioteca.")
            
            col_tit, col_btn = st.columns([3, 1])
            with col_tit: st.markdown("<h3 style='margin:0; color:var(--txt-main);'>Galería Final</h3>", unsafe_allow_html=True)
            with col_btn:
                zip_path = "archivos_brutos/todos_los_clips.zip"
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for clip in st.session_state.mis_clips_data:
                        n_limpio = re.sub(r'[^\w\s-]', '', clip["titulo"]).strip().replace(" ", "_")
                        zipf.write(clip["ruta"], f"Clip_{clip['id']}_{n_limpio}.mp4")
            with open(zip_path, "rb") as f: 
                st.download_button(label="📦 Descargar TODOS (.zip)", data=f, file_name="Tyvidoo_Clips.zip", mime="application/zip", use_container_width=True)

            st.divider()
            cols = st.columns(3)
            for i, clip in enumerate(st.session_state.mis_clips_data):
                with cols[i % 3]:
                    st.markdown(f"<div class='glass-card'>", unsafe_allow_html=True)
                    st.video(clip["ruta"])
                    st.markdown(f"<b style='display:block; margin: 10px 0;'>{clip['titulo']}</b>", unsafe_allow_html=True)
                    with open(clip["ruta"], "rb") as f: 
                        st.download_button(label="⬇️ Descargar HD", data=f, file_name=f"Clip_{clip['id']}.mp4", mime="video/mp4", use_container_width=True, key=f"dl_{clip['id']}")
                    st.markdown("</div>", unsafe_allow_html=True)
                    
            if st.button("Crear nuevo proyecto", type="primary"):
                st.session_state.mis_clips_data = []
                st.session_state.aviso_ia = ""
                st.rerun()

    # --- PESTAÑA DE LA BIBLIOTECA ---
    elif menu_principal == "📚 Mi Biblioteca":
        st.markdown("<h3 style='color:var(--txt-main);'>Tus clips guardados en la nube</h3>", unsafe_allow_html=True)
        st.info("💡 Estos clips se guardan de forma segura durante 24 horas.")
        try:
            res_bib = supabase.table("historial_clips").select("*").eq("email_usuario", st.session_state.user_email).order("fecha_creacion", desc=True).execute()
            if not res_bib.data:
                st.info("Aún no tienes clips guardados en tu biblioteca.")
            else:
                cols_b = st.columns(3)
                for idx, b_clip in enumerate(res_bib.data):
                    with cols_b[idx % 3]:
                        st.markdown(f"<div class='glass-card'>", unsafe_allow_html=True)
                        st.video(b_clip['ruta_archivo'])
                        st.link_button("⬇️ Descargar HD", b_clip['ruta_archivo'], use_container_width=True)
                        st.markdown(f"<b style='display:block; margin: 10px 0;'>{b_clip['titulo_clip']}</b>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
        except Exception as e:
            st.error("Error al cargar la biblioteca. Asegúrate de haber completado los pasos de Supabase.")
