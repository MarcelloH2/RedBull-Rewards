import streamlit as st
import firebase_admin

from firebase_admin import credentials, firestore
from google import genai
from google.genai import types

from streamlit_webrtc import (
    webrtc_streamer,
    WebRtcMode,
    VideoProcessorBase
)

from PIL import Image

import av
import io
import time
import threading


# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================

st.set_page_config(
    page_title="RedBull Rewards",
    page_icon="🥤",
    layout="centered"
)


# =========================
# ESTILO
# =========================

st.markdown("""
<style>

.stApp {
    background-color: #f5f5f5;
}

.titulo {
    text-align: center;
    font-size: 42px;
    font-weight: bold;
    color: #cc0000;
    margin-top: 40px;
    margin-bottom: 10px;
}

.subtitulo {
    text-align: center;
    font-size: 20px;
    color: #555;
    margin-bottom: 30px;
}

.usuario {
    text-align: center;
    font-size: 18px;
    margin-bottom: 20px;
}

.status-detectando {
    text-align: center;
    font-size: 20px;
    font-weight: bold;
}

</style>
""", unsafe_allow_html=True)


# =========================
# FIREBASE / FIRESTORE
# =========================

if not firebase_admin._apps:

    firebase_config = dict(
        st.secrets["firebase"]
    )

    cred = credentials.Certificate(
        firebase_config
    )

    firebase_admin.initialize_app(
        cred
    )

db = firestore.client()


# =========================
# GEMINI
# =========================

gemini_client = genai.Client(
    api_key=st.secrets["gemini"]["api_key"]
)


# =========================
# FUNÇÃO GEMINI
# =========================

def verificar_redbull(imagem_bytes):

    imagem = types.Part.from_bytes(
        data=imagem_bytes,
        mime_type="image/jpeg"
    )

    prompt = """
Analise esta imagem.

Determine se existe uma LATA FÍSICA
da bebida energética RED BULL
claramente visível.

Considere SIM somente quando:

- for realmente uma lata;
- for claramente da marca Red Bull;
- a lata estiver suficientemente visível;
- houver confiança razoável na identificação.

Considere NAO quando:

- for outra marca;
- for garrafa;
- for apenas o logotipo;
- for desenho ou ilustração;
- a imagem estiver ruim ou duvidosa;
- não houver uma lata Red Bull claramente identificável.

Responda SOMENTE:

SIM

ou

NAO
"""

    resposta = gemini_client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[
            imagem,
            prompt
        ]
    )

    if not resposta.text:
        return False

    resultado = (
        resposta.text
        .strip()
        .upper()
        .replace("Ã", "A")
    )

    return resultado.startswith("SIM")


# =========================
# REGISTRAR LATINHA
# =========================

def registrar_latinha(
    email,
    pontos_por_latinha=10
):

    usuario_ref = (
        db.collection("usuarios")
        .document(email)
    )

    usuario_ref.update({
        "latinhas": firestore.Increment(1),
        "pontos": firestore.Increment(
            pontos_por_latinha
        )
    })


# =========================
# PROCESSADOR DO VÍDEO
# =========================

class RedBullProcessor(VideoProcessorBase):

    def __init__(self, email):

        self.email = email

        self.ultima_analise = 0

        self.intervalo_analise = 2

        self.confirmacoes = 0

        self.necessarias = 2

        self.analisando = False

        self.redbull_detectada = False

        self.pontuou = False

        self.erro = None

        self.lock = threading.Lock()

        # Depois que pontua,
        # precisa a lata desaparecer
        # antes de pontuar outra vez
        self.bloqueado = False

        self.frames_sem_redbull = 0


    # =========================
    # ANALISAR FRAME
    # =========================

    def analisar_frame(
        self,
        imagem_bytes
    ):

        try:

            resultado = verificar_redbull(
                imagem_bytes
            )

            with self.lock:

                self.redbull_detectada = resultado

                # =========================
                # RED BULL DETECTADA
                # =========================

                if resultado:

                    self.frames_sem_redbull = 0

                    if not self.bloqueado:

                        self.confirmacoes += 1

                        if (
                            self.confirmacoes
                            >= self.necessarias
                        ):

                            registrar_latinha(
                                self.email,
                                10
                            )

                            self.pontuou = True

                            self.bloqueado = True

                            self.confirmacoes = 0

                # =========================
                # NÃO DETECTOU
                # =========================

                else:

                    self.confirmacoes = 0

                    self.frames_sem_redbull += 1

                    # Precisa não detectar
                    # em 2 análises
                    # para liberar outra lata
                    if (
                        self.frames_sem_redbull
                        >= 2
                    ):

                        self.bloqueado = False

                        self.frames_sem_redbull = 0

        except Exception as erro:

            with self.lock:

                self.erro = str(erro)

                self.confirmacoes = 0

        finally:

            with self.lock:
                self.analisando = False


    # =========================
    # RECEBER FRAME
    # =========================

    def recv(self, frame):

        agora = time.time()

        # Analisa aproximadamente
        # a cada 2 segundos
        if (
            agora - self.ultima_analise
            >= self.intervalo_analise
        ):

            with self.lock:

                pode_analisar = (
                    not self.analisando
                )

                if pode_analisar:
                    self.analisando = True

            if pode_analisar:

                self.ultima_analise = agora

                imagem = frame.to_image()

                # Reduz tamanho para
                # deixar a análise mais leve
                imagem.thumbnail(
                    (640, 640)
                )

                buffer = io.BytesIO()

                imagem.save(
                    buffer,
                    format="JPEG",
                    quality=80
                )

                imagem_bytes = (
                    buffer.getvalue()
                )

                thread = threading.Thread(
                    target=self.analisar_frame,
                    args=(imagem_bytes,),
                    daemon=True
                )

                thread.start()

        return frame


# =========================
# AUTENTICAÇÃO
# =========================

if not st.user.is_logged_in:

    st.markdown(
        '<div class="titulo">'
        '🥤 RedBull Rewards'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitulo">'
        'Entre para começar a acumular pontos!'
        '</div>',
        unsafe_allow_html=True
    )

    if st.button(
        "🔐 Entrar com Google",
        use_container_width=True
    ):
        st.login()

    st.stop()


# =========================
# USUÁRIO
# =========================

nome = st.user.get(
    "name",
    "Usuário"
)

email = st.user.get(
    "email",
    ""
)

if not email:

    st.error(
        "Não foi possível obter "
        "o e-mail da conta Google."
    )

    st.stop()


# =========================
# FIRESTORE - USUÁRIO
# =========================

usuario_ref = (
    db.collection("usuarios")
    .document(email)
)

usuario_doc = usuario_ref.get()


if not usuario_doc.exists:

    usuario_ref.set({
        "nome": nome,
        "email": email,
        "pontos": 0,
        "latinhas": 0
    })

    pontos = 0
    latinhas = 0

else:

    dados = usuario_doc.to_dict()

    pontos = dados.get(
        "pontos",
        0
    )

    latinhas = dados.get(
        "latinhas",
        0
    )


# =========================
# INTERFACE
# =========================

st.markdown(
    '<div class="titulo">'
    '🥤 RedBull Rewards'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitulo">'
    'Recicle suas latinhas Red Bull '
    'e acumule pontos!'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="usuario">
        👋 Olá, <b>{nome}</b><br>
        {email}
    </div>
    """,
    unsafe_allow_html=True
)


# =========================
# PONTOS
# =========================

st.divider()

col1, col2 = st.columns(2)

with col1:

    st.metric(
        "⭐ Seus pontos",
        pontos
    )

with col2:

    st.metric(
        "🥤 Latinhas",
        latinhas
    )


# =========================
# CÂMERA
# =========================

st.divider()

st.subheader(
    "📹 Reciclagem em tempo real"
)

st.write(
    "Aponte a câmera para uma "
    "latinha Red Bull e mantenha "
    "ela visível por alguns segundos."
)


# =========================
# WEBRTC
# =========================

ctx = webrtc_streamer(

    key="camera-redbull",

    mode=WebRtcMode.SENDRECV,

    video_processor_factory=lambda:
        RedBullProcessor(email),

    media_stream_constraints={
        "video": {
            "facingMode": "environment"
        },
        "audio": False
    },

    async_processing=True
)


# =========================
# STATUS
# =========================

if ctx.video_processor:

    processor = ctx.video_processor

    with processor.lock:

        detectada = (
            processor.redbull_detectada
        )

        confirmacoes = (
            processor.confirmacoes
        )

        pontuou = (
            processor.pontuou
        )

        erro = processor.erro

        analisando = (
            processor.analisando
        )

    if erro:

        st.error(
            "Erro na análise da imagem:"
        )

        st.code(erro)

    elif pontuou:

        st.success(
            "♻️ Latinha Red Bull validada!"
        )

        st.success(
            "⭐ +10 pontos"
        )

    elif detectada:

        st.success(
            "🥤 Red Bull detectada!"
        )

        st.write(
            f"Verificação "
            f"{confirmacoes}/2"
        )

    elif analisando:

        st.info(
            "🔍 Analisando..."
        )

    else:

        st.info(
            "🔍 Procurando uma latinha "
            "Red Bull..."
        )


# =========================
# INFORMAÇÃO
# =========================

st.divider()

st.info(
    "🥤 Mantenha a latinha visível "
    "por alguns segundos. "
    "Duas confirmações são necessárias."
)


# =========================
# ATUALIZAR SALDO
# =========================

if st.button(
    "🔄 Atualizar saldo",
    use_container_width=True
):

    st.rerun()


# =========================
# LOGOUT
# =========================

st.divider()

if st.button(
    "🚪 Sair da conta",
    use_container_width=True
):

    st.logout()