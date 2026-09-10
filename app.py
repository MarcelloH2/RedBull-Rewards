import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google import genai
from streamlit_webrtc import webrtc_streamer, WebRtcMode


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

    st.write("")

    if st.button(
        "🔐 Entrar com Google",
        use_container_width=True
    ):
        st.login()

    st.stop()


# =========================
# USUÁRIO AUTENTICADO
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
        "Não foi possível obter o e-mail "
        "da conta Google."
    )

    st.stop()


# =========================
# BUSCAR / CRIAR USUÁRIO
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
        label="⭐ Seus pontos",
        value=pontos
    )

with col2:

    st.metric(
        label="🥤 Latinhas",
        value=latinhas
    )


# =========================
# CÂMERA EM TEMPO REAL
# =========================

st.divider()

st.subheader(
    "📹 Reciclagem em tempo real"
)

st.write(
    "Aponte a câmera para uma latinha Red Bull."
)

webrtc_streamer(
    key="camera-redbull",
    mode=WebRtcMode.SENDRECV,
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

st.divider()

st.info(
    "🥤 Cada latinha Red Bull válida "
    "vale 10 pontos."
)


# =========================
# LOGOUT
# =========================

st.divider()

if st.button(
    "🚪 Sair da conta",
    use_container_width=True
):
    st.logout()