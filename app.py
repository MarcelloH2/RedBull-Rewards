import streamlit as st
import qrcode
from io import BytesIO
import streamlit as st

# =========================
# CONFIGURAÇÃO DA PÁGINA
# =========================

st.set_page_config(
    page_title="RedBull Rewards",
    page_icon="🥤",
    layout="centered"
)

# =========================
# ESTILO DA INTERFACE
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

    .instrucao {
        text-align: center;
        font-size: 18px;
        color: #555;
        margin-top: 20px;
    }

    .usuario {
        text-align: center;
        font-size: 18px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

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
        'Entre para começar a acumular pontos'
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
# USUÁRIO LOGADO
# =========================

st.markdown(
    '<div class="titulo">🥤 RedBull Rewards</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitulo">'
    'Recicle sua latinha e acumule pontos!'
    '</div>',
    unsafe_allow_html=True
)

# Nome do usuário
nome_usuario = st.user.get("name", "Usuário")
email_usuario = st.user.get("email", "")

st.markdown(
    f"""
    <div class="usuario">
        👋 Olá, <b>{nome_usuario}</b><br>
        {email_usuario}
    </div>
    """,
    unsafe_allow_html=True
)

# =========================
# BOTÃO DE SAIR
# =========================

if st.button(
    "🚪 Sair da conta",
    use_container_width=True
):
    st.logout()

st.divider()

# =========================
# QR CODE
# =========================

link_login = "https://ecofluxobr-dd73ey4nolbw2ecfktumzi.streamlit.app/"

qr = qrcode.QRCode(
    version=1,
    box_size=10,
    border=4
)

qr.add_data(link_login)
qr.make(fit=True)

imagem_qr = qr.make_image()

buffer = BytesIO()
imagem_qr.save(buffer, format="PNG")

# =========================
# QR CODE CENTRALIZADO
# =========================

col_esquerda, col_centro, col_direita = st.columns([1, 2, 1])

with col_centro:
    st.image(
        buffer.getvalue(),
        width=300
    )

# =========================
# INSTRUÇÃO
# =========================

st.markdown(
    '<div class="instrucao">'
    '📱 Escaneie o QR Code para começar'
    '</div>',
    unsafe_allow_html=True
)