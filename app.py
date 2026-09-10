import streamlit as st
import firebase_admin
import av

from firebase_admin import credentials, firestore
from google import genai
from google.genai import types

from streamlit_webrtc import (
    webrtc_streamer,
    WebRtcMode,
    VideoProcessorBase
)

from PIL import ImageDraw

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
# VERIFICAR RED BULL
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

    tentativas = 3

    for tentativa in range(tentativas):

        try:

            resposta = (
                gemini_client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=[
                        imagem,
                        prompt
                    ]
                )
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

        except Exception as erro:

            mensagem = str(erro)

            erro_temporario = (
                "503" in mensagem
                or "UNAVAILABLE" in mensagem
                or "429" in mensagem
                or "RESOURCE_EXHAUSTED" in mensagem
            )

            if erro_temporario:

                if tentativa < tentativas - 1:

                    tempo_espera = (
                        2 ** (tentativa + 1)
                    )

                    time.sleep(
                        tempo_espera
                    )

                    continue

                raise Exception(
                    "Gemini temporariamente "
                    "indisponível."
                )

            raise erro

    return False


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

        # =========================
        # TEMPO DA TENTATIVA
        # =========================

        self.tempo_limite = 10

        self.inicio_tentativa = (
            time.time()
        )

        self.fim_tentativa = (
            self.inicio_tentativa
            + self.tempo_limite
        )

        # =========================
        # ANÁLISE
        # =========================

        self.intervalo_analise = 2

        self.ultima_analise = 0

        self.analisando = False

        self.redbull_detectada = False

        self.confirmacoes = 0

        self.confirmacoes_necessarias = 2

        self.pontuou = False

        self.erro = None

        self.lock = threading.Lock()


    # =========================
    # TEMPO RESTANTE
    # =========================

    def tempo_restante(self):

        restante = (
            self.fim_tentativa
            - time.time()
        )

        return max(
            0,
            int(restante) + 1
        )


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

                # Se a resposta da IA chegou
                # depois dos 10 segundos,
                # não vale mais.
                if (
                    time.time()
                    >= self.fim_tentativa
                ):

                    self.redbull_detectada = False

                    self.confirmacoes = 0

                    return

                self.erro = None

                self.redbull_detectada = (
                    resultado
                )

                if resultado:

                    self.confirmacoes += 1

                    # =========================
                    # LATINHA VALIDADA
                    # =========================

                    if (
                        self.confirmacoes
                        >=
                        self.confirmacoes_necessarias
                        and not self.pontuou
                    ):

                        registrar_latinha(
                            self.email,
                            10
                        )

                        self.pontuou = True

                else:

                    self.confirmacoes = 0

        except Exception as erro:

            with self.lock:

                self.erro = str(erro)

                self.confirmacoes = 0

                self.redbull_detectada = False

        finally:

            with self.lock:

                self.analisando = False


    # =========================
    # RECEBER VÍDEO
    # =========================

    def recv(self, frame):

        agora = time.time()

        imagem = frame.to_image()


        # =========================
        # VERIFICA TEMPO
        # =========================

        tempo_restante = (
            self.tempo_restante()
        )


        # =========================
        # ANALISAR SOMENTE
        # DURANTE OS 10 SEGUNDOS
        # =========================

        if (
            tempo_restante > 0
            and not self.pontuou
        ):

            tempo_passado = (
                agora
                - self.ultima_analise
            )

            if (
                tempo_passado
                >= self.intervalo_analise
            ):

                pode_analisar = False

                with self.lock:

                    if not self.analisando:

                        self.analisando = True

                        pode_analisar = True

                if pode_analisar:

                    self.ultima_analise = (
                        agora
                    )

                    imagem_analise = (
                        imagem.copy()
                    )

                    imagem_analise.thumbnail(
                        (640, 640)
                    )

                    buffer = io.BytesIO()

                    imagem_analise.save(
                        buffer,
                        format="JPEG",
                        quality=80
                    )

                    imagem_bytes = (
                        buffer.getvalue()
                    )

                    thread = (
                        threading.Thread(
                            target=
                            self.analisar_frame,

                            args=(
                                imagem_bytes,
                            ),

                            daemon=True
                        )
                    )

                    thread.start()


        # =========================
        # TEXTO SOBRE O VÍDEO
        # =========================

        draw = ImageDraw.Draw(
            imagem
        )

        with self.lock:

            pontuou = self.pontuou

            detectada = (
                self.redbull_detectada
            )

            confirmacoes = (
                self.confirmacoes
            )

            analisando = (
                self.analisando
            )

            erro = self.erro


        # =========================
        # RESULTADO
        # =========================

        if pontuou:

            texto1 = (
                "RED BULL VALIDADA!"
            )

            texto2 = (
                "+10 PONTOS"
            )

        elif tempo_restante <= 0:

            texto1 = (
                "TEMPO ENCERRADO"
            )

            texto2 = (
                "Pressione STOP e START "
                "para tentar novamente"
            )

        elif erro:

            texto1 = (
                "Erro na analise"
            )

            texto2 = (
                "Tentando novamente..."
            )

        elif detectada:

            texto1 = (
                "RED BULL DETECTADA"
            )

            texto2 = (
                f"Validacao "
                f"{confirmacoes}/2"
            )

        elif analisando:

            texto1 = (
                f"Tempo: "
                f"{tempo_restante}s"
            )

            texto2 = (
                "Analisando..."
            )

        else:

            texto1 = (
                f"Tempo: "
                f"{tempo_restante}s"
            )

            texto2 = (
                "Aponte para uma Red Bull"
            )


        # Fundo para facilitar leitura
        draw.rectangle(
            (10, 10, 440, 85),
            fill="black"
        )

        draw.text(
            (20, 20),
            texto1,
            fill="white"
        )

        draw.text(
            (20, 50),
            texto2,
            fill="white"
        )


        # =========================
        # DEVOLVE FRAME
        # =========================

        novo_frame = (
            av.VideoFrame.from_image(
                imagem
            )
        )

        return novo_frame


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
        'Entre para começar a '
        'acumular pontos!'
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
# BUSCAR USUÁRIO
# =========================

usuario_ref = (
    db.collection("usuarios")
    .document(email)
)

usuario_doc = (
    usuario_ref.get()
)


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

    dados = (
        usuario_doc.to_dict()
    )

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
# SALDO
# =========================

st.divider()

col1, col2 = (
    st.columns(2)
)

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
# RECICLAGEM
# =========================

st.divider()

st.subheader(
    "♻️ Escanear Red Bull"
)

st.write(
    "Pressione START e aponte a câmera "
    "para a latinha. Você terá "
    "**10 segundos** para realizar "
    "a validação."
)


# =========================
# WEBRTC
# =========================

ctx = webrtc_streamer(

    key="camera-redbull",

    mode=WebRtcMode.SENDRECV,

    video_processor_factory=lambda:
        RedBullProcessor(
            email
        ),

    media_stream_constraints={
        "video": {
            "facingMode": "environment"
        },
        "audio": False
    },

    async_processing=True
)


# =========================
# INFORMAÇÕES
# =========================

st.info(
    "🥤 Mantenha a Red Bull visível "
    "durante a validação. "
    "São necessárias duas confirmações."
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