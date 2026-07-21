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

# --- CONFIGURACIÓN DE PÁGINA Y CSS ---
st.set_page_config(page_title="Tyvidoo | AI Video Clipping Tool", page_icon="✂️", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #050505; color: #ffffff; }
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container { padding-top: 1rem !important; max-width: 1200px; padding-bottom: 5rem;}
    
    .top-nav { display: flex; justify-content: space-between; align-items: center; padding: 20px 0; border-bottom: 1px solid rgba(255,255,255,0.05); margin-bottom: 40px; }
    .nav-logo { font-size: 24px; font-weight: 900; letter-spacing: -1px; background: linear-gradient(90deg, #FFFFFF, #AAAAAA); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    
    .dash-header { background: linear-gradient(135deg, #151515 0%, #0a0a0a 100%); padding: 40px; border-radius: 20px; border: 1px solid #222; margin-bottom: 30px; box-shadow: 0 20px 40px rgba(0,0,0,0.5); }
    .dash-title { font-size: 2.5rem; font-weight: 900; margin-bottom: 10px; }
    .dash-sub { color: #888; font-size: 1.1rem; }
    
    .glass-card { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 20px; padding: 20px; text-align: center; transition: all 0.3s ease; }
    .glass-card:hover { transform: translateY(-5px); border: 1px solid rgba(255,255,255,0.2); }

    .stButton>button[kind="primary"] { background-color: #ffffff !important; color: #000000 !important; font-weight: 800 !important; border-radius: 12px !important; border: none !important; font-size: 16px !important; padding: 10px 30px !important; width: 100% !important; margin-top: 5px; }
    .stButton>button[kind="primary"]:hover { transform: translateY(-2px); background-color: #eeeeee !important; }
    
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: transparent; border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; padding-bottom: 10px; font-weight: 600; font-size: 16px; }
    .stTabs [aria-selected="true"] { color: #ffffff !important; border-bottom: 2px solid #ffffff !important; }
    </style>
""", unsafe_allow_html=True)

# --- INICIALIZAR MEMORIA ---
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "mis_clips_data" not in st.session_state: st.session_state.mis_clips_data = [] 
if "whisper_data" not in st.session_state: st.session_state.whisper_data = None
if "video_bruto_path" not in st.session_state: st.session_state.video_bruto_path = None
if "duracion_max_video" not in st.session_state: st.session_state.duracion_max_video = 100.0
if "show_auth" not in st.session_state: st.session_state.show_auth = False

# --- FUNCIONES DE BASE DE DATOS ---
def registrar_usuario(email, password):
    email = email.lower().strip()
    try:
        password_bytes = password.strip()[:72].encode('utf-8')
        hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
        supabase.table("usuarios").insert({"email": email, "password_hash": hashed_password, "creditos": 30}).execute()
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

def procesar_video_youtube(url, cant, d_min, d_max, prog):
    for d in ["archivos_brutos", "clips_finales"]:
        os.makedirs(d, exist_ok=True)
        for a in os.listdir(d): 
            if os.path.isfile(os.path.join(d, a)): os.remove(os.path.join(d, a))

    v = os.path.abspath("archivos_brutos/v.mp4")
    a = os.path.abspath("archivos_brutos/a.mp3")
    
    prog.markdown("<div class='loader-container'><div class='pulse-ring'></div><h3>📥 Descargando desde YouTube...</h3></div>", unsafe_allow_html=True)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': v,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'quiet': True,
        'extractor_args': {'youtube': {'player_client': ['ios', 'web']}},
        'http_headers': { 'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15' }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
    subprocess.run(["ffmpeg", "-y", "-i", v, "-b:a", "32k", "-map", "a", a], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return procesar_ia(a, v, cant, d_min, d_max, prog)

def procesar_video_local(archivo_path, cant, d_min, d_max, prog):
    for d in ["archivos_brutos", "clips_finales"]:
        os.makedirs(d, exist_ok=True)
        for archivo in os.listdir(d): 
            if os.path.isfile(os.path.join(d, archivo)) and archivo != "v.mp4": 
                os.remove(os.path.join(d, archivo))

    a = os.path.abspath("archivos_brutos/a.mp3")
    prog.markdown("<div class='loader-container'><div class='pulse-ring'></div><h3>🎵 Extrayendo audio del archivo...</h3></div>", unsafe_allow_html=True)
    subprocess.run(["ffmpeg", "-y", "-i", archivo_path, "-b:a", "32k", "-map", "a", a], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return procesar_ia(a, archivo_path, cant, d_min, d_max, prog)

def procesar_ia(a, v, cant, d_min, d_max, prog):
    prog.markdown("<div class='loader-container'><div class='pulse-ring'></div><h3>🧠 Transcribiendo en Español (API)...</h3></div>", unsafe_allow_html=True)
    
    client = OpenAI(api_key=API_KEY)
    with open(a, "rb") as audio_file:
        res_raw = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["word"],
            language="es" # OBLIGAMOS A QUE SEA EN ESPAÑOL
        )
    
    res_w = res_raw.model_dump() if hasattr(res_raw, 'model_dump') else res_raw
    st.session_state.whisper_data = res_w
    st.session_state.video_bruto_path = v
    if res_w.get("words"): st.session_state.duracion_max_video = res_w["words"][-1]["end"]

    prog.markdown("<div class='loader-container'><div class='pulse-ring'></div><h3>🎯 Buscando los mejores momentos...</h3></div>", unsafe_allow_html=True)
    
    # PROMPT ESTRICTO
    prompt_completo = f"Actúa como un experto editor de TikTok. Tu tarea es extraer la mayor cantidad de clips posibles (máximo {cant}) del siguiente texto. OBLIGATORIO: cada clip debe durar entre {d_min} y {d_max} segundos. Títulos en ESPAÑOL, muy clickbait (máximo 5 palabras). Devuelve un JSON EXACTO con esta estructura: {{\"clips\": [{{\"inicio\": 10.5, \"fin\": 32.0, \"titulo\": \"TITULO\"}}]}}"
    
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini", messages=[{"role": "system", "content": prompt_completo}, {"role": "user", "content": res_w['text']}], response_format={"type": "json_object"}
        )
        clips = json.loads(res.choices[0].message.content).get("clips", [])
    except Exception as e:
        clips = []
        
    return clips

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

    # COORDENADAS FIJAS PARA EVITAR EL CENTRO
    estilo_srt = f"PlayResX=1080,PlayResY=1920,Encoding=UTF-8,FontSize={ass_fs},PrimaryColour={col_sub},OutlineColour=&H40000000&,BorderStyle=1,Outline={out},Alignment=2,MarginV={mv},Bold=1"
    f_txt = f"[m]drawtext=text=' {tit_safe} ':fontfile={font}:fontsize={tit_fs}:fontcolor={col_tit}:x=(w-text_w)/2:y=220:box=1:boxcolor={col_bg}@0.95:boxborderw=20:enable=between(t\\,0\\,5)[w_txt];[w_txt]subtitles=filename={srt}:force_style='{estilo_srt}'[f]"
    
    cmd.extend(["-filter_complex", f_base + f_txt, "-map", "[f]", "-map", "0:a", "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", out_vid])
    subprocess.run(cmd, capture_output=True)
    return out_vid if os.path.exists(out_vid) else None

# ==========================================
# INTERFAZ
# ==========================================
if not st.session_state.logged_in:
    col_logo, col_space, col_login = st.columns([2, 5, 1])
    with col_logo: st.markdown("<div class='top-nav'><div class='nav-logo'>✂️ Tyvidoo AI</div></div>", unsafe_allow_html=True)
    with col_login:
        st.write("")
        if st.button("Sign In", use_container_width=True):
            st.session_state.show_auth = True
            st.rerun()

    if not st.session_state.show_auth:
        st.markdown("<div style='text-align: center; margin-top: 20px;'><h1 class='hero-title'>De 1 vídeo largo a 10 clips virales.</h1></div>", unsafe_allow_html=True)
        col_pad1, col_center, col_pad2 = st.columns([1, 8, 1])
        with col_center:
            if st.button("🚀 Iniciar Sesión y Generar Clips", type="primary", use_container_width=True):
                st.session_state.show_auth = True
                st.rerun()
    else:
        st.markdown("<div style='text-align: center; margin-bottom: 30px;'><h2 style='font-weight: 800;'>Comienza a crear</h2></div>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            tab1, tab2 = st.tabs(["📝 Registrarse", "🔐 Iniciar Sesión"])
            with tab1:
                with st.form("reg_form"):
                    e_reg = st.text_input("Correo")
                    p_reg = st.text_input("Contraseña", type="password")
                    if st.form_submit_button("Crear cuenta", type="primary", use_container_width=True):
                        exito, msj = registrar_usuario(e_reg, p_reg)
                        if exito: st.success("✅ Creada. Inicia sesión.")
                        else: st.error(f"⚠️ Error: {msj}")
            with tab2:
                with st.form("log_form"):
                    e_log = st.text_input("Correo")
                    p_log = st.text_input("Contraseña", type="password")
                    if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                        if login_usuario(e_log, p_log):
                            st.session_state.logged_in = True
                            st.session_state.user_email = e_log.lower().strip()
                            st.session_state.show_auth = False
                            st.rerun()
                        else: st.error("❌ Datos incorrectos.")
            if st.button("← Volver al Inicio", use_container_width=True):
                st.session_state.show_auth = False
                st.rerun()

else:
    creditos = obtener_creditos(st.session_state.user_email)
    
    with st.sidebar:
        st.markdown("<h2 style='font-weight:900;'>✂️ Tyvidoo</h2>", unsafe_allow_html=True)
        st.caption(st.session_state.user_email)
        st.markdown(f"<div style='background: rgba(255, 255, 255, 0.05); border-radius: 10px; padding: 15px; text-align: center; margin: 20px 0;'><h2 style='margin:0; font-weight: 800;'>{creditos} <span style='font-size: 14px; color: #888;'>créditos</span></h2></div>", unsafe_allow_html=True)
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.logged_in = False; st.session_state.user_email = ""; st.rerun()
            
        st.divider()
        st.markdown("<b>⚙️ Configuración del Motor</b>", unsafe_allow_html=True)
        cant_clips = st.slider("Clips a extraer", 1, 30, 10)
        dur_clips = st.slider("Duración aprox. (seg)", 15, 90, (20, 45))
        plantilla = st.selectbox("Estilo Visual", ["Hormozi 💛", "Podcast 🎙️", "Neón 👾"])
        
        # NUEVOS TAMAÑOS ADAPTADOS A FORMATO VERTICAL 1080x1920
        if plantilla == "Hormozi 💛": f_def, c_t, c_b, c_s, afs, aout, amv, tfs = "Impact", "#FFFFFF", "#000000", "#FFFF00", 110, 4, 450, 80
        elif plantilla == "Podcast 🎙️": f_def, c_t, c_b, c_s, afs, aout, amv, tfs = "Arial", "#FFFFFF", "#333333", "#FFFFFF", 80, 3, 350, 60
        else: f_def, c_t, c_b, c_s, afs, aout, amv, tfs = "Impact", "#00FFFF", "#111111", "#FF00FF", 100, 4, 400, 80
        col_s_ass = hex_a_ass(c_s)
        
        st.divider()
        archivo_logo = st.file_uploader("Marca de Agua (PNG)", type=["png"])

    st.markdown("<div class='dash-header'><div class='dash-title'>✂️ Espacio de Trabajo</div></div>", unsafe_allow_html=True)
    
    tab_yt, tab_upload = st.tabs(["🔴 Opción A: Enlace YouTube", "📁 Opción B: Subir Archivo Manual"])
    with tab_yt:
        url_video = st.text_input("", placeholder="🔗 Enlace YouTube...", label_visibility="collapsed")
        btn_crear_yt = st.button("Procesar YouTube", type="primary")
    with tab_upload:
        archivo_subido = st.file_uploader("📂 Archivo", type=["mp4", "mov"], label_visibility="collapsed")
        btn_crear_up = st.button("Procesar Archivo", type="primary")

    espacio_animacion = st.empty()

    if btn_crear_yt or btn_crear_up:
        if btn_crear_yt and not url_video: st.warning("⚠️ Pega un enlace.")
        elif btn_crear_up and not archivo_subido: st.warning("⚠️ Sube archivo.")
        elif creditos < 1: st.error("❌ No tienes suficientes créditos.")
        else:
            st.session_state.mis_clips_data = []
            logo_path = "logo_tmp.png" if archivo_logo else None
            if logo_path:
                with open(logo_path, "wb") as f: f.write(archivo_logo.getbuffer())
            
            try:
                if btn_crear_yt: lista = procesar_video_youtube(url_video, cant_clips, dur_clips[0], dur_clips[1], espacio_animacion)
                else:
                    os.makedirs("archivos_brutos", exist_ok=True)
                    video_guardado_path = os.path.abspath("archivos_brutos/v.mp4")
                    espacio_animacion.markdown("<h3>📥 Subiendo...</h3>", unsafe_allow_html=True)
                    with open(video_guardado_path, "wb") as f: f.write(archivo_subido.getbuffer())
                    lista = procesar_video_local(video_guardado_path, cant_clips, dur_clips[0], dur_clips[1], espacio_animacion)
                
                # Cobramos solo los clips que se hayan podido generar realmente
                clips_reales = len(lista)
                for i, cl in enumerate(lista):
                    espacio_animacion.markdown(f"<h3>✂️ Renderizando clip {i+1}/{clips_reales}...</h3>", unsafe_allow_html=True)
                    r = renderizar_un_clip(i+1, cl["inicio"], cl["fin"], cl["titulo"], st.session_state.whisper_data, st.session_state.video_bruto_path, f"/System/Library/Fonts/Supplemental/{f_def}.ttf", tfs, c_t, c_b, afs, col_s_ass, aout, amv, logo_path)
                    if r: st.session_state.mis_clips_data.append({"id": i+1, "inicio": cl["inicio"], "fin": cl["fin"], "titulo": cl["titulo"], "ruta": r})
                
                espacio_animacion.empty()
                if st.session_state.mis_clips_data:
                    gastar_creditos(st.session_state.user_email, clips_reales)
                    st.rerun()
            except Exception as e:
                espacio_animacion.empty()
                st.error(f"Error procesando: {e}")

    if st.session_state.mis_clips_data:
        st.divider()
        st.markdown("<h3 style='margin-bottom: 20px;'>Tus clips generados</h3>", unsafe_allow_html=True)
        cols = st.columns(3)
        for i, clip in enumerate(st.session_state.mis_clips_data):
            with cols[i % 3]:
                st.markdown(f"<div class='glass-card'>", unsafe_allow_html=True)
                st.video(clip["ruta"])
                st.markdown(f"<b style='display:block; margin: 10px 0;'>{clip['titulo']}</b>", unsafe_allow_html=True)
                with open(clip["ruta"], "rb") as f: 
                    st.download_button(label="⬇️ Descargar HD", data=f, file_name=f"Clip_{clip['id']}.mp4", mime="video/mp4", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
