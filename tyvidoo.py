import streamlit as st
import os
import json
import subprocess
import whisper
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
    API_KEY = st.secrets["OPENAI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception as e:
    st.error("⚠️ Faltan las claves en .streamlit/secrets.toml")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CONFIGURACIÓN DE PÁGINA Y CSS PREMIUM ---
st.set_page_config(page_title="Tyvidoo | #1 AI Video Clipping Tool", page_icon="✂️", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #050505; color: #ffffff; }
    header {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container { padding-top: 1rem !important; max-width: 1200px; padding-bottom: 5rem;}
    
    /* NAV */
    .top-nav {
        display: flex; justify-content: space-between; align-items: center;
        padding: 20px 0; border-bottom: 1px solid rgba(255,255,255,0.05); margin-bottom: 40px;
    }
    .nav-logo {
        font-size: 24px; font-weight: 900; letter-spacing: -1px;
        background: linear-gradient(90deg, #FFFFFF, #AAAAAA);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    
    /* HERO */
    .hero-tag { color: #888; font-size: 14px; font-weight: 600; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 15px; }
    .hero-title { font-size: 4rem; font-weight: 900; line-height: 1.1; letter-spacing: -2px; margin-bottom: 20px; }
    .hero-subtitle { 
        font-size: 1.2rem; color: #999; font-weight: 400; max-width: 650px; 
        margin: 0 auto 30px auto; line-height: 1.5; text-align: center; 
    }
    
    /* DASHBOARD PREMIUM */
    .dash-header {
        background: linear-gradient(135deg, #151515 0%, #0a0a0a 100%);
        padding: 40px; border-radius: 20px; border: 1px solid #222; margin-bottom: 40px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.5);
    }
    .dash-title { font-size: 2.5rem; font-weight: 900; margin-bottom: 10px; }
    .dash-sub { color: #888; font-size: 1.1rem; }
    
    .glass-card {
        background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05);
        border-radius: 20px; padding: 20px; text-align: center; transition: all 0.3s ease;
    }
    .glass-card:hover { transform: translateY(-5px); border: 1px solid rgba(255,255,255,0.2); }

    /* FIX INPUTS Y BOTONES */
    .stButton>button[kind="primary"] {
        background-color: #ffffff !important; color: #000000 !important; font-weight: 800 !important;
        border-radius: 12px !important; border: none !important; font-size: 16px !important; 
        padding: 10px 30px !important; width: 100% !important; margin-top: 5px;
    }
    .stButton>button[kind="primary"]:hover { transform: translateY(-2px); background-color: #eeeeee !important; }
    
    /* REVIEWS MARQUEE */
    .marquee-wrapper { overflow: hidden; white-space: nowrap; margin-top: 40px; padding: 20px 0; border-top: 1px solid #111; border-bottom: 1px solid #111;}
    .marquee-content { display: inline-block; animation: marquee 25s linear infinite; }
    .review-card {
        display: inline-block; background: rgba(255,255,255,0.03); padding: 15px 25px; 
        border-radius: 30px; border: 1px solid rgba(255,255,255,0.05); margin-right: 20px; font-size: 14px; color: #ccc;
    }
    .review-card b { color: #fff; }
    @keyframes marquee { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }

    /* SECCIONES */
    .section-title { font-size: 2.5rem; font-weight: 800; text-align: center; margin: 80px 0 20px 0; letter-spacing: -1px; }
    .section-subtitle { text-align: center; color: #888; margin-bottom: 40px; font-size: 1.1rem; }
    
    .feature-card, .info-card {
        background: #0a0a0a; border: 1px solid #222; border-radius: 20px; padding: 30px; height: 100%;
    }
    .pricing-card {
        background: #0a0a0a; border: 1px solid #222; border-radius: 20px; padding: 40px 30px; 
        text-align: center; position: relative; height: 100%;
    }
    .pricing-card.pro { border: 2px solid #ffffff; background: linear-gradient(180deg, #111 0%, #050505 100%); transform: scale(1.05); z-index: 10;}
    .badge { position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: #fff; color: #000; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }
    .price { font-size: 3rem; font-weight: 900; margin: 20px 0; }
    .price span { font-size: 1rem; color: #666; font-weight: normal; }
    .pricing-features { text-align: left; margin: 30px 0; color: #aaa; font-size: 14px; line-height: 2; }
    
    /* EJEMPLOS VIDEOS */
    .video-mockup {
        background: #111; border-radius: 20px; padding: 10px; border: 1px solid #333; text-align: center;
    }
    .video-mockup img { border-radius: 10px; width: 100%; object-fit: cover; aspect-ratio: 9/16; opacity: 0.8;}
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
        return True
    except: return False

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
        for seg in res["segments"]:
            if "words" in seg:
                for p in seg["words"]:
                    if p["end"] > ini and p["start"] < fin:
                        start_aj = max(0.0, p["start"]-ini)
                        end_aj = min(fin-ini, p["end"]-ini)
                        if end_aj > start_aj:
                            caracteres_malos = " ,.?!:;()'\"[]{}"
                            palabra = p['word'].strip(caracteres_malos).upper()
                            f.write(f"{c}\n{segundos_a_srt(start_aj)} --> {segundos_a_srt(end_aj)}\n{palabra}\n\n")
                            c += 1

def procesar_video_master(url, cant, d_min, d_max, prog):
    for d in ["archivos_brutos", "clips_finales"]:
        os.makedirs(d, exist_ok=True)
        for a in os.listdir(d): 
            if os.path.isfile(os.path.join(d, a)): os.remove(os.path.join(d, a))

    v = os.path.abspath("archivos_brutos/v.mp4")
    a = os.path.abspath("archivos_brutos/a.mp3")
    
    prog.markdown("<div class='loader-container'><div class='pulse-ring'></div><h3>📥 Saltando cortafuegos de YouTube...</h3></div>", unsafe_allow_html=True)
    
    # -------------------------------------------------------------
    # NUEVO PARCHE ANTI-403: Forzamos cliente móvil (Android/iOS)
    # y evitamos las conexiones IPv6 (donde YouTube bloquea más la nube)
    # -------------------------------------------------------------
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': v,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'ios']}},
        'source_address': '0.0.0.0' # Fuerza a usar IPv4
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl: 
        ydl.download([url])
        
    subprocess.run(["ffmpeg", "-y", "-i", v, "-q:a", "0", "-map", "a", a], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    prog.markdown("<div class='loader-container'><div class='pulse-ring'></div><h3>🧠 Transcribiendo...</h3></div>", unsafe_allow_html=True)
    res_w = whisper.load_model("base").transcribe(a, task="transcribe", word_timestamps=True)
    st.session_state.whisper_data = res_w
    st.session_state.video_bruto_path = v
    if res_w["segments"]: st.session_state.duracion_max_video = res_w["segments"][-1]["end"]

    prog.markdown("<div class='loader-container'><div class='pulse-ring'></div><h3>🎯 Buscando viralidad...</h3></div>", unsafe_allow_html=True)
    
    prompt_1 = f"Actúa como editor experto. Extrae EXACTAMENTE {cant} clips. DURACIÓN: {d_min}-{d_max} segundos. "
    prompt_2 = f"NO cortes en {d_min}s por pereza, busca el final lógico. Títulos clickbait MAX 5 PALABRAS. Sin emojis. JSON exacto:\n"
    prompt_3 = '{"clips": [{"inicio": 10.5, "fin": 32.0, "titulo": "TITULO"}]}'
    prompt_completo = prompt_1 + prompt_2 + prompt_3
    
    res = OpenAI(api_key=API_KEY).chat.completions.create(
        model="gpt-4o-mini", 
        messages=[
            {"role": "system", "content": prompt_completo}, 
            {"role": "user", "content": res_w['text']}
        ], 
        response_format={"type": "json_object"}
    )
    
    clips = json.loads(res.choices[0].message.content).get("clips", [])
    while len(clips) > 0 and len(clips) < cant: clips.append(clips[-1].copy())
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

    estilo_srt = f"Encoding=UTF-8,FontSize={ass_fs},PrimaryColour={col_sub},OutlineColour=&H40000000&,BorderStyle=1,Outline={out},Alignment=2,MarginV={mv},Bold=1"
    
    f_txt = (
        f"[m]drawtext=text=' {tit_safe} ':fontfile={font}:fontsize={tit_fs}:fontcolor={col_tit}:"
        f"x=(w-text_w)/2:y=220:box=1:boxcolor={col_bg}@0.95:boxborderw=20:enable=between(t\\,0\\,5)[w_txt];"
        f"[w_txt]subtitles=filename={srt}:force_style='{estilo_srt}'[f]"
    )
    
    cmd.extend([
        "-filter_complex", f_base + f_txt, 
        "-map", "[f]", "-map", "0:a", 
        "-c:v", "libx264", "-c:a", "aac", 
        "-movflags", "+faststart", out_vid
    ])
    subprocess.run(cmd, capture_output=True)
    return out_vid if os.path.exists(out_vid) else None


# ==========================================
# VISTA 1: LANDING PAGE (NO LOGUEADO)
# ==========================================
if not st.session_state.logged_in:
    
    col_logo, col_space, col_login = st.columns([2, 5, 1])
    with col_logo:
        st.markdown("<div class='top-nav'><div class='nav-logo'>✂️ Tyvidoo AI</div></div>", unsafe_allow_html=True)
    with col_login:
        st.write("")
        if st.button("Sign In", use_container_width=True):
            st.session_state.show_auth = True
            st.rerun()

    if not st.session_state.show_auth:
        h_html_1 = "<div style='text-align: center; margin-top: 20px;'><p class='hero-tag'>#1 AI VIDEO CLIPPING TOOL</p>"
        h_html_2 = "<h1 class='hero-title'>1 video largo, clips virales infinitos.<br>Crea 10x más rápido.</h1>"
        h_html_3 = "<p class='hero-subtitle'>Tyvidoo convierte tus vídeos largos de YouTube en Shorts listos para publicar, con subtítulos dinámicos de estilo Hormozi.</p></div>"
        st.markdown(h_html_1 + h_html_2 + h_html_3, unsafe_allow_html=True)

        col_pad1, col_center, col_pad2 = st.columns([1, 8, 1])
        with col_center:
            url_demo = st.text_input("Enlace del vídeo original", placeholder="🔗 Pega tu enlace de YouTube aquí...")
            c_ed1, c_ed2 = st.columns(2)
            with c_ed1:
                st.slider("Número de Clips deseados", 5, 30, 10)
            with c_ed2:
                st.selectbox("Estilo Visual", ["Hormozi 💛", "Podcast 🎙️", "Neón Gaming 👾"])
            
            st.write("")
            if st.button("🚀 Generar mis clips ahora", type="primary", use_container_width=True):
                st.session_state.show_auth = True
                st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)

        m_1 = "<div class='marquee-wrapper'><div class='marquee-content'>"
        m_2 = "<div class='review-card'>⭐⭐⭐⭐⭐ \"Me ahorra 10 horas de edición a la semana\" - <b>@creador_es</b></div>"
        m_3 = "<div class='review-card'>⭐⭐⭐⭐⭐ \"Mis vistas en TikTok se multiplicaron x5\" - <b>@marketing_pro</b></div>"
        m_4 = "<div class='review-card'>⭐⭐⭐⭐⭐ \"Subtítulos estilo Hormozi automáticos. Magia.\" - <b>@podcast_latam</b></div>"
        m_5 = "<div class='review-card'>⭐⭐⭐⭐⭐ \"Mejor y más barato que la competencia\" - <b>@streamer_xd</b></div>"
        m_6 = m_2 + m_3 + m_4 + m_5 + "</div></div>"
        st.markdown(m_1 + m_2 + m_3 + m_4 + m_5 + m_6, unsafe_allow_html=True)

        st.markdown("<div class='section-title'>Resultados de calidad profesional 🎬</div>", unsafe_allow_html=True)
        st.markdown("<div class='section-subtitle'>No edites a ciegas. Así se verán tus clips generados.</div>", unsafe_allow_html=True)
        
        c_vid1, c_vid2, c_vid3 = st.columns(3)
        img_hormozi = "https://images.unsplash.com/photo-1557804506-669a67965ba0?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&h=700&q=80"
        img_podcast = "https://images.unsplash.com/photo-1581368135153-a506cf13b1e1?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&h=700&q=80"
        img_neon = "https://images.unsplash.com/photo-1542751371-adc38448a05e?ixlib=rb-4.0.3&auto=format&fit=crop&w=400&h=700&q=80"
        
        with c_vid1: st.markdown(f"<div class='video-mockup'><img src='{img_hormozi}'><h4 style='margin-top:15px;'>Estilo Hormozi 💛</h4></div>", unsafe_allow_html=True)
        with c_vid2: st.markdown(f"<div class='video-mockup'><img src='{img_podcast}'><h4 style='margin-top:15px;'>Estilo Podcast 🎙️</h4></div>", unsafe_allow_html=True)
        with c_vid3: st.markdown(f"<div class='video-mockup'><img src='{img_neon}'><h4 style='margin-top:15px;'>Estilo Neón 👾</h4></div>", unsafe_allow_html=True)

        st.markdown("<div class='section-title'>Todo lo que necesitas para crecer 📈</div>", unsafe_allow_html=True)
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1: st.markdown("<div class='feature-card'><h2>🎯</h2><h4>Curación con IA</h4><p style='color:#888;'>Nuestra IA detecta las partes con más retención, humor o tensión para asegurar el hook perfecto.</p></div>", unsafe_allow_html=True)
        with f_col2: st.markdown("<div class='feature-card'><h2>✍️</h2><h4>Subtítulos Dinámicos</h4><p style='color:#888;'>Generamos subtítulos precisos palabra por palabra estilo Alex Hormozi o el que tú elijas.</p></div>", unsafe_allow_html=True)
        with f_col3: st.markdown("<div class='feature-card'><h2>🎬</h2><h4>Editor Profesional</h4><p style='color:#888;'>Ajusta el inicio y fin al milísegundo, pon tu propio logo de agua y descarga en ZIP.</p></div>", unsafe_allow_html=True)

        st.markdown("<div class='section-title'>Planes simples y transparentes 💳</div>", unsafe_allow_html=True)
        
        col_tog1, col_tog2, col_tog3 = st.columns([3, 2, 3])
        with col_tog2:
            st.markdown("<div style='margin-bottom: 40px; text-align: center;'>", unsafe_allow_html=True)
            facturacion_anual = st.toggle("Facturación Anual (Ahorra 50%)", value=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
        precio_pro = "9" if facturacion_anual else "19"
        precio_agencia = "24" if facturacion_anual else "49"
        texto_mes = "/mes (cobrado anualmente)" if facturacion_anual else "/mes"

        p_col1, p_col2, p_col3 = st.columns(3)
        with p_col1:
            st.markdown(f"""
            <div class='pricing-card'>
                <h3>Starter</h3><div class='price'>$0<span>/mes</span></div>
                <div class='pricing-features'>✔️ <b>30 créditos gratis</b><br>✔️ Exportación a 720p<br>✔️ Marca de agua de Tyvidoo<br>❌ Soporte prioritario</div>
                <button style="width:100%; padding:15px; border-radius:10px; background:transparent; border:1px solid #555; color:white;">Empezar Gratis</button>
            </div>
            """, unsafe_allow_html=True)
        
        with p_col2:
            st.markdown(f"""
            <div class='pricing-card pro'>
                <div class='badge'>MÁS POPULAR</div>
                <h3>Creator Pro</h3><div class='price'>${precio_pro}<span>{texto_mes}</span></div>
                <div class='pricing-features'>✔️ <b>200 minutos al mes</b><br>✔️ Calidad 1080p HD<br>✔️ Sin marca de agua<br>✔️ Plantillas personalizadas</div>
                <button style="width:100%; padding:15px; border-radius:10px; background:white; border:none; color:black; font-weight:bold;">Elegir Pro</button>
            </div>
            """, unsafe_allow_html=True)

        with p_col3:
            st.markdown(f"""
            <div class='pricing-card'>
                <h3>Agencia</h3><div class='price'>${precio_agencia}<span>{texto_mes}</span></div>
                <div class='pricing-features'>✔️ <b>1000 minutos al mes</b><br>✔️ Calidad 1080p HD<br>✔️ Acceso a la API<br>✔️ Soporte prioritario 24/7</div>
                <button style="width:100%; padding:15px; border-radius:10px; background:transparent; border:1px solid #555; color:white;">Contactar Ventas</button>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div class='section-title'>Conoce Tyvidoo 🤝</div>", unsafe_allow_html=True)
        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.markdown("""
            <div class='info-card'>
                <h3>👋 Nuestra Misión</h3>
                <p style="color:#888; line-height: 1.6; margin-top: 15px;">Tyvidoo nació para democratizar la creación de contenido. Creemos que no necesitas pagar miles de euros a una agencia para tener clips virales de calidad.</p>
            </div>
            """, unsafe_allow_html=True)
        with info_col2:
            st.markdown("""
            <div class='info-card'>
                <h3>🎧 Soporte 24/7</h3>
                <p style="color:#888; line-height: 1.6; margin-top: 15px;">No te dejamos solo frente a una máquina. Si tienes dudas, estamos aquí.<br><br>📩 Escríbenos a: <b>soporte@tyvidoo.com</b></p>
            </div>
            """, unsafe_allow_html=True)

    else:
        st.markdown("<div style='text-align: center; margin-bottom: 30px;'><h2 style='font-weight: 800;'>Comienza a crear</h2></div>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            tab1, tab2 = st.tabs(["📝 Registrarse", "🔐 Iniciar Sesión"])
            with tab1:
                with st.form("reg_form"):
                    e_reg = st.text_input("Correo")
                    p_reg = st.text_input("Contraseña", type="password")
                    if st.form_submit_button("Crear cuenta (30 créditos gratis)", type="primary", use_container_width=True):
                        if registrar_usuario(e_reg, p_reg): st.success("✅ Creada. Inicia sesión.")
                        else: st.error("⚠️ Error al crear.")
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

# ==========================================
# VISTA 2: PANEL DE CONTROL (LOGUEADO)
# ==========================================
else:
    creditos = obtener_creditos(st.session_state.user_email)
    
    with st.sidebar:
        st.markdown("<h2 style='font-weight:900;'>✂️ Tyvidoo</h2>", unsafe_allow_html=True)
        st.caption(st.session_state.user_email)
        
        st.markdown(f"""
        <div style="background: rgba(255, 255, 255, 0.05); border-radius: 10px; padding: 15px; text-align: center; margin: 20px 0;">
            <h2 style="margin:0; font-weight: 800;">{creditos} <span style="font-size: 14px; color: #888;">créditos</span></h2>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.rerun()
            
        st.divider()
        st.markdown("<b>⚙️ Configuración del Motor</b>", unsafe_allow_html=True)
        cant_clips = st.slider("Clips a extraer", 1, 30, 10)
        dur_clips = st.slider("Duración aprox. (seg)", 15, 90, (20, 45))
        plantilla = st.selectbox("Estilo Visual", ["Hormozi 💛", "Podcast 🎙️", "Neón 👾"])
        
        if plantilla == "Hormozi 💛": f_def, c_t, c_b, c_s, afs, aout, amv, tfs = "Impact", "#FFFFFF", "#000000", "#FFFF00", 18, 2, 120, 45
        elif plantilla == "Podcast 🎙️": f_def, c_t, c_b, c_s, afs, aout, amv, tfs = "Arial", "#FFFFFF", "#333333", "#FFFFFF", 12, 1, 80, 35
        else: f_def, c_t, c_b, c_s, afs, aout, amv, tfs = "Impact", "#00FFFF", "#111111", "#FF00FF", 16, 2, 100, 45
        col_s_ass = hex_a_ass(c_s)
        
        st.divider()
        archivo_logo = st.file_uploader("Marca de Agua (PNG)", type=["png"])

    st.markdown("""
    <div class='dash-header'>
        <div class='dash-title'>✂️ Nuevo Proyecto</div>
        <div class='dash-sub'>Pega el enlace de un vídeo de YouTube y deja que la IA trabaje por ti.</div>
    </div>
    """, unsafe_allow_html=True)
    
    col_input, col_btn = st.columns([4, 1])
    with col_input:
        url_video = st.text_input("", placeholder="🔗 Pegar URL de YouTube...", label_visibility="collapsed")
    with col_btn:
        btn_crear = st.button("Renderizar", type="primary", use_container_width=True)

    espacio_animacion = st.empty()

    if btn_crear:
        if not url_video: st.warning("Por favor, pega un enlace primero.")
        elif creditos < cant_clips: st.error("❌ No tienes suficientes créditos para esta acción.")
        else:
            st.session_state.mis_clips_data = []
            logo_path = "logo_tmp.png" if archivo_logo else None
            if logo_path:
                with open(logo_path, "wb") as f: f.write(archivo_logo.getbuffer())
            
            try:
                lista = procesar_video_master(url_video, cant_clips, dur_clips[0], dur_clips[1], espacio_animacion)
                for i, cl in enumerate(lista):
                    espacio_animacion.markdown(f"<div class='loader-container'><div class='pulse-ring'></div><h3>✂️ Renderizando {i+1}/{len(lista)}</h3></div>", unsafe_allow_html=True)
                    r = renderizar_un_clip(i+1, cl["inicio"], cl["fin"], cl["titulo"], st.session_state.whisper_data, st.session_state.video_bruto_path, f"/System/Library/Fonts/Supplemental/{f_def}.ttf", tfs, c_t, c_b, afs, col_s_ass, aout, amv, logo_path)
                    if r: st.session_state.mis_clips_data.append({"id": i+1, "inicio": cl["inicio"], "fin": cl["fin"], "titulo": cl["titulo"], "ruta": r})
                
                espacio_animacion.empty()
                if st.session_state.mis_clips_data:
                    gastar_creditos(st.session_state.user_email, cant_clips)
                    st.rerun()
            except Exception as e:
                espacio_animacion.empty()
                st.error(f"Error 403: YouTube ha detectado el servidor en la nube. ¡Intenta con un vídeo diferente o espera unos minutos a que pase el bloqueo!")

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
                    st.download_button(
                        label="⬇️ Descargar HD", 
                        data=f, 
                        file_name=f"Clip_{clip['id']}.mp4", 
                        mime="video/mp4", 
                        use_container_width=True
                    )
                st.markdown("</div>", unsafe_allow_html=True)