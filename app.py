import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from google import genai
from google.genai import types


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
# ANALISAR FOTO COM GEMINI
# =========================

def analisar_latinha_redbull(foto):

    imagem_bytes = foto.getvalue()

    mime_type = (
        foto.type
        if foto.type
        else "image/jpeg"
    )

    imagem = types.Part.from_bytes(
        data=imagem_bytes,
        mime_type=mime_type
    )

    prompt = """
Analise cuidadosamente esta imagem.

Quero saber se existe uma LATA FÍSICA
de bebida energética RED BULL
claramente visível na imagem.

Regras:

- Deve ser uma lata física de Red Bull.
- O logotipo ou identidade visual da
  Red Bull deve estar suficientemente
  visível para identificar a marca.
- Não aceite apenas o logotipo isolado.
- Não aceite garrafas.
- Não aceite outros produtos da Red Bull.
- Não aceite outras marcas de energético.
- Não aceite desenhos ou ilustrações.
- Não aceite quando não for possível
  ter confiança de que é uma lata Red Bull.

Responda SOMENTE com uma das palavras:

SIM

ou

NAO
"""

    resposta = (
        gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                prompt,
                imagem
            ]
        )
    )

    resultado = (
        resposta.text
        .strip()
        .upper()
        .replace("Ã", "A")
    )

    return resultado.startswith("SIM")


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
# CÂMERA
# =========================

st.divider()

st.subheader(
    "📸 Reciclar uma Red Bull"
)

st.write(
    "Tire uma foto mostrando claramente "
    "a latinha Red Bull."
)

foto = st.camera_input(
    "Tirar foto da latinha"
)


# =========================
# ANALISAR FOTO
# =========================

if foto is not None:

    if st.button(
        "🤖 Verificar latinha",
        use_container_width=True
    ):

        with st.spinner(
            "Analisando a imagem..."
        ):

            try:

                eh_redbull = (
                    analisar_latinha_redbull(
                        foto
                    )
                )

                if eh_redbull:

                    registrar_latinha(
                        email=email,
                        pontos_por_latinha=10
                    )

                    st.success(
                        "✅ Latinha Red Bull "
                        "identificada! +10 pontos"
                    )

                    st.balloons()

                    st.rerun()

                else:

                    st.error(
                        "❌ Não foi possível "
                        "identificar uma latinha "
                        "Red Bull."
                    )

                    st.warning(
                        "Nenhum ponto foi adicionado."
                    )

            except Exception as erro:

                st.error(
                    "Ocorreu um erro ao analisar "
                    "a imagem."
                )

                st.code(
                    str(erro)
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