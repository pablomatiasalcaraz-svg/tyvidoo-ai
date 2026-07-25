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

# --- DETECTAR E INICIAR SESIÓN CON GOOGLE INMEDIATAMENTE ---
# Comprobamos los parámetros de la URL arriba del todo para evitar re-renderizados molestos
if "access_token" in st.query_params or "#access_token" in st.query_params:
    st.session_state.logged_in = True
    st.session_state.user_email = "usuario_google@tyvidoo.com"
    st.query_params.clear()

# --- CONFIGURACIÓN DE PÁGINA Y CSS PREMIUM ---
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
    
    .hero-tag { color: #888; font-size: 14px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 15px; }
    .hero-title { font-size: 4rem; font-weight: 900; line-height: 1.1; letter-spacing: -2px; margin-bottom: 20px; }
    .hero-subtitle { font-size: 1.2rem; color: #999; font-weight: 400; max-width: 650px; margin: 0 auto 30px auto; line-height: 1.5; text-align: center; }
    
    .dash-header { background: linear-gradient(135deg, #151515 0%, #0a0a0a 100%); padding: 40px; border-radius: 20px; border: 1px solid #222; margin-bottom: 30px; box-shadow: 0 20px 40px rgba(0,0,0,0.5); }
    .dash-title { font-size: 2.5rem; font-weight: 900; margin-bottom: 10px; }
    .dash-sub { color: #888; font-size: 1.1rem; }
    
    .glass-card { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 20px; padding: 20px; text-align: center; transition: all 0.3s ease; }
    .glass-card:hover { transform: translateY(-5px); border: 1px solid rgba(255,255,255,0.2); }

    .stButton>button[kind="primary"] { background-color: #ffffff !important; color: #000000 !important; font-weight: 800 !important; border-radius: 12px !important; border: none !important; font-size: 16px !important; padding: 10px 30px !important; width: 100% !important; margin-top: 5px; }
    .stButton>button[kind="primary"]:hover { transform: translateY(-2px); background-color: #eeeeee !important; }
    .stButton>button[kind="secondary"] { background-color: transparent !important; color: #fff !important; border: none !important; padding: 0 !important; margin-top: 5px; }
    .stDownloadButton>button { background-color: #222222 !important; color: #ffffff !important; font-weight: 600 !important; border-radius: 8px !important; border: 1px solid #444 !important; }
    .stDownloadButton>button:hover { background-color: #333333 !important; border: 1px solid #666 !important;}
    
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: transparent; border-radius: 4px 4px 0px 0px; gap: 1px; padding-top: 10px; padding-bottom: 10px; font-weight: 600; font-size: 16px; }
    .stTabs [aria-selected="true"] { color: #ffffff !important; border-bottom: 2px solid #ffffff !important; }
    
    .marquee-wrapper { overflow: hidden; white-space: nowrap; margin-top: 40px; padding: 20px 0; border-top: 1px solid #111; border-bottom: 1px solid #111;}
    .marquee-content { display: inline-block; animation: marquee 25s linear infinite; }
    .review-card { display: inline-block; background: rgba(255,255,255,0.03); padding: 15px 25px; border-radius: 30px; border: 1px solid rgba(255,255,255,0.05); margin-right: 20px; font-size: 14px; color: #ccc; }
    .review-card b { color: #fff; }
    @keyframes marquee { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }

    .section-title { font-size: 2.5rem; font-weight: 800; text-align: center; margin: 80px 0 20px 0; letter-spacing: -1px; }
    .section-subtitle { text-align: center; color: #888; margin-bottom: 40px; font-size: 1.1rem; }
    
    .feature-card, .info-card { background: #0a0a0a; border: 1px solid #222; border-radius: 20px; padding: 30px; height: 100%; }
    .pricing-card { background: #0a0a0a; border: 1px solid #222; border-radius: 20px; padding: 40px 30px; text-align: center; position: relative; height: 100%; }
    .pricing-card.pro { border: 2px solid #ffffff; background: linear-gradient(180deg, #111 0%, #050505 100%); transform: scale(1.05); z-index: 10;}
    .badge { position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: #fff; color: #000; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }
    .price { font-size: 3rem; font-weight: 900; margin: 20px 0; }
    .price span { font-size: 1rem; color: #666; font-weight: normal; }
    .pricing-features { text-align: left; margin: 30px 0; color: #aaa; font-size: 14px; line-height: 2; }
    .video-mockup { background: #111; border-radius: 20px; padding: 10px; border: 1px solid #333; text-align: center; }
    .video-mockup img { border-radius: 10px; width: 100%; object-fit: cover; aspect-ratio: 9/16; opacity: 0.8;}
    
    .clip-preview-container { border: 1px solid #333; border-radius: 10px; padding: 15px; margin-bottom: 10px; background: rgba(255,255,255,0.02); }
    
    /* Botón Premium de Google con SVG Oficial */
    .google-custom-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        background-color: #ffffff;
        color: #1f2937;
        font-weight: 600;
        font-size: 16px;
        font-family: 'Inter', sans-serif;
        border-radius: 12px;
        padding: 12px 24px;
        text-decoration: none;
        border: 1px solid #e5e7eb;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        transition: background-color 0.2s, transform 0.1s;
        width: 100%;
        box-sizing: border-box;
        margin-top: 15px;
        cursor: pointer;
    }
    .google-custom-btn:hover { background-color: #f9fafb; transform: translateY(-1px); }
    .google-custom-btn svg { width: 20px; height: 20px; margin-right: 12px; }
    </style>
""", unsafe_allow_html=True)

# HACK INYECTADO: Si detecta la respuesta de Supabase mediante Hash (#), la redirige al instante como parámetro limpio (?)
import streamlit.components.v1 as components
components.html("""
    <script>
        if (window.parent.location.hash.includes("access_token")) {
            var newUrl = window.parent.location.href.replace('#', '?');
            window.parent.location.replace(newUrl);
        }
    </script>
""", height=0, width=0)

# --- INICIALIZAR MEMORIA ---
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
    if email == "usuario_google@tyvidoo.com": return 100 
    try:
        respuesta = supabase.table("usuarios").select("creditos").eq("email", email).execute()
        if len(respuesta.data) > 0: return respuesta.data[0]["creditos"]
        return 0
    except: return 0

def gastar_creditos(email, cantidad):
    email = email.lower().strip()
    if email == "usuario_google@tyvidoo.com": return True 
    try:
        respuesta = supabase.table("usuarios").select("creditos").eq("email", email).execute()
        if len(respuesta.data) > 0 and respuesta.data[0]["creditos"] >= cantidad:
            supabase.table("usuarios").update({"creditos": respuesta.data[0]["creditos"] - cantidad}).eq("email", email).execute()
            return True
        return False
    except: return False

# --- MOTOR DE EDICIÓN ---
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

def procesar_video_youtube(url, cant, d_min, d_max, prog, modo_prueba=False):
    for d in ["archivos_brutos", "clips_finales"]:
        os.makedirs(d, exist_ok=True)
        for a in os.listdir(d): 
            if os.path.isfile(os.path.join(d, a)): os.remove(os.path.join(d, a))

    v = os.path.abspath("archivos_brutos/v.mp4")
    a = os.path.abspath("archivos_brutos/a.mp3")
    
    prog.markdown("<h3>📥 Descargando vídeo de YouTube...</h3>", unsafe_allow_html=True)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': v,
        'geo_bypass': True,
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
    
    subprocess.run(["ffmpeg", "-y", "-i", v, "-b:a", "32k", "-map", "a", a], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return procesar_ia(a, v, cant, d_min, d_max, prog)

def procesar_video_local(archivo_path, cant, d_min, d_max, prog, modo_prueba=False):
    for d in ["archivos_brutos", "clips_finales"]:
        os.makedirs(d, exist_ok=True)
        for archivo in os.listdir(d): 
            if os.path.isfile(os.path.join(d, archivo)) and archivo != "v.mp4": os.remove(os.path.join(d, archivo))

    a = os.path.abspath("archivos_brutos/a.mp3")
    subprocess.run(["ffmpeg", "-y", "-i", archivo_path, "-b:a", "32k", "-map", "a", a], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return procesar_ia(a, archivo_path, cant, d_min, d_max, prog)

def procesar_ia(a, v, cant, d_min, d_max, prog):
    prog.markdown("<h3>🧠 Transcribiendo con Inteligencia Artificial...</h3>", unsafe_allow_html=True)
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

    transcript_con_tiempos = ""
    palabras = res_w.get("words", [])
    for i in range(0, len(palabras), 15):
        chunk = palabras[i:i+15]
        if chunk:
            transcript_con_tiempos += f"[{chunk[0]['start']:.1f}s - {chunk[-1]['end']:.1f}s] " + " ".join([p['word'] for p in chunk]) + "\n"
    
    prompt_completo = f"""Actúa como un experto editor de TikTok. Extrae {cant} clips virales. Devuelve un JSON EXACTO: {{"clips": [{{"inicio": 10.5, "fin": 42.1, "titulo": "TITULO"}}]}}"""
    
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini", messages=[{"role": "system", "content": prompt_completo}, {"role": "user", "content": transcript_con_tiempos}], response_format={"type": "json_object"}
        )
        clips = json.loads(res.choices[0].message.content).get("clips", [])
    except:
        clips = []
        
    clips_finales = []
    for c in clips:
        ini, fin, tit = float(c.get("inicio", 0)), float(c.get("fin", d_min)), str(c.get("titulo", "VIRAL"))
        clips_finales.append({"inicio": round(ini, 1), "fin": round(fin, 1), "titulo": tit.upper()})
    return clips_finales[:cant]

def renderizar_un_clip(num, ini, fin, tit, res_w, vid, font, tit_fs, col_tit, col_bg, ass_fs, col_sub, out, mv, logo):
    ts = int(time.time() * 1000)
    srt = f"archivos_brutos/sub_{ts}.srt"
    out_vid = f"clips_finales/clip_{ts}.mp4"
    generar_srt_por_palabras(res_w, ini, fin, srt)
    tit_safe = re.sub(r'[^\w\s]', '', tit).upper()
    
    f_base = "[0:v]split=2[original][copy];[copy]scale=-1:1920,crop=1080:1920,boxblur=20:20[bg];[original]scale=1080:-1[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[m_base];"
    cmd = ["ffmpeg", "-y", "-ss", str(ini), "-to", str(fin), "-i", vid]
    f_base += "[m_base]null[m];"

    estilo_srt = f"PlayResX=1080,PlayResY=1920,Encoding=UTF-8,FontSize={ass_fs},PrimaryColour={col_sub},OutlineColour=&H40000000&,BorderStyle=1,Outline={out},Alignment=2,MarginV={mv},Bold=1"
    f_txt = f"[m]drawtext=text=' {tit_safe} ':fontfile={font}:fontsize={tit_fs}:fontcolor={col_tit}:x=(w-text_w)/2:y=220:box=1:boxcolor={col_bg}@0.95:boxborderw=20:enable=between(t\\,0\\,5)[w_txt];[w_txt]subtitles=filename={srt}:force_style='{estilo_srt}'[f]"
    
    cmd.extend(["-filter_complex", f_base + f_txt, "-map", "[f]", "-map", "0:a", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", out_vid])
    subprocess.run(cmd, capture_output=True)
    return out_vid if os.path.exists(out_vid) else None

# ==========================================
# RENDERIZADO DE VISTAS
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
        st.markdown("""
        <div style='text-align: center; margin-top: 20px;'>
            <p class='hero-tag'>#1 AI VIDEO CLIPPING TOOL</p>
            <h1 class='hero-title'>De 1 vídeo largo a 10 clips virales.<br>Automáticamente.</h1>
            <p class='hero-subtitle'>Tyvidoo convierte tus vídeos y podcasts en Shorts listos para publicar en segundos.</p>
        </div>
        """, unsafe_allow_html=True)

        col_pad1, col_center, col_pad2 = st.columns([1, 8, 1])
        with col_center:
            st.markdown("<div style='background: rgba(255,255,255,0.03); border: 1px dashed rgba(255,255,255,0.2); border-radius: 20px; padding: 20px; text-align: center;'><h3>Empieza a crear</h3>", unsafe_allow_html=True)
            if st.button("🚀 Iniciar Sesión y Generar Clips", type="primary", use_container_width=True):
                st.session_state.show_auth = True
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    else:
        st.markdown("<div style='text-align: center; margin-bottom: 30px;'><h2 style='font-weight: 800;'>Comienza a crear</h2></div>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            # BOTÓN OFICIAL DE GOOGLE CON SVG VECTORIZADO DE ALTA CALIDAD
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
            
            st.markdown("<p style='text-align:center; margin:20px 0; color:#555;'>— O CON TU CORREO —</p>", unsafe_allow_html=True)
            
            tab1, tab2 = st.tabs(["📝 Registrarse", "🔐 Iniciar Sesión"])
            with tab1:
                with st.form("reg_form"):
                    e_reg, p_reg = st.text_input("Correo"), st.text_input("Contraseña", type="password")
                    if st.form_submit_button("Crear cuenta", type="primary", use_container_width=True):
                        exito, msj = registrar_usuario(e_reg, p_reg)
                        if exito: st.success("✅ Cuenta creada. Ya puedes iniciar sesión.")
                        else: st.error(f"⚠️ Error: {msj}")
            with tab2:
                with st.form("log_form"):
                    e_log, p_log = st.text_input("Correo"), st.text_input("Contraseña", type="password")
                    if st.form_submit_button("Entrar", type="primary", use_container_width=True):
                        if login_usuario(e_log, p_log):
                            st.session_state.logged_in, st.session_state.user_email = True, e_log.lower().strip()
                            st.session_state.show_auth = False
                            st.rerun()
                        else: st.error("❌ Credenciales incorrectas.")
            if st.button("← Volver", use_container_width=True):
                st.session_state.show_auth = False
                st.rerun()

else:
    # VISTA PANEL DE TRABAJO (SI EL USUARIO YA ESTÁ LOGUEADO)
    creditos = obtener_creditos(st.session_state.user_email)
    
    with st.sidebar:
        st.markdown("<h2 style='font-weight:900;'>✂️ Tyvidoo</h2>", unsafe_allow_html=True)
        st.caption(st.session_state.user_email)
        st.markdown(f"<div style='background: rgba(255, 255, 255, 0.05); border-radius: 10px; padding: 15px; text-align: center; margin: 20px 0;'><h2 style='margin:0; font-weight: 800;'>{creditos} <span style='font-size: 14px; color: #888;'>créditos</span></h2></div>", unsafe_allow_html=True)
        
        menu_principal = st.radio("Menú", ["✂️ Crear Clips", "📚 Mi Biblioteca"], label_visibility="collapsed")
        
        st.divider()
        if menu_principal == "✂️ Crear Clips":
            cant_clips = st.slider("Clips a extraer", 1, 10, 3)
            dur_clips = st.slider("Duración aprox. (seg)", 15, 60, (20, 40))
            
            st.divider()
            st.markdown("<b>🎨 Diseño de Subtítulos</b>", unsafe_allow_html=True)
            opciones_pl = ["Hormozi 💛", "Podcast 🎙️", "Neón 👾"]
            st.session_state.plantilla = st.selectbox("Elige estilo", opciones_pl, index=opciones_pl.index(st.session_state.plantilla))
            
            plantilla = st.session_state.plantilla
            if plantilla == "Hormozi 💛": f_def, c_t, c_b, c_s, afs, aout, amv, tfs = "Impact", "#FFFFFF", "#000000", "#FFFF00", 110, 4, 450, 60
            elif plantilla == "Podcast 🎙️": f_def, c_t, c_b, c_s, afs, aout, amv, tfs = "Arial", "#FFFFFF", "#333333", "#FFFFFF", 80, 3, 350, 50
            else: f_def, c_t, c_b, c_s, afs, aout, amv, tfs = "Impact", "#00FFFF", "#111111", "#FF00FF", 100, 4, 400, 60
            col_s_ass = hex_a_ass(c_s)
        
        st.divider()
        if st.button("🗑️ Eliminar mi cuenta", use_container_width=True): st.session_state.show_delete_confirm = True
            
        if st.session_state.get("show_delete_confirm", False):
            st.warning("⚠️ ¿Estás completamente seguro?")
            if st.button("Sí, borrar definitivamente", type="primary", use_container_width=True):
                try:
                    supabase.table("historial_clips").delete().eq("email_usuario", st.session_state.user_email).execute()
                    supabase.table("usuarios").delete().eq("email", st.session_state.user_email).execute()
                except: pass
                st.session_state.logged_in = False
                st.session_state.user_email = ""
                st.session_state.show_delete_confirm = False
                st.rerun()
            if st.button("Cancelar", use_container_width=True):
                st.session_state.show_delete_confirm = False
                st.rerun()

        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.logged_in = False; st.session_state.user_email = ""; st.rerun()

    st.markdown("<div class='dash-header'><div class='dash-title'>✂️ Espacio de Trabajo</div></div>", unsafe_allow_html=True)
    
    if menu_principal == "✂️ Crear Clips":
        espacio_animacion = st.empty()

        if not st.session_state.mis_clips_data:
            modo_subida = st.radio("Origen del vídeo", ["🔴 Enlace YouTube", "📁 Archivo Manual"], horizontal=True)
            
            if modo_subida == "🔴 Enlace YouTube":
                url_video = st.text_input("", placeholder="🔗 Pega tu enlace de YouTube aquí...", label_visibility="collapsed")
                btn_crear = st.button("🚀 Procesar y Crear Clips", type="primary")
                archivo_subido = None
            else:
                archivo_subido = st.file_uploader("📂 Archivo Local", type=["mp4", "mov"], label_visibility="collapsed")
                btn_crear = st.button("🚀 Procesar y Crear Clips", type="primary")
                url_video = None

            if btn_crear:
                if modo_subida == "🔴 Enlace YouTube" and not url_video: st.warning("⚠️ Introduce un enlace.")
                elif modo_subida == "📁 Archivo Manual" and not archivo_subido: st.warning("⚠️ Sube un archivo.")
                else:
                    try:
                        if url_video: 
                            clips_a_renderizar = procesar_video_youtube(url_video, cant_clips, dur_clips[0], dur_clips[1], espacio_animacion)
                        else:
                            os.makedirs("archivos_brutos", exist_ok=True)
                            v_path = os.path.abspath("archivos_brutos/v.mp4")
                            with open(v_path, "wb") as f: f.write(archivo_subido.getbuffer())
                            clips_a_renderizar = procesar_video_local(v_path, cant_clips, dur_clips[0], dur_clips[1], espacio_animacion)
                        
                        for i, cl in enumerate(clips_a_renderizar):
                            espacio_animacion.markdown(f"<h3>✂️ Renderizando clip {i+1}/{len(clips_a_renderizar)}...</h3>", unsafe_allow_html=True)
                            r = renderizar_un_clip(i+1, cl["inicio"], cl["fin"], cl["titulo"], st.session_state.whisper_data, st.session_state.video_bruto_path, f"/System/Library/Fonts/Supplemental/{f_def}.ttf", tfs, c_t, c_b, afs, col_s_ass, aout, amv, None)
                            if r: 
                                st.session_state.mis_clips_data.append({"id": i+1, "titulo": cl["titulo"], "ruta": r})
                                try:
                                    n_nube = f"clip_{int(time.time())}_{i}.mp4"
                                    with open(r, "rb") as f: supabase.storage.from_("clips").upload(n_nube, f.read(), {"content-type": "video/mp4"})
                                    url_nube = supabase.storage.from_("clips").get_public_url(n_nube)
                                    supabase.table("historial_clips").insert({"email_usuario": st.session_state.user_email, "titulo_clip": cl["titulo"], "ruta_archivo": url_nube}).execute()
                                except: pass
                        
                        espacio_animacion.empty()
                        if len(st.session_state.mis_clips_data) > 0:
                            gastar_creditos(st.session_state.user_email, len(st.session_state.mis_clips_data))
                            st.rerun()
                    except Exception as e:
                        espacio_animacion.empty()
                        st.error(f"Error: {e}")

        elif st.session_state.mis_clips_data:
            st.success("✅ ¡Tus clips virales están listos!")
            if st.button("Crear nuevo proyecto", type="primary"):
                st.session_state.mis_clips_data = []
                st.rerun()
            
            cols = st.columns(3)
            for i, clip in enumerate(st.session_state.mis_clips_data):
                with cols[i % 3]:
                    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
                    st.video(clip["ruta"])
                    st.markdown(f"<b>{clip['titulo']}</b>", unsafe_allow_html=True)
                    with open(clip["ruta"], "rb") as f: st.download_button("Descargar MP4", f, file_name=f"clip_{i}.mp4", mime="video/mp4", use_container_width=True, key=f"d_{i}")
                    st.markdown("</div>", unsafe_allow_html=True)

    elif menu_principal == "📚 Mi Biblioteca":
        st.markdown("<h3>Tus clips en la nube</h3>", unsafe_allow_html=True)
        try:
            res_bib = supabase.table("historial_clips").select("*").eq("email_usuario", st.session_state.user_email).order("fecha_creacion", desc=True).execute()
            if not res_bib.data: st.info("Aún no tienes clips en tu biblioteca.")
            else:
                cols_b = st.columns(3)
                for idx, b_clip in enumerate(res_bib.data):
                    with cols_b[idx % 3]:
                        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
                        st.video(b_clip['ruta_archivo'])
                        st.markdown(f"<b>{b_clip['titulo_clip']}</b>", unsafe_allow_html=True)
                        st.link_button("Descargar", b_clip['ruta_archivo'], use_container_width=True)
                        st.markdown("</div>", unsafe_allow_html=True)
        except: st.error("Error al conectar con la biblioteca.")
