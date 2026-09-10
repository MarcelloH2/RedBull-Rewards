import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore


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
    firebase_config = dict(st.secrets["firebase"])

    cred = credentials.Certificate(firebase_config)

    firebase_admin.initialize_app(cred)

db = firestore.client()


# =========================
# FUNÇÃO PARA REGISTRAR LATINHA
# =========================

def registrar_latinha(email, pontos_por_latinha=10):

    usuario_ref = db.collection("usuarios").document(email)

    usuario_ref.update({
        "latinhas": firestore.Increment(1),
        "pontos": firestore.Increment(pontos_por_latinha)
    })


# =========================
# AUTENTICAÇÃO
# =========================

if not st.user.is_logged_in:

    st.markdown(
        '<div class="titulo">🥤 RedBull Rewards</div>',
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

nome = st.user.get("name", "Usuário")
email = st.user.get("email", "")

if not email:
    st.error(
        "Não foi possível obter o e-mail da conta Google."
    )
    st.stop()


# =========================
# BUSCAR / CRIAR USUÁRIO
# =========================

usuario_ref = db.collection("usuarios").document(email)

usuario_doc = usuario_ref.get()


# Primeiro login
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

    pontos = dados.get("pontos", 0)
    latinhas = dados.get("latinhas", 0)


# =========================
# INTERFACE DO USUÁRIO
# =========================

st.markdown(
    '<div class="titulo">🥤 RedBull Rewards</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitulo">'
    'Recicle suas latinhas e acumule pontos!'
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
# PONTOS E LATINHAS
# =========================

st.divider()

st.metric(
    label="⭐ Seus pontos",
    value=pontos
)

st.metric(
    label="🥤 Latinhas recicladas",
    value=latinhas
)


# =========================
# CÂMERA / RECICLAGEM
# =========================

st.subheader("📸 Reciclar uma latinha")

foto = st.camera_input(
    "Tire uma foto da latinha"
)

if foto is not None:

    st.image(
        foto,
        caption="Foto capturada"
    )

    if st.button(
        "✅ Confirmar reciclagem",
        use_container_width=True
    ):

        registrar_latinha(
            email=email,
            pontos_por_latinha=10
        )

        st.success(
            "Latinha registrada! +10 pontos"
        )

        st.rerun()


# =========================
# MENSAGEM
# =========================

if latinhas == 0:

    st.info(
        "🥤 Recicle sua primeira latinha para começar a ganhar pontos!"
    )

else:

    st.success(
        f"🎉 Você já reciclou {latinhas} latinha(s)!"
    )


st.divider()


# =========================
# LOGOUT
# =========================

if st.button(
    "🚪 Sair da conta",
    use_container_width=True
):
    st.logout()