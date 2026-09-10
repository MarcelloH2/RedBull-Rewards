import streamlit as st
import firebase_admin
import av
import io
import time
import threading

from firebase_admin import credentials, firestore
from google import genai
from google.genai import types

from streamlit_webrtc import (
    webrtc_streamer,
    WebRtcMode,
    VideoProcessorBase
)

from PIL import ImageDraw


# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================

st.set_page_config(
    page_title="RedBull Rewards",
    page_icon="🥤",
    layout="centered"
)


# =========================================================
# CSS
# =========================================================

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


# =========================================================
# FIREBASE
# =========================================================

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


# =========================================================
# GEMINI
# =========================================================

gemini_client = genai.Client(
    api_key=st.secrets["gemini"]["api_key"]
)


# =========================================================
# ANALISAR IMAGEM
# =========================================================

def verificar_redbull(imagem_bytes):

    imagem = types.Part.from_bytes(
        data=imagem_bytes,
        mime_type="image/jpeg"
    )

    prompt = """
Analise cuidadosamente esta imagem.

Determine se existe uma LATA FÍSICA
da bebida energética RED BULL
claramente visível na imagem.

Responda SIM somente se:

- houver uma lata física;
- a lata for claramente Red Bull;
- a marca Red Bull estiver identificável;
- a lata estiver suficientemente visível;
- houver boa confiança na identificação.

Responda NAO se:

- não houver lata;
- for outra bebida;
- for outra marca;
- for garrafa;
- for somente um logotipo;
- for desenho;
- for ilustração;
- a imagem estiver muito ruim;
- não houver certeza de que é Red Bull.

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

                    # 1ª falha -> espera 2s
                    # 2ª falha -> espera 4s
                    espera = 2 ** (tentativa + 1)

                    time.sleep(espera)

                    continue

                raise Exception(
                    "O Gemini está temporariamente "
                    "indisponível. Tente novamente "
                    "em alguns instantes."
                )

            raise erro

    return False


# =========================================================
# REGISTRAR LATINHA
# =========================================================

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


# =========================================================
# PROCESSADOR DO VÍDEO
# =========================================================

class RedBullProcessor(VideoProcessorBase):

    def __init__(self, email):

        self.email = email

        # -------------------------
        # TEMPO
        # -------------------------

        self.tempo_limite = 15

        self.inicio_tentativa = time.time()

        self.fim_tentativa = (
            self.inicio_tentativa
            + self.tempo_limite
        )

        # -------------------------
        # ANÁLISE
        # -------------------------

        self.intervalo_analise = 1.5

        self.ultima_analise = 0

        self.analisando = False

        self.redbull_detectada = False

        self.confirmacoes = 0

        self.confirmacoes_necessarias = 2

        self.pontuou = False

        self.erro = None

        self.lock = threading.Lock()


    # =====================================================
    # TEMPO RESTANTE
    # =====================================================

    def tempo_restante(self):

        restante = (
            self.fim_tentativa
            - time.time()
        )

        return max(
            0,
            int(restante) + 1
        )


    # =====================================================
    # ANALISAR FRAME
    # =====================================================

    def analisar_frame(
        self,
        imagem_bytes,
        momento_captura
    ):

        try:

            resultado = verificar_redbull(
                imagem_bytes
            )

            precisa_pontuar = False

            with self.lock:

                self.erro = None

                # O que importa é quando
                # a imagem foi CAPTURADA.
                #
                # Se a imagem foi capturada
                # antes dos 15 segundos,
                # a resposta ainda será aceita.

                if (
                    momento_captura
                    > self.fim_tentativa
                ):

                    return

                self.redbull_detectada = (
                    resultado
                )

                if resultado:

                    self.confirmacoes += 1

                    if (
                        self.confirmacoes
                        >=
                        self.confirmacoes_necessarias
                        and not self.pontuou
                    ):

                        # Marca primeiro para evitar
                        # pontuação duplicada.
                        self.pontuou = True

                        precisa_pontuar = True

                else:

                    self.confirmacoes = 0


            # Firestore fora do lock
            # para não travar o vídeo.
            if precisa_pontuar:

                try:

                    registrar_latinha(
                        self.email,
                        10
                    )

                except Exception as erro_firestore:

                    with self.lock:

                        self.pontuou = False

                        self.erro = (
                            "Erro ao registrar pontos: "
                            + str(erro_firestore)
                        )


        except Exception as erro:

            with self.lock:

                self.erro = str(erro)

                self.redbull_detectada = False


        finally:

            with self.lock:

                self.analisando = False


    # =====================================================
    # RECEBER FRAME
    # =====================================================

    def recv(self, frame):

        agora = time.time()

        imagem = frame.to_image()

        tempo_restante = (
            self.tempo_restante()
        )


        # =================================================
        # CAPTURAR FRAME PARA ANÁLISE
        # =================================================

        if (
            tempo_restante > 0
            and not self.pontuou
        ):

            tempo_desde_ultima = (
                agora
                - self.ultima_analise
            )

            if (
                tempo_desde_ultima
                >= self.intervalo_analise
            ):

                pode_analisar = False

                with self.lock:

                    if not self.analisando:

                        self.analisando = True

                        pode_analisar = True


                if pode_analisar:

                    self.ultima_analise = agora

                    momento_captura = agora

                    imagem_analise = (
                        imagem.copy()
                    )

                    # Mantém mais detalhes
                    # da lata.
                    imagem_analise.thumbnail(
                        (768, 768)
                    )

                    buffer = io.BytesIO()

                    imagem_analise.save(
                        buffer,
                        format="JPEG",
                        quality=90
                    )

                    imagem_bytes = (
                        buffer.getvalue()
                    )

                    thread = threading.Thread(
                        target=self.analisar_frame,

                        args=(
                            imagem_bytes,
                            momento_captura
                        ),

                        daemon=True
                    )

                    thread.start()


        # =================================================
        # ESTADO ATUAL
        # =================================================

        with self.lock:

            pontuou = (
                self.pontuou
            )

            detectada = (
                self.redbull_detectada
            )

            confirmacoes = (
                self.confirmacoes
            )

            analisando = (
                self.analisando
            )

            erro = (
                self.erro
            )


        # =================================================
        # TEXTO NA CÂMERA
        # =================================================

        draw = ImageDraw.Draw(
            imagem
        )


        # -------------------------
        # VALIDOU
        # -------------------------

        if pontuou:

            texto1 = (
                "RED BULL VALIDADA!"
            )

            texto2 = (
                "+10 PONTOS"
            )


        # -------------------------
        # ACABOU O TEMPO
        # -------------------------

        elif tempo_restante <= 0:

            if analisando:

                texto1 = (
                    "AGUARDANDO ANALISE..."
                )

                texto2 = (
                    "Processando ultima imagem"
                )

            else:

                texto1 = (
                    "TEMPO ENCERRADO"
                )

                texto2 = (
                    "STOP e START para tentar novamente"
                )


        # -------------------------
        # ERRO
        # -------------------------

        elif erro:

            texto1 = (
                "ERRO NA ANALISE"
            )

            texto2 = (
                "Tentando novamente..."
            )


        # -------------------------
        # DETECTOU
        # -------------------------

        elif detectada:

            texto1 = (
                "RED BULL DETECTADA"
            )

            texto2 = (
                f"Validacao "
                f"{confirmacoes}/2"
            )


        # -------------------------
        # GEMINI ANALISANDO
        # -------------------------

        elif analisando:

            texto1 = (
                f"Tempo: "
                f"{tempo_restante}s"
            )

            texto2 = (
                "Gemini analisando..."
            )


        # -------------------------
        # PROCURANDO
        # -------------------------

        else:

            texto1 = (
                f"Tempo: "
                f"{tempo_restante}s"
            )

            texto2 = (
                "Aponte para uma Red Bull"
            )


        # =================================================
        # FUNDO DO TEXTO
        # =================================================

        draw.rectangle(
            (
                10,
                10,
                520,
                90
            ),
            fill="black"
        )


        draw.text(
            (
                20,
                20
            ),
            texto1,
            fill="white"
        )


        draw.text(
            (
                20,
                52
            ),
            texto2,
            fill="white"
        )


        # =================================================
        # DEVOLVER FRAME
        # =================================================

        return av.VideoFrame.from_image(
            imagem
        )


# =========================================================
# LOGIN
# =========================================================

if not st.user.is_logged_in:

    st.markdown(
        """
        <div class="titulo">
            🥤 RedBull Rewards
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        """
        <div class="subtitulo">
            Entre para começar
            a acumular pontos!
        </div>
        """,
        unsafe_allow_html=True
    )

    st.write("")

    if st.button(
        "🔐 Entrar com Google",
        use_container_width=True
    ):

        st.login()

    st.stop()


# =========================================================
# DADOS DO USUÁRIO
# =========================================================

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


# =========================================================
# FIRESTORE - USUÁRIO
# =========================================================

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


# =========================================================
# CABEÇALHO
# =========================================================

st.markdown(
    """
    <div class="titulo">
        🥤 RedBull Rewards
    </div>
    """,
    unsafe_allow_html=True
)


st.markdown(
    """
    <div class="subtitulo">
        Recicle suas latinhas Red Bull
        e acumule pontos!
    </div>
    """,
    unsafe_allow_html=True
)


st.markdown(
    f"""
    <div class="usuario">

        👋 Olá, <b>{nome}</b>

        <br>

        {email}

    </div>
    """,
    unsafe_allow_html=True
)


# =========================================================
# PONTOS
# =========================================================

st.divider()

col1, col2 = st.columns(2)


with col1:

    st.metric(
        label="⭐ Seus pontos",
        value=pontos
    )


with col2:

    st.metric(
        label="🥤 Latinhas",
        value=latinhas
    )


# =========================================================
# RECICLAGEM
# =========================================================

st.divider()

st.subheader(
    "♻️ Escanear Red Bull"
)


st.write(
    "Pressione **START** e aponte "
    "a câmera para a latinha. "
    "Você terá **15 segundos** "
    "para realizar a validação."
)


st.write(
    "Tente deixar a lata relativamente "
    "perto da câmera, com o nome e o "
    "logotipo da Red Bull visíveis."
)


# =========================================================
# WEBRTC
# =========================================================

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


# =========================================================
# INFORMAÇÃO
# =========================================================

st.info(
    "🥤 São necessárias duas "
    "confirmações da Red Bull "
    "para receber 10 pontos."
)


# =========================================================
# ATUALIZAR SALDO
# =========================================================

if st.button(
    "🔄 Atualizar saldo",
    use_container_width=True
):

    st.rerun()


# =========================================================
# LOGOUT
# =========================================================

st.divider()

if st.button(
    "🚪 Sair da conta",
    use_container_width=True
):

    st.logout()