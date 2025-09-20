import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from src.vectorstore import get_vector_store
from src import CONFIG
from src.utils import format_docs, chat_stream
from chat_db import init_chat_table, load_conversations, save_message  # ajout DB

OPENAI_API_KEY = CONFIG["OPENAI_API_KEY"]
BASE_DIR = "./collections"

# --- Vérification login ---
# --- Vérification login ---
if "logged_in" not in st.session_state or not st.session_state.logged_in:
    st.error("🚫 Accès refusé. Veuillez vous connecter.")
    if st.button("🔑 Retour à la connexion"):
        st.switch_page("app.py")
    st.stop()

# --- Vérification rôle ---
if st.session_state.role == "admin":
    st.error("🚫 Accès refusé. Les admins ne peuvent pas accéder au chat.")
    st.stop()

# --- Initialisation DB pour conversations ---
init_chat_table()
matricule = st.session_state["matricule"]

# Charger conversations depuis DB
if "conversations" not in st.session_state:
    st.session_state.conversations = load_conversations(matricule)
    if not st.session_state.conversations:
        st.session_state.conversations = {"Conversation 1": []}

if "active_conv" not in st.session_state:
    st.session_state.active_conv = list(st.session_state.conversations.keys())[0]

st.write(f"Bienvenue {st.session_state.nom} {st.session_state.prenom} 👋")

# --- Header avec bouton déconnexion ---
col1, col2 = st.columns([8, 1])
with col1:
    st.title("💬 Interrogez vos documents")
with col2:
    if st.button("🔓 "):
        st.session_state.clear()
        st.switch_page("app.py")

# --- Sidebar : gestion des conversations ---
with st.sidebar:
    st.subheader("💬 Gestion des conversations")

    conv_names = list(st.session_state.conversations.keys())

    # Sélection conversation
    selected_conv = st.selectbox(
        "📂 Sélectionner une conversation",
        conv_names,
        index=conv_names.index(st.session_state.active_conv),
        key="conv_selectbox"
    )
    st.session_state.active_conv = selected_conv

    # Actions (nouvelle / supprimer)
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("➕ Nouvelle", use_container_width=True):
            new_name = f"Conversation {len(conv_names) + 1}"
            st.session_state.conversations[new_name] = []
            st.session_state.active_conv = new_name
            st.rerun()

    with col2:
        if st.button("🗑️ Supprimer", use_container_width=True):
            conv_to_delete = st.session_state.active_conv

            # Supprimer en mémoire
            st.session_state.conversations.pop(conv_to_delete, None)

            # Supprimer aussi en DB
            from chat_db import delete_conversation
            delete_conversation(matricule, conv_to_delete)

            # Rester sur une autre conv si dispo
            if st.session_state.conversations:
                st.session_state.active_conv = list(st.session_state.conversations.keys())[0]
            else:
                st.session_state.conversations = {"Conversation 1": []}
                st.session_state.active_conv = "Conversation 1"

            st.success(f"✅ {conv_to_delete} supprimée.")
            st.rerun()


# --- Préparation du modèle et du retriever ---
vector_store = get_vector_store()
llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY, temperature=0.7)

template = """
Tu es Hugo, un assistant juridique spécialisé dans le domaine bancaire. 
Ta mission est de répondre uniquement aux questions juridiques relatives au secteur bancaire, en t’appuyant exclusivement sur les documents fournis et les éléments de contexte.

Règles de comportement :
- Si la question ne concerne pas le juridique ou le domaine bancaire, réponds : « Merci de poser des questions juridiques dans le domaine bancaire ! ».
- Si on te demande « Bonjour » ,« Parle-moi de toi », « Qui es-tu ? » ou « Que sais-tu faire ? », tu peux répondre brièvement à propos de ton rôle.
- Si la réponse n’est pas présente dans les documents ou que tu n’en es pas certain, dis simplement que tu ne sais pas. N’invente jamais de réponse.
- Donne toujours une réponse claire, concise (maximum trois phrases).
- Termine toujours ta réponse par : « merci de m'avoir posé la question ! ».

Contexte : {context}

Question : {question}
"""

prompt = PromptTemplate.from_template(template)

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

# --- Affichage de l’historique ---
for msg in st.session_state.conversations[st.session_state.active_conv]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Input utilisateur ---
if user_input := st.chat_input("💬 Pose ta question ici..."):
    # Ajout + sauvegarde du message utilisateur
    st.session_state.conversations[st.session_state.active_conv].append(
        {"role": "user", "content": user_input}
    )
    save_message(matricule, st.session_state.active_conv, "user", user_input)

    with st.chat_message("user"):
        st.markdown(user_input)

    # Génération réponse
    response = chain.invoke(user_input)

    with st.spinner("Génération de la réponse..."):
        with st.chat_message("assistant"):
            stream_text = st.write_stream(chat_stream(response))

    # Ajout + sauvegarde du message assistant
    st.session_state.conversations[st.session_state.active_conv].append(
        {"role": "assistant", "content": response}
    )
    save_message(matricule, st.session_state.active_conv, "assistant", response)
