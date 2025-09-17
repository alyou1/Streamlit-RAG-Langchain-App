import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from src.vectorstore import get_vector_store
from src import CONFIG
from src.utils import format_docs, chat_stream

OPENAI_API_KEY = CONFIG["OPENAI_API_KEY"]
BASE_DIR = "./collections"

# --- Vérification login ---
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("🚫 Accès refusé. Veuillez vous connecter.")
    if st.button("🔑 Retour à la connexion"):
        st.switch_page("app.py")
    st.stop()

# Exemple page chat
if st.session_state.role == "admin":
    st.error("🚫 Accès refusé. Les admins ne peuvent pas accéder au chat.")
    st.stop()

st.write(f"Bienvenue {st.session_state.nom} {st.session_state.prenom} 👋")

# --- Header avec bouton déconnexion ---
col1, col2 = st.columns([8, 1])
with col1:
    st.title("💬 Interrogez vos documents")
with col2:
    if st.button("🔓 "):
        st.session_state.clear()  # on reset la session
        st.switch_page("app.py")

# --- Initialisation des conversations ---
if "conversations" not in st.session_state:
    st.session_state.conversations = {"Conversation 1": []}
if "active_conv" not in st.session_state:
    st.session_state.active_conv = "Conversation 1"

# --- Sidebar pour gérer les conversations ---
with st.sidebar:
    st.subheader("💬 Conversations")
    conv_names = list(st.session_state.conversations.keys())
    selected_conv = st.selectbox(
        "Choisir une conversation",
        conv_names,
        index=conv_names.index(st.session_state.active_conv)
    )
    st.session_state.active_conv = selected_conv

    if st.button("➕ Nouvelle conversation"):
        new_name = f"Conversation {len(conv_names) + 1}"
        st.session_state.conversations[new_name] = []
        st.session_state.active_conv = new_name
        st.rerun()

# --- Préparation du modèle et du retriever ---
vector_store = get_vector_store()

llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY, temperature=0.7)
#
# prompt = ChatPromptTemplate.from_template(
#     "Réponds à la question suivante en utilisant le contexte.\n\n"
#     "Contexte:\n{context}\n\nQuestion:\n{question}\n\nRéponse:"
# )

template = """
Tu es Hugo, un assistant juridique spécialisé dans le domaine bancaire. 
Ta mission est de répondre uniquement aux questions juridiques relatives au secteur bancaire, en t’appuyant exclusivement sur les documents fournis et les éléments de contexte.

Règles de comportement :
- Si la question ne concerne pas le juridique ou le domaine bancaire, réponds : « Merci de poser des questions juridiques dans le domaine bancaire ! ».
- Si on te demande « Parle-moi de toi », « Qui es-tu ? » ou « Que sais-tu faire ? », tu peux répondre brièvement à propos de ton rôle.
- Si la réponse n’est pas présente dans les documents ou que tu n’en es pas certain, dis simplement que tu ne sais pas. N’invente jamais de réponse.
- Donne toujours une réponse claire, concise (maximum trois phrases).
- Termine toujours ta réponse par : « merci de m'avoir posé la question ! ».

Contexte : {context}

Question : {question}
"""

prompt =  PromptTemplate.from_template(template)

retriever = vector_store.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={"score_threshold": 0.5, "k": 5}
)

chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough(),
    }
    | prompt
    | llm
    | StrOutputParser()
)

# --- Affichage historique ---
for msg in st.session_state.conversations[st.session_state.active_conv]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Input utilisateur ---
if user_input := st.chat_input("💬 Pose ta question ici..."):
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.conversations[st.session_state.active_conv].append(
        {"role": "user", "content": user_input}
    )

    response = chain.invoke(user_input)

    with st.spinner("Génération de la réponse..."):
        with st.chat_message("assistant"):
            stream_text = st.write_stream(chat_stream(response))

    st.session_state.conversations[st.session_state.active_conv].append(
        {"role": "assistant", "content": response}
    )
